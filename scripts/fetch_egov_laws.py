#!/usr/bin/env python3
"""Fetch selected Japanese law articles from e-Gov API V2.

Outputs backend/data/egov_laws.json in a format compatible with
legal_knowledge.json (id, category, title, content, review_point).

Usage:
    python scripts/fetch_egov_laws.py
"""
import json
import logging
import time
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://laws.e-gov.go.jp/api/2"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "backend" / "data" / "egov_laws.json"
REQUEST_DELAY = 1.5  # seconds between API calls to be polite


# ---------------------------------------------------------------------------
# Target laws: (law_id, short_name, category, article_filter)
#   article_filter: None = all articles, or set of int article numbers
# ---------------------------------------------------------------------------
TARGET_LAWS = [
    # Civil Code - selected sections
    ("129AC0000000089", "minpo", "民法（賃貸借）",
     set(range(601, 623))),  # 601-622
    ("129AC0000000089", "minpo", "民法（請負・委任）",
     set(range(632, 657))),  # 632-656
    ("129AC0000000089", "minpo", "民法（売買）",
     set(range(555, 586))),  # 555-585
    # Land and Building Lease Act - all articles
    ("403AC0000000090", "shakuchi", "借地借家法", None),
    # Labor Standards Act - key articles for employment contracts
    ("322AC0000000049", "roudou_kijun", "労働基準法",
     {1, 2, 3, 4, 5, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24,
      25, 26, 27, 32, 33, 34, 35, 36, 37, 38, 39, 56, 57, 58, 59, 60,
      61, 62, 63, 64, 89, 90, 91, 104, 114, 117, 118, 119, 120}),
    # Labor Contract Act - all articles (small law)
    ("419AC0000000128", "roudou_keiyaku", "労働契約法", None),
    # Consumer Contract Act - all articles
    ("412AC0000000061", "shohisha_keiyaku", "消費者契約法", None),
    # Specified Commercial Transactions Act - key articles
    ("351AC0000000057", "tokusho", "特定商取引法",
     {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 15_2,
      24, 25, 26, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45,
      49, 58, 59}),
    # Part-time Workers Act - key articles
    ("405AC0000000076", "parttime", "パートタイム・有期雇用労働法",
     {1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 23, 24, 25, 26, 31}),
    # Subcontracting Act - all articles (small law)
    ("331AC0000000120", "shitauke", "下請法", None),
]


def fetch_law_data(law_id: str) -> dict:
    """Fetch full law data from e-Gov API V2."""
    url = f"{BASE_URL}/law_data/{law_id}"
    params = {"response_format": "json"}
    logger.info("Fetching %s ...", law_id)
    resp = httpx.get(url, params=params, timeout=120)
    resp.raise_for_status()
    return resp.json()


def extract_text_recursive(node) -> str:
    """Recursively extract all text from a law JSON node."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(extract_text_recursive(item) for item in node)
    if isinstance(node, dict):
        return "".join(extract_text_recursive(child) for child in node.get("children", []))
    return ""


def find_nodes_by_tag(node, tag: str) -> list[dict]:
    """Recursively find all nodes with the given tag."""
    results = []
    if isinstance(node, dict):
        if node.get("tag") == tag:
            results.append(node)
        for child in node.get("children", []):
            results.extend(find_nodes_by_tag(child, tag))
    elif isinstance(node, list):
        for item in node:
            results.extend(find_nodes_by_tag(item, tag))
    return results


def get_child_by_tag(node: dict, tag: str):
    """Get the first child with the given tag."""
    for child in node.get("children", []):
        if isinstance(child, dict) and child.get("tag") == tag:
            return child
    return None


def extract_article_num(article: dict) -> int | None:
    """Extract article number from Article node attributes."""
    num_str = article.get("attr", {}).get("Num", "")
    if not num_str:
        return None
    # Handle compound numbers like "15_2" -> 15
    try:
        return int(num_str.split("_")[0])
    except (ValueError, IndexError):
        return None


def extract_article_caption(article: dict) -> str:
    """Extract ArticleCaption text (e.g. '（目的）')."""
    caption = get_child_by_tag(article, "ArticleCaption")
    if caption:
        text = extract_text_recursive(caption).strip()
        # Remove surrounding parentheses for review_point use
        return text.strip("（）()")
    return ""


def extract_article_title(article: dict) -> str:
    """Extract ArticleTitle text (e.g. '第一条')."""
    title = get_child_by_tag(article, "ArticleTitle")
    if title:
        return extract_text_recursive(title).strip()
    return ""


def extract_article_body(article: dict) -> str:
    """Extract all paragraph text from an article."""
    paragraphs = find_nodes_by_tag(article, "Paragraph")
    parts = []
    for para in paragraphs:
        para_num_node = get_child_by_tag(para, "ParagraphNum")
        para_num = extract_text_recursive(para_num_node).strip() if para_num_node else ""

        para_sentence = get_child_by_tag(para, "ParagraphSentence")
        sentence_text = extract_text_recursive(para_sentence).strip() if para_sentence else ""

        # Also extract Items within the paragraph
        items = find_nodes_by_tag(para, "Item")
        item_texts = []
        for item in items:
            item_title = get_child_by_tag(item, "ItemTitle")
            item_sentence = get_child_by_tag(item, "ItemSentence")
            t = extract_text_recursive(item_title).strip() if item_title else ""
            s = extract_text_recursive(item_sentence).strip() if item_sentence else ""
            if t or s:
                item_texts.append(f"{t} {s}".strip())

        line = ""
        if para_num:
            line = f"{para_num} {sentence_text}"
        else:
            line = sentence_text

        if item_texts:
            line += "\n" + "\n".join(item_texts)

        if line.strip():
            parts.append(line.strip())

    return "\n".join(parts)


def make_review_point(law_name: str, article_title: str, caption: str) -> str:
    """Generate a review_point string from article metadata."""
    if caption:
        return f"{law_name}{article_title}に基づき{caption}に関する条項を確認する"
    return f"{law_name}{article_title}の規定に照らし契約条項を確認する"


def process_law(law_data: dict, short_name: str, category: str,
                article_filter: set[int] | None) -> list[dict]:
    """Extract articles from a law's JSON data."""
    law_full_text = law_data.get("law_full_text", {})

    # Get the law title from revision_info
    law_title = law_data.get("revision_info", {}).get("law_title", category)

    # Find all Article nodes
    articles = find_nodes_by_tag(law_full_text, "Article")
    logger.info("  Found %d articles in %s", len(articles), law_title)

    docs = []
    for article in articles:
        num = extract_article_num(article)
        if num is None:
            continue
        if article_filter is not None and num not in article_filter:
            continue

        caption = extract_article_caption(article)
        article_title = extract_article_title(article)
        body = extract_article_body(article)

        if not body.strip():
            continue

        # Build document in legal_knowledge.json format
        doc_id = f"egov_{short_name}_{num}"
        title_str = f"{law_title}{article_title}"
        if caption:
            title_str += f" — {caption}"

        docs.append({
            "id": doc_id,
            "category": category,
            "title": title_str,
            "content": body,
            "review_point": make_review_point(law_title, article_title, caption),
        })

    return docs


def main():
    all_docs: list[dict] = []
    seen_ids: set[str] = set()

    # Group by law_id to avoid duplicate API calls
    law_cache: dict[str, dict] = {}

    for law_id, short_name, category, article_filter in TARGET_LAWS:
        if law_id not in law_cache:
            law_cache[law_id] = fetch_law_data(law_id)
            time.sleep(REQUEST_DELAY)

        docs = process_law(law_cache[law_id], short_name, category, article_filter)

        # Deduplicate (same article from same law but different category)
        for doc in docs:
            if doc["id"] not in seen_ids:
                seen_ids.add(doc["id"])
                all_docs.append(doc)
            else:
                # Same article appears in multiple category filters (e.g. Civil Code)
                # Keep the first one but log
                logger.debug("Skipping duplicate %s", doc["id"])

    # Sort by id for stable output
    all_docs.sort(key=lambda d: d["id"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)

    logger.info("Wrote %d documents to %s", len(all_docs), OUTPUT_PATH)


if __name__ == "__main__":
    main()

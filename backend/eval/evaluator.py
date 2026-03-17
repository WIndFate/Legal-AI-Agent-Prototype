import json
from pathlib import Path

from backend.rag.store import get_store


def _recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Calculate Recall@K: ratio of relevant docs found in top-K results."""
    retrieved_top_k = set(retrieved_ids[:k])
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    return len(retrieved_top_k & relevant) / len(relevant)


def _reciprocal_rank(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """Calculate Reciprocal Rank: 1/rank of the first relevant result."""
    relevant = set(relevant_ids)
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def run_rag_eval(k: int = 3) -> dict:
    """Run RAG evaluation against the eval dataset.

    Returns a report with Recall@K and MRR metrics.
    """
    data_path = Path(__file__).parent.parent / "data" / "eval_dataset.json"
    with open(data_path, "r", encoding="utf-8") as f:
        eval_dataset = json.load(f)

    store = get_store()
    results = []

    for sample in eval_dataset:
        search_results = store.search(sample["query"], n_results=k)
        retrieved_ids = [r["id"] for r in search_results]

        recall = _recall_at_k(retrieved_ids, sample["relevant_ids"], k)
        rr = _reciprocal_rank(retrieved_ids, sample["relevant_ids"])

        results.append({
            "id": sample["id"],
            "description": sample["description"],
            "recall_at_k": recall,
            "reciprocal_rank": rr,
            "retrieved_ids": retrieved_ids,
            "relevant_ids": sample["relevant_ids"],
        })

    mean_recall = sum(r["recall_at_k"] for r in results) / len(results)
    mrr = sum(r["reciprocal_rank"] for r in results) / len(results)

    return {
        "k": k,
        "num_samples": len(results),
        "mean_recall_at_k": round(mean_recall, 3),
        "mrr": round(mrr, 3),
        "per_sample": results,
    }

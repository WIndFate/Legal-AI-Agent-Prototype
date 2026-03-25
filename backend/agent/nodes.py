import json
import logging
import queue as _queue

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

from backend.agent.state import AgentState
from backend.agent.tools import analyze_clause_risk, generate_suggestion
from backend.config import get_settings
from backend.services.costing import log_model_usage

settings = get_settings()
analysis_model = settings.ANALYSIS_MODEL
parse_model = settings.PARSE_MODEL
translation_model = settings.TRANSLATION_MODEL

analysis_llm = ChatOpenAI(model=analysis_model, temperature=0, streaming=True)
parse_llm = ChatOpenAI(model=parse_model, temperature=0)

SYSTEM_PROMPT = """あなたは日本法に精通した法律AI契約審査アシスタントです。
与えられた契約書を専門的に審査し、リスクのある条項を特定し、修正案を提案します。
必ず日本語で回答してください。分析は具体的かつ実務的な観点で行ってください。"""

CLAUSE_ANALYSIS_PROMPT = """あなたは日本法に精通した契約審査AIです。
与えられた1つの契約条項だけを分析してください。

必ず以下を守ってください:
- 出力はJSONオブジェクトのみ
- risk_level は「高」「中」「低」のいずれか
- risk_reason は簡潔だが具体的に書く
- referenced_law には根拠として参照した日本の法律名・条文番号を日本語原文のまま書く
- suggestion はまだ生成しない

出力形式:
{"clause_number":"第X条","risk_level":"高/中/低","risk_reason":"理由","referenced_law":"参照法令"}"""


def parse_contract(state: AgentState) -> dict:
    """Parse contract text into individual clauses using LLM."""
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"""以下の契約書を個別の条項に分割してください。
各条項について、条項番号、タイトル、本文を抽出してください。

JSON配列形式で出力してください:
[{{"number": "第1条", "title": "条項タイトル", "text": "条項本文"}}]

契約書:
{state["contract_text"]}"""),
    ]
    response = parse_llm.invoke(messages)
    log_model_usage("parse_contract", parse_model, response)

    try:
        content = response.content.strip()
        # Extract JSON from markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        clauses = json.loads(content)
    except (json.JSONDecodeError, IndexError):
        clauses = [{"number": "全文", "title": "契約書全文", "text": state["contract_text"]}]

    return {"clauses": clauses, "messages": [response]}


def _extract_json_payload(content: str) -> dict:
    stripped = content.strip()
    if "```json" in stripped:
        stripped = stripped.split("```json")[1].split("```")[0].strip()
    elif "```" in stripped:
        stripped = stripped.split("```")[1].split("```")[0].strip()
    return json.loads(stripped)


def _fallback_clause_analysis(clause: dict) -> dict:
    return {
        "clause_number": clause.get("number", "全文"),
        "risk_level": "不明",
        "risk_reason": "分析に失敗しました",
        "suggestion": "",
        "referenced_law": "",
    }


def _analyze_single_clause(clause: dict, event_queue: _queue.Queue | None = None) -> dict:
    clause_text = clause.get("text", "")
    clause_number = clause.get("number", "全文")
    clause_title = clause.get("title", "")

    if event_queue:
        event_queue.put({"type": "tool_call", "tool": "analyze_clause_risk", "clause": clause_text[:40]})
    legal_knowledge = analyze_clause_risk.invoke({"clause_text": clause_text})
    if event_queue:
        event_queue.put({"type": "tool_result", "tool": "analyze_clause_risk", "clause": clause_text[:40]})

    response = analysis_llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=CLAUSE_ANALYSIS_PROMPT),
        HumanMessage(content=(
            f"条項番号: {clause_number}\n"
            f"条項タイトル: {clause_title}\n"
            f"条項本文:\n{clause_text}\n\n"
            f"関連法律知識:\n{legal_knowledge}"
        )),
    ])
    log_model_usage(
        "analyze_clause",
        analysis_model,
        response,
        clause_number=clause_number,
    )

    try:
        analysis = _extract_json_payload(str(response.content))
    except (json.JSONDecodeError, IndexError, TypeError):
        return _fallback_clause_analysis(clause)

    risk_level = analysis.get("risk_level", "不明")
    risk_reason = analysis.get("risk_reason", "")
    suggestion = ""

    if risk_level in {"高", "中"} and risk_reason:
        if event_queue:
            event_queue.put({"type": "tool_call", "tool": "generate_suggestion", "clause": clause_text[:40]})
        suggestion = generate_suggestion.invoke({
            "clause_text": clause_text,
            "risk_reason": risk_reason,
            "risk_level": risk_level,
        })
        if event_queue:
            event_queue.put({"type": "tool_result", "tool": "generate_suggestion", "clause": clause_text[:40]})

    return {
        "clause_number": analysis.get("clause_number") or clause_number,
        "risk_level": risk_level,
        "risk_reason": risk_reason or "分析結果が不十分でした",
        "suggestion": suggestion,
        "referenced_law": analysis.get("referenced_law", ""),
    }


def analyze_risks(state: AgentState) -> dict:
    """Analyze clauses one by one to avoid multi-round prompt growth."""
    clauses = state["clauses"]
    risk_analysis = [_analyze_single_clause(clause) for clause in clauses]
    return {"risk_analysis": risk_analysis, "messages": []}


llm_translator = ChatOpenAI(model=translation_model, temperature=0)


def generate_report(state: AgentState) -> dict:
    """Generate the final structured review report, translated if target_language != 'ja'."""
    risk_analysis = state["risk_analysis"]
    clauses = state.get("clauses", [])
    target_lang = state.get("target_language", "ja")

    high_risks = [r for r in risk_analysis if r.get("risk_level") == "高"]
    medium_risks = [r for r in risk_analysis if r.get("risk_level") == "中"]
    low_risks = [r for r in risk_analysis if r.get("risk_level") == "低"]

    if high_risks:
        overall_risk = "高"
    elif medium_risks:
        overall_risk = "中"
    else:
        overall_risk = "低"

    summary = (
        f"契約書の審査が完了しました。全{len(risk_analysis)}条項中、"
        f"高リスク{len(high_risks)}件、中リスク{len(medium_risks)}件、"
        f"低リスク{len(low_risks)}件が検出されました。"
    )

    # Translate report if target language is not Japanese
    if target_lang != "ja":
        summary, risk_analysis, overall_risk = _translate_report(
            summary, risk_analysis, overall_risk, target_lang
        )

    clause_text_by_number = {
        clause.get("number", ""): clause.get("text", "")
        for clause in clauses
    }
    risk_analysis_with_originals = [
        {
            **analysis,
            "original_text": clause_text_by_number.get(analysis.get("clause_number", ""), ""),
        }
        for analysis in risk_analysis
    ]

    report = {
        "overall_risk_level": overall_risk,
        "summary": summary,
        "clause_analyses": risk_analysis_with_originals,
        "high_risk_count": len(high_risks),
        "medium_risk_count": len(medium_risks),
        "low_risk_count": len(low_risks),
        "total_clauses": len(risk_analysis_with_originals),
    }

    return {"review_report": report}


def _translate_report(
    summary: str,
    risk_analysis: list[dict],
    overall_risk: str,
    target_lang: str,
) -> tuple[str, list[dict], str]:
    """Translate report content to target language using GPT-4o-mini."""
    # Build translation payload
    translate_payload = json.dumps({
        "summary": summary,
        "overall_risk": overall_risk,
        "clauses": [
            {
                "clause_number": r.get("clause_number", ""),
                "risk_level": r.get("risk_level", ""),
                "risk_reason": r.get("risk_reason", ""),
                "suggestion": r.get("suggestion", ""),
                "referenced_law": r.get("referenced_law", ""),
            }
            for r in risk_analysis
        ],
    }, ensure_ascii=False)

    lang_names = {
        "en": "English", "zh-CN": "Simplified Chinese", "zh-TW": "Traditional Chinese",
        "ko": "Korean", "vi": "Vietnamese", "pt-BR": "Brazilian Portuguese",
        "id": "Indonesian", "ne": "Nepali",
    }
    lang_name = lang_names.get(target_lang, target_lang)

    response = llm_translator.invoke([
        SystemMessage(content=(
            f"Translate the following JSON content to {lang_name}. "
            "Translate all text values (summary, risk_level, risk_reason, suggestion, overall_risk). "
            "Keep clause_number as-is (e.g. 第1条). "
            "Keep referenced_law in its original Japanese text — do NOT translate law names or article numbers. "
            "Keep JSON structure exactly the same. "
            "Output only valid JSON, no markdown."
        )),
        HumanMessage(content=translate_payload),
    ])
    log_model_usage("translate_report", translation_model, response, target_language=target_lang)

    try:
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        translated = json.loads(content)
        return (
            translated.get("summary", summary),
            translated.get("clauses", risk_analysis),
            translated.get("overall_risk", overall_risk),
        )
    except (json.JSONDecodeError, KeyError):
        logger.warning(
            "Translation to %s failed, falling back to Japanese. Response: %s",
            target_lang, response.content[:200],
        )
        return summary, risk_analysis, overall_risk


def analyze_risks_streaming(state: AgentState, event_queue: _queue.Queue) -> dict:
    """Same as analyze_risks but emits per-clause progress events."""
    clauses = state["clauses"]
    risk_analysis = []
    for clause in clauses:
        event_queue.put({"type": "thinking"})
        risk_analysis.append(_analyze_single_clause(clause, event_queue=event_queue))
    return {"risk_analysis": risk_analysis, "messages": []}

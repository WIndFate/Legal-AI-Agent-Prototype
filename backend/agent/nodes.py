import json
import logging
import queue as _queue

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

from backend.agent.state import AgentState
from backend.agent.tools import analyze_clause_risk, generate_suggestion, ALL_TOOLS

llm = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True)
llm_with_tools = llm.bind_tools(ALL_TOOLS)

SYSTEM_PROMPT = """あなたは日本法に精通した法律AI契約審査アシスタントです。
与えられた契約書を専門的に審査し、リスクのある条項を特定し、修正案を提案します。
必ず日本語で回答してください。分析は具体的かつ実務的な観点で行ってください。"""


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
    response = llm.invoke(messages)

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


def analyze_risks(state: AgentState) -> dict:
    """Analyze risks for each clause using real LLM tool calling (2-3 rounds)."""
    clauses = state["clauses"]

    clauses_list = []
    for clause in clauses:
        clauses_list.append(
            f"【{clause['number']} {clause['title']}】\n"
            f"条項本文: {clause['text']}"
        )

    analysis_prompt = f"""以下の各契約条項を分析してください。

まず、各条項について analyze_clause_risk ツールを呼び出してください。
ツールが返す法律知識に基づいてリスクレベルを判定してください。
その後、リスクが高または中の条項については generate_suggestion ツールで修正案を生成してください。
generate_suggestion ツールが返したテキストをそのまま suggestion フィールドに使用してください。自分で修正案を考えないでください。

最終的に、全条項のリスク評価を以下のJSON配列形式で出力してください:
[{{"clause_number": "第X条", "risk_level": "高/中/低", "risk_reason": "理由", "suggestion": "generate_suggestionツールの返り値をそのまま使用、低リスクは空文字", "referenced_law": "参照した日本の法律名・条文番号（日本語原文のまま記載）"}}]

条項一覧:
{chr(10).join(clauses_list)}"""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=analysis_prompt),
    ]

    tool_map = {
        "analyze_clause_risk": analyze_clause_risk,
        "generate_suggestion": generate_suggestion,
    }

    # Agentic loop: keep calling tools until LLM returns a final text response
    final_content = ""
    for _ in range(5):  # max 5 rounds to avoid infinite loops
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            final_content = response.content
            break

        # Execute all tool calls returned in this round
        for tool_call in response.tool_calls:
            tool_fn = tool_map.get(tool_call["name"])
            if tool_fn:
                result = tool_fn.invoke(tool_call["args"])
            else:
                result = f"Unknown tool: {tool_call['name']}"
            messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))

    try:
        content = final_content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        risk_analysis = json.loads(content)
    except (json.JSONDecodeError, IndexError):
        risk_analysis = [
            {
                "clause_number": c["number"],
                "risk_level": "不明",
                "risk_reason": "分析に失敗しました",
                "suggestion": "",
                "referenced_law": "",
            }
            for c in clauses
        ]

    return {"risk_analysis": risk_analysis, "messages": messages[2:]}


llm_translator = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def generate_report(state: AgentState) -> dict:
    """Generate the final structured review report, translated if target_language != 'ja'."""
    risk_analysis = state["risk_analysis"]
    clauses = state["clauses"]
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
    """Same as analyze_risks but emits tool_call/tool_result events to event_queue."""
    clauses = state["clauses"]

    clauses_list = []
    for clause in clauses:
        clauses_list.append(
            f"【{clause['number']} {clause['title']}】\n"
            f"条項本文: {clause['text']}"
        )

    analysis_prompt = f"""以下の各契約条項を分析してください。

まず、各条項について analyze_clause_risk ツールを呼び出してください。
ツールが返す法律知識に基づいてリスクレベルを判定してください。
その後、リスクが高または中の条項については generate_suggestion ツールで修正案を生成してください。
generate_suggestion ツールが返したテキストをそのまま suggestion フィールドに使用してください。自分で修正案を考えないでください。

最終的に、全条項のリスク評価を以下のJSON配列形式で出力してください:
[{{"clause_number": "第X条", "risk_level": "高/中/低", "risk_reason": "理由", "suggestion": "generate_suggestionツールの返り値をそのまま使用、低リスクは空文字", "referenced_law": "参照した日本の法律名・条文番号（日本語原文のまま記載）"}}]

条項一覧:
{chr(10).join(clauses_list)}"""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=analysis_prompt),
    ]

    tool_map = {
        "analyze_clause_risk": analyze_clause_risk,
        "generate_suggestion": generate_suggestion,
    }

    final_content = ""
    for _ in range(5):
        event_queue.put({"type": "thinking"})
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            final_content = response.content
            break

        for tool_call in response.tool_calls:
            clause_hint = ""
            if "clause_text" in tool_call["args"]:
                clause_hint = tool_call["args"]["clause_text"][:40]

            event_queue.put({
                "type": "tool_call",
                "tool": tool_call["name"],
                "clause": clause_hint,
            })

            tool_fn = tool_map.get(tool_call["name"])
            result = tool_fn.invoke(tool_call["args"]) if tool_fn else f"Unknown tool: {tool_call['name']}"

            event_queue.put({
                "type": "tool_result",
                "tool": tool_call["name"],
                "clause": clause_hint,
            })
            messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))

    try:
        content = final_content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        risk_analysis = json.loads(content)
    except (json.JSONDecodeError, IndexError):
        risk_analysis = [
            {
                "clause_number": c["number"],
                "risk_level": "不明",
                "risk_reason": "分析に失敗しました",
                "suggestion": "",
                "referenced_law": "",
            }
            for c in clauses
        ]

    return {"risk_analysis": risk_analysis, "messages": messages[2:]}

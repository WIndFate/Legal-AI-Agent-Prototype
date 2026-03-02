import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.agent.state import AgentState
from backend.agent.tools import search_legal_knowledge, ALL_TOOLS

llm = ChatOpenAI(model="gpt-4o", temperature=0)
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


def retrieve_knowledge(state: AgentState) -> dict:
    """Retrieve relevant legal knowledge for each clause via RAG."""
    rag_results = []
    for clause in state["clauses"]:
        query = f"{clause['title']} {clause['text'][:200]}"
        result_text = search_legal_knowledge.invoke({"query": query})
        rag_results.append({
            "clause_number": clause["number"],
            "knowledge": result_text,
        })
    return {"rag_results": rag_results}


def analyze_risks(state: AgentState) -> dict:
    """Analyze risks for each clause using LLM with tool calling."""
    clauses = state["clauses"]
    rag_results = state["rag_results"]

    clauses_with_knowledge = []
    for i, clause in enumerate(clauses):
        knowledge = rag_results[i]["knowledge"] if i < len(rag_results) else ""
        clauses_with_knowledge.append(
            f"【{clause['number']} {clause['title']}】\n"
            f"条項本文: {clause['text']}\n"
            f"関連法律知識:\n{knowledge}"
        )

    analysis_prompt = f"""以下の各契約条項を分析し、リスク評価を行ってください。

各条項について以下を判定してください:
- risk_level: "高" / "中" / "低"
- risk_reason: リスクの具体的な理由（リスクが低い場合は簡潔に）
- suggestion: 修正案（リスクが中以上の場合のみ）
- referenced_law: 参照した法律知識

JSON配列形式で出力してください:
[{{"clause_number": "第X条", "risk_level": "高/中/低", "risk_reason": "理由", "suggestion": "修正案または空文字", "referenced_law": "参照法律"}}]

条項一覧:
{chr(10).join(clauses_with_knowledge)}"""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=analysis_prompt),
    ]
    response = llm.invoke(messages)

    try:
        content = response.content.strip()
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

    return {"risk_analysis": risk_analysis, "messages": [response]}


def generate_report(state: AgentState) -> dict:
    """Generate the final structured review report."""
    risk_analysis = state["risk_analysis"]

    high_risks = [r for r in risk_analysis if r.get("risk_level") == "高"]
    medium_risks = [r for r in risk_analysis if r.get("risk_level") == "中"]
    low_risks = [r for r in risk_analysis if r.get("risk_level") == "低"]

    if high_risks:
        overall_risk = "高"
    elif medium_risks:
        overall_risk = "中"
    else:
        overall_risk = "低"

    report = {
        "overall_risk_level": overall_risk,
        "summary": f"契約書の審査が完了しました。全{len(risk_analysis)}条項中、"
                   f"高リスク{len(high_risks)}件、中リスク{len(medium_risks)}件、"
                   f"低リスク{len(low_risks)}件が検出されました。",
        "clause_analyses": risk_analysis,
        "high_risk_count": len(high_risks),
        "medium_risk_count": len(medium_risks),
        "low_risk_count": len(low_risks),
        "total_clauses": len(risk_analysis),
    }

    return {"review_report": report}


def should_skip_detailed_analysis(state: AgentState) -> str:
    """Conditional edge: skip detailed analysis if no risky clauses found."""
    # After initial risk analysis, check if there are high risks
    risk_analysis = state.get("risk_analysis", [])
    has_high_risk = any(r.get("risk_level") == "高" for r in risk_analysis)
    if has_high_risk:
        return "generate_report"
    return "generate_report"

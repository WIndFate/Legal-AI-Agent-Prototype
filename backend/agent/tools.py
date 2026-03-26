from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from backend.config import get_settings
from backend.rag.store import get_store
from backend.services.costing import log_model_usage

settings = get_settings()
suggestion_model = settings.SUGGESTION_MODEL
RAG_RESULTS_PER_CLAUSE = 2
MAX_KNOWLEDGE_CHARS = 220


def format_rag_results(clause_text: str, results: list[dict]) -> str:
    """Format RAG search results into a knowledge prompt for clause analysis.

    Shared by the @tool (single clause) and the batch path in analyze_risks.
    """
    if not results:
        return (
            f"条項「{clause_text[:30]}...」: "
            "関連法律知識が見つかりませんでした。一般的な契約法原則に基づいてリスクを判定してください。"
        )

    knowledge_parts = []
    for r in results:
        title = r["metadata"].get("title", "参考資料")
        content = r["content"].replace("\n", " ").strip()
        compact_content = content[:MAX_KNOWLEDGE_CHARS]
        if len(content) > MAX_KNOWLEDGE_CHARS:
            compact_content += "..."
        knowledge_parts.append(
            f"【{title}】\n"
            f"要点: {compact_content}\n"
            "審査メモ: この根拠が条項の不利益性、一方的不均衡、説明不足の有無にどう関係するかを判定してください。"
        )

    return (
        f"条項「{clause_text[:30]}...」に関連する法律知識:\n\n"
        + "\n\n---\n\n".join(knowledge_parts)
        + "\n\n上記に基づきリスクレベルと理由を判定してください。"
    )


@tool
def analyze_clause_risk(clause_text: str) -> str:
    """Analyze the risk level of a single contract clause by searching
    relevant Japanese legal knowledge from the RAG knowledge base internally.

    Args:
        clause_text: The text of the contract clause to analyze.
    """
    store = get_store()
    results = store.search(clause_text[:300], n_results=RAG_RESULTS_PER_CLAUSE)
    return format_rag_results(clause_text, results)


@tool
def generate_suggestion(clause_text: str, risk_reason: str, risk_level: str = "中") -> str:
    """Generate a concrete modification suggestion for a risky contract clause
    by calling a dedicated LLM internally.

    Args:
        clause_text: The original clause text that has identified risks.
        risk_reason: The reason why this clause is considered risky.
        risk_level: Risk level ("高" or "中") used to control suggestion detail.
    """
    suggestion_style = (
        "修正案は2〜3文で、交渉や修正文案としてそのまま使える具体的な提案にしてください。"
        if risk_level == "高"
        else "修正案は1文または短い2文までに抑え、最低限の是正ポイントだけを簡潔に示してください。"
    )
    llm = ChatOpenAI(model=suggestion_model, temperature=0)
    response = llm.invoke([
        SystemMessage(content="あなたは日本法に精通した法律専門家です。リスクのある契約条項に対して、具体的かつ実務的な修正案を提案してください。"),
        HumanMessage(content=f"""以下のリスクある契約条項に対して、具体的な修正案を生成してください。

条項本文:
{clause_text}

リスクの理由:
{risk_reason}

リスクレベル:
{risk_level}

出力スタイル:
{suggestion_style}

修正案のみを出力してください。前置きや説明は不要です。"""),
    ])
    log_model_usage("generate_suggestion", suggestion_model, response, risk_level=risk_level)
    return response.content


ALL_TOOLS = [analyze_clause_risk, generate_suggestion]

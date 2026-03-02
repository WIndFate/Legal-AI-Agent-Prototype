from langchain_core.tools import tool

from backend.rag.store import get_store


@tool
def search_legal_knowledge(query: str) -> str:
    """Search relevant Japanese legal knowledge from the RAG knowledge base.

    Args:
        query: The search query text, typically a contract clause or legal concept.
    """
    store = get_store()
    results = store.search(query, n_results=3)
    if not results:
        return "関連する法律知識が見つかりませんでした。"

    output_parts = []
    for r in results:
        output_parts.append(
            f"【{r['metadata']['title']}】\n{r['content']}"
        )
    return "\n\n---\n\n".join(output_parts)


@tool
def analyze_clause_risk(clause_text: str, legal_context: str) -> str:
    """Analyze the risk level of a single contract clause.

    Args:
        clause_text: The text of the contract clause to analyze.
        legal_context: Relevant legal knowledge retrieved from RAG.
    """
    # This tool is invoked by the LLM via tool calling.
    # The actual analysis is done by the LLM in the analyze_risks node,
    # so this serves as a structured input/output interface.
    return (
        f"条項分析対象:\n{clause_text}\n\n"
        f"参照法律知識:\n{legal_context}\n\n"
        "上記の情報に基づいてリスク分析を実行してください。"
    )


@tool
def generate_suggestion(clause_text: str, risk_reason: str) -> str:
    """Generate a modification suggestion for a risky contract clause.

    Args:
        clause_text: The original clause text that has identified risks.
        risk_reason: The reason why this clause is considered risky.
    """
    return (
        f"修正対象条項:\n{clause_text}\n\n"
        f"リスク理由:\n{risk_reason}\n\n"
        "上記に基づいて具体的な修正案を生成してください。"
    )


ALL_TOOLS = [search_legal_knowledge, analyze_clause_risk, generate_suggestion]

from langgraph.graph import StateGraph, END

from backend.agent.state import AgentState
from backend.agent.nodes import (
    parse_contract,
    retrieve_knowledge,
    analyze_risks,
    generate_report,
)


def build_graph() -> StateGraph:
    """Build the LangGraph workflow for contract review."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("parse_contract", parse_contract)
    workflow.add_node("retrieve_knowledge", retrieve_knowledge)
    workflow.add_node("analyze_risks", analyze_risks)
    workflow.add_node("generate_report", generate_report)

    # Define edges: linear pipeline
    workflow.set_entry_point("parse_contract")
    workflow.add_edge("parse_contract", "retrieve_knowledge")
    workflow.add_edge("retrieve_knowledge", "analyze_risks")
    workflow.add_edge("analyze_risks", "generate_report")
    workflow.add_edge("generate_report", END)

    return workflow.compile()


# Compiled graph instance
review_agent = build_graph()


async def run_review(contract_text: str) -> dict:
    """Run the contract review agent and return the report."""
    initial_state = {
        "contract_text": contract_text,
        "clauses": [],
        "current_clause_index": 0,
        "rag_results": [],
        "risk_analysis": [],
        "review_report": {},
        "messages": [],
    }
    result = await review_agent.ainvoke(initial_state)
    return result["review_report"]

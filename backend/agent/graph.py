from langgraph.graph import StateGraph, END

from backend.agent.state import AgentState
from backend.agent.nodes import (
    parse_contract,
    analyze_risks,
    generate_report,
)


def build_graph() -> StateGraph:
    """Build the LangGraph workflow for contract review."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("parse_contract", parse_contract)
    workflow.add_node("analyze_risks", analyze_risks)
    workflow.add_node("generate_report", generate_report)

    # Define edges: linear pipeline
    workflow.set_entry_point("parse_contract")
    workflow.add_edge("parse_contract", "analyze_risks")
    workflow.add_edge("analyze_risks", "generate_report")
    workflow.add_edge("generate_report", END)

    return workflow.compile()


# Compiled graph instance
review_agent = build_graph()


async def run_review(contract_text: str, target_language: str = "ja") -> dict:
    """Run the contract review agent and return the report."""
    initial_state = {
        "contract_text": contract_text,
        "clauses": [],
        "risk_analysis": [],
        "review_report": {},
        "messages": [],
        "target_language": target_language,
    }
    result = await review_agent.ainvoke(initial_state)
    return result["review_report"]


async def run_review_stream(contract_text: str, target_language: str = "ja"):
    """Yield SSE-ready dicts using LangGraph astream_events."""
    initial_state = {
        "contract_text": contract_text,
        "clauses": [],
        "risk_analysis": [],
        "review_report": {},
        "messages": [],
        "target_language": target_language,
    }

    NODE_LABELS = {
        "parse_contract":  "契約書を解析しています...",
        "analyze_risks":   "AIが自律的にリスク分析を実行しています...",
        "generate_report": "最終レポートを生成しています...",
    }

    # State for tracking per-clause progress during analyze_risks.
    # Each clause triggers exactly one analysis_llm.invoke() OUTSIDE any tool,
    # while generate_suggestion (for high/medium risk) fires INSIDE a tool.
    # We count on_chat_model_end events that happen outside tools during
    # the analyzing phase to derive clause-level progress.
    current_phase = None
    in_tool = False
    clause_analyzed_count = 0

    async for event in review_agent.astream_events(initial_state, version="v2"):
        kind = event["event"]
        name = event.get("name", "")

        # Node start → progress step
        if kind == "on_chain_start" and name in NODE_LABELS:
            current_phase = name
            if name == "analyze_risks":
                clause_analyzed_count = 0
            yield {"type": "node_start", "node": name, "label": NODE_LABELS[name]}

        # Parse complete → emit clause count for frontend progress
        elif kind == "on_chain_end" and name == "parse_contract":
            output = event["data"].get("output", {})
            clauses = output.get("clauses", [])
            yield {"type": "node_end", "node": "parse_contract", "total_clauses": len(clauses)}

        # Graph end → send final report
        elif kind == "on_chain_end" and name == "LangGraph":
            output = event["data"].get("output", {})
            if "review_report" in output:
                yield {"type": "complete", "report": output["review_report"]}

        # LLM token stream → send text chunks
        elif kind == "on_chat_model_stream":
            chunk = event["data"].get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                yield {"type": "token", "text": chunk.content}

        # Clause analysis LLM completed (outside any tool) → clause progress
        elif kind == "on_chat_model_end" and current_phase == "analyze_risks" and not in_tool:
            clause_analyzed_count += 1
            yield {"type": "clause_progress", "analyzed": clause_analyzed_count}

        # Tool call → show agent decision
        elif kind == "on_tool_start" and name in ("analyze_clause_risk", "generate_suggestion"):
            in_tool = True
            args = event["data"].get("input", {})
            clause_hint = args.get("clause_text", "")[:30]
            yield {"type": "tool_call", "tool": name, "clause": clause_hint}

        # Tool result → surface compact completion events to the frontend
        elif kind == "on_tool_end" and name in ("analyze_clause_risk", "generate_suggestion"):
            in_tool = False
            output = event["data"].get("output", "")
            yield {"type": "tool_result", "tool": name, "result_preview": str(output)[:80]}

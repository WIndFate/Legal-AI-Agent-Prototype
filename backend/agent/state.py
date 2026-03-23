from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    contract_text: str
    clauses: list[dict]
    risk_analysis: list[dict]
    review_report: dict
    messages: Annotated[list[BaseMessage], add_messages]
    target_language: str  # ISO language code, e.g. "ja", "zh-CN", "en"

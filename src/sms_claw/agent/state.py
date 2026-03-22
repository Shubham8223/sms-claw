"""LangGraph agent state."""
from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    phone: str
    session_id: str
    user_prefs: dict[str, Any]
    short_term: list[str]
    final_response: str
    error: str | None

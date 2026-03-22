"""
LangGraph ReAct agent graph.

Nodes
-----
load_context   Pull working memory + short/long-term context, build system msg.
call_llm       Invoke LLM with tools bound; produces tool calls or final answer.
run_tools      Execute every tool call the LLM requested.
format_reply   Trim final answer to SMS-safe length.
save_memory    Persist turn to Postgres + refresh Redis working memory.

Edges
-----
load_context → call_llm
call_llm     → run_tools      (tool_calls present)
call_llm     → format_reply   (no tool_calls — final answer)
run_tools    → call_llm       (loop back with results)
format_reply → save_memory → END
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import partial
from typing import Any

import redis.asyncio as aioredis
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from sms_claw.agent.llm_factory import build_llm
from sms_claw.agent.prompts import ERROR_MESSAGE, SYSTEM_PROMPT
from sms_claw.agent.state import AgentState
from sms_claw.core.constants import MAX_TOOL_ITERATIONS, SMS_MAX_REPLY_CHARS
from sms_claw.core.exceptions import LLMError
from sms_claw.core.logging import get_logger
from sms_claw.memory.long_term import LongTermMemory
from sms_claw.memory.short_term import ShortTermMemory
from sms_claw.memory.working import WorkingMemory
from sms_claw.tools.memory_tool import make_memory_tool
from sms_claw.tools.registry import get_all_tools

log = get_logger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _all_tools(phone: str, ltm: LongTermMemory) -> list[Any]:
    return get_all_tools() + [make_memory_tool(phone, ltm)]


def _tool_map(phone: str, ltm: LongTermMemory) -> dict[str, Any]:
    return {t.name: t for t in _all_tools(phone, ltm)}


# ── Node: load_context ─────────────────────────────────────────────────────────


async def _load_context(
    state: AgentState,
    *,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> dict[str, Any]:
    phone = state["phone"]
    session_id = state["session_id"]

    stm = ShortTermMemory(db)
    ltm = LongTermMemory(db)
    wm = WorkingMemory(redis)

    prefs = await ltm.get_preferences(phone)
    summaries = await stm.get_recent_summaries(phone, limit=3)
    history = await wm.load(session_id)

    system_content = SYSTEM_PROMPT.format(
        phone=phone,
        user_prefs=prefs or "none yet",
        short_term="\n".join(summaries) if summaries else "no recent sessions",
        datetime=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )

    messages = (
        [SystemMessage(content=system_content)] + history + state.get("messages", [])
    )

    log.info(
        "context_loaded",
        phone=phone,
        history_len=len(history),
        summaries=len(summaries),
    )
    return {**state, "messages": messages, "user_prefs": prefs, "short_term": summaries}


# ── Node: call_llm ─────────────────────────────────────────────────────────────


async def _call_llm(
    state: AgentState,
    *,
    phone: str,
    db: AsyncSession,
) -> dict[str, Any]:
    ltm = LongTermMemory(db)
    tools = _all_tools(phone, ltm)

    try:
        llm = build_llm().bind_tools(tools)
        response: AIMessage = await llm.ainvoke(state["messages"])
        log.info(
            "llm_responded",
            phone=phone,
            tool_calls=[tc["name"] for tc in (response.tool_calls or [])],
        )
        return {**state, "messages": state["messages"] + [response]}
    except Exception as exc:
        log.error("llm_call_failed", phone=phone, error=str(exc), exc_info=True)
        return {**state, "error": str(exc)}


# ── Node: run_tools ────────────────────────────────────────────────────────────


async def _run_tools(
    state: AgentState,
    *,
    phone: str,
    db: AsyncSession,
) -> dict[str, Any]:
    last: AIMessage = state["messages"][-1]
    if not last.tool_calls:
        return state

    ltm = LongTermMemory(db)
    tmap = _tool_map(phone, ltm)
    results: list[ToolMessage] = []

    for tc in last.tool_calls:
        name, args, tid = tc["name"], tc["args"], tc["id"]
        if name not in tmap:
            content = f"Tool '{name}' is not available."
        else:
            try:
                t = tmap[name]
                content = await t.arun(args) if hasattr(t, "arun") else t.run(args)
                log.info("tool_executed", phone=phone, tool=name)
            except Exception as exc:
                log.error(
                    "tool_execution_error",
                    phone=phone,
                    tool=name,
                    error=str(exc),
                    exc_info=True,
                )
                content = f"Tool '{name}' failed: {exc}"
        results.append(ToolMessage(content=str(content), tool_call_id=tid))

    return {**state, "messages": state["messages"] + results}


# ── Node: format_reply ─────────────────────────────────────────────────────────


async def _format_reply(state: AgentState) -> dict[str, Any]:
    if state.get("error"):
        return {**state, "final_response": ERROR_MESSAGE}

    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            text = msg.content if isinstance(msg.content, str) else str(msg.content)
            if len(text) > SMS_MAX_REPLY_CHARS:
                text = (
                    text[: SMS_MAX_REPLY_CHARS - 20].rsplit(" ", 1)[0]
                    + "… (reply MORE)"
                )
            return {**state, "final_response": text}

    return {**state, "final_response": ERROR_MESSAGE}


# ── Node: save_memory ──────────────────────────────────────────────────────────


async def _save_memory(
    state: AgentState,
    *,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> dict[str, Any]:
    import uuid

    phone = state["phone"]
    session_id = state["session_id"]

    stm = ShortTermMemory(db)
    wm = WorkingMemory(redis)

    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            await stm.log_message(uuid.UUID(session_id), "user", str(msg.content))
        elif isinstance(msg, AIMessage) and not msg.tool_calls:
            await stm.log_message(
                uuid.UUID(session_id),
                "assistant",
                str(msg.content),
                tool_calls=msg.additional_kwargs.get("tool_calls"),
            )

    # Persist history (strip system message to save space)
    history = [m for m in state["messages"] if not isinstance(m, SystemMessage)]
    await wm.save(session_id, history)

    log.info("memory_saved", phone=phone, session_id=session_id)
    return state


# ── Routing ────────────────────────────────────────────────────────────────────


def _router(state: AgentState) -> str:
    if state.get("error"):
        return "format_reply"
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        # Guard against infinite tool loops
        tool_msgs = sum(1 for m in state["messages"] if isinstance(m, ToolMessage))
        if tool_msgs >= MAX_TOOL_ITERATIONS:
            log.warning("max_tool_iterations_reached", count=tool_msgs)
            return "format_reply"
        return "run_tools"
    return "format_reply"


# ── Graph factory ──────────────────────────────────────────────────────────────


def build_graph(phone: str, db: AsyncSession, redis: aioredis.Redis) -> Any:
    """Compile a LangGraph for one request with phone, db, and redis injected."""
    g = StateGraph(AgentState)

    g.add_node("load_context", partial(_load_context, db=db, redis=redis))
    g.add_node("call_llm", partial(_call_llm, phone=phone, db=db))
    g.add_node("run_tools", partial(_run_tools, phone=phone, db=db))
    g.add_node("format_reply", _format_reply)
    g.add_node("save_memory", partial(_save_memory, db=db, redis=redis))

    g.set_entry_point("load_context")
    g.add_edge("load_context", "call_llm")
    g.add_conditional_edges("call_llm", _router)
    g.add_edge("run_tools", "call_llm")
    g.add_edge("format_reply", "save_memory")
    g.add_edge("save_memory", END)

    return g.compile()


async def run_agent(
    phone: str,
    session_id: str,
    user_message: str,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> str:
    """Run one SMS turn through the agent. Returns the formatted reply string."""
    graph = build_graph(phone=phone, db=db, redis=redis)

    initial: AgentState = {
        "messages": [HumanMessage(content=user_message)],
        "phone": phone,
        "session_id": session_id,
        "user_prefs": {},
        "short_term": [],
        "final_response": "",
        "error": None,
    }

    try:
        result = await graph.ainvoke(initial)
        return result.get("final_response", ERROR_MESSAGE)
    except Exception as exc:
        log.error("agent_run_failed", phone=phone, error=str(exc), exc_info=True)
        return ERROR_MESSAGE

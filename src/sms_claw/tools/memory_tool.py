"""Memory tool — agent-callable note to long-term memory. Built per-request."""

from __future__ import annotations

from langchain_core.tools import tool

from sms_claw.core.logging import get_logger
from sms_claw.memory.long_term import LongTermMemory

log = get_logger(__name__)


def make_memory_tool(phone: str, ltm: LongTermMemory):  # type: ignore[no-untyped-def]
    """
    Build a bound memory_note tool for a specific user.
    Called by the agent graph at request time so phone and ltm are closed over.
    """

    @tool
    async def memory_note(content: str, category: str = "general") -> str:
        """
        Save a fact or preference to long-term memory permanently.
        Use when the user shares something important to remember:
        preferences, names, addresses, habits, or recurring tasks.
        category options: preference | fact | contact | task | general
        """
        try:
            await ltm.save(phone=phone, content=content, category=category)
            log.info("memory_note_saved", phone=phone, category=category)
            return f"Remembered: {content}"
        except Exception as exc:
            log.error("memory_note_error", phone=phone, error=str(exc), exc_info=True)
            return f"Could not save to memory: {exc}"

    return memory_note

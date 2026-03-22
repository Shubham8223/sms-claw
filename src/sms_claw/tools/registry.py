"""Tool registry — every tool decorator registers here."""

from __future__ import annotations

from langchain_core.tools import BaseTool

_TOOL_REGISTRY: dict[str, BaseTool] = {}


def register_tool(tool: BaseTool) -> BaseTool:
    """Register a LangChain tool by name. Used as a decorator."""
    _TOOL_REGISTRY[tool.name] = tool
    return tool


def get_all_tools() -> list[BaseTool]:
    """Import all tools (triggers registration) and return the list."""
    from sms_claw.tools import (  # noqa: F401
        email_tool,
        github_tool,
        telegram_tool,
        web_tool,
        whatsapp_tool,
    )

    return list(_TOOL_REGISTRY.values())

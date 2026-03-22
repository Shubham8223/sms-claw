"""
Structured logging with structlog.

- Development : coloured console output with rich tracebacks.
- Production  : JSON lines, exception tracebacks serialised as strings so they
                survive log aggregators (Datadog, CloudWatch, Loki …).

Usage
-----
    from sms_claw.core.logging import get_logger
    log = get_logger(__name__)

    log.info("user_enrolled", phone=phone)
    log.warning("rate_limit", phone=phone, count=count)
    log.error("agent_failed", phone=phone, exc_info=True)   # attaches traceback
"""

from __future__ import annotations

import logging
import sys
import traceback
from typing import Any

import structlog
from rich.console import Console
from rich.logging import RichHandler

_console = Console(stderr=True)

# ── Custom processor: attach full traceback string ────────────────────────────


def _add_traceback(
    logger: Any, method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """
    If exc_info=True (or an exception tuple) is in the event dict,
    format the full traceback into event_dict["traceback"] so it is
    always captured regardless of the renderer.
    """
    exc_info = event_dict.pop("exc_info", False)
    if exc_info:
        if exc_info is True:
            exc_info = sys.exc_info()
        if exc_info[0] is not None:
            event_dict["traceback"] = "".join(
                traceback.format_exception(*exc_info)
            ).strip()
            event_dict["exception_type"] = exc_info[0].__name__
            event_dict["exception_message"] = str(exc_info[1])
    return event_dict


# ── Setup ─────────────────────────────────────────────────────────────────────


def setup_logging(level: str = "INFO", *, production: bool = False) -> None:
    """
    Call once at application startup.

    Parameters
    ----------
    level:      Log level string (DEBUG, INFO, WARNING, ERROR).
    production: If True, emit JSON lines; otherwise rich console.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        _add_traceback,
    ]

    if production:
        handler: logging.Handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        renderer = structlog.processors.JSONRenderer()
    else:
        handler = RichHandler(
            console=_console,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,
        )
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )

    # Configure standard logging first so structlog falls back correctly
    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        handlers=[handler],
        force=True,
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a bound structlog logger for the given module name."""
    return structlog.get_logger(name)

"""LLM provider factory — returns a bound LangChain chat model."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.language_models import BaseChatModel

from sms_claw.core.config import get_settings
from sms_claw.core.exceptions import LLMError
from sms_claw.core.logging import get_logger

log = get_logger(__name__)


def build_llm(
    provider: str | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    s = get_settings()
    _provider = provider or s.default_llm_provider
    _model = model or s.default_llm_model

    log.info("building_llm", provider=_provider, model=_model)

    try:
        if _provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=_model,
                api_key=s.anthropic_api_key,
                max_tokens=1024,
                **kwargs,
            )

        if _provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=_model,
                api_key=s.openai_api_key,
                **kwargs,
            )

        if _provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=_model,
                google_api_key=s.google_api_key,
                **kwargs,
            )

        if _provider == "nvidia":
            from langchain_nvidia_ai_endpoints import ChatNVIDIA

            return ChatNVIDIA(
                model=_model,
                api_key=s.nvidia_api_key,
                base_url=s.nvidia_base_url,
                **kwargs,
            )

    except Exception as exc:
        log.error("llm_build_failed", provider=_provider, error=str(exc), exc_info=True)
        raise LLMError(f"Failed to initialise {_provider} LLM: {exc}") from exc

    raise LLMError(
        f"Unknown LLM provider: '{_provider}'. Supported: anthropic | openai | google | nvidia"
    )


@lru_cache(maxsize=1)
def get_default_llm() -> BaseChatModel:
    return build_llm()

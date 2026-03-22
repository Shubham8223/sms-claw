"""Unit tests — LLM factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sms_claw.core.exceptions import LLMError


def test_build_anthropic():
    with patch("sms_claw.agent.llm_factory.get_settings") as ms:
        ms.return_value.default_llm_provider = "anthropic"
        ms.return_value.default_llm_model = "claude-sonnet-4-20250514"
        ms.return_value.anthropic_api_key = "sk-ant-test"
        with patch(
            "sms_claw.agent.llm_factory.ChatAnthropic", return_value=MagicMock()
        ):
            from sms_claw.agent.llm_factory import build_llm

            llm = build_llm(provider="anthropic")
            assert llm is not None


def test_build_openai():
    with patch("sms_claw.agent.llm_factory.get_settings") as ms:
        ms.return_value.default_llm_provider = "openai"
        ms.return_value.default_llm_model = "gpt-4o"
        ms.return_value.openai_api_key = "sk-test"
        with patch("sms_claw.agent.llm_factory.ChatOpenAI", return_value=MagicMock()):
            from sms_claw.agent.llm_factory import build_llm

            llm = build_llm(provider="openai")
            assert llm is not None


def test_unknown_provider_raises():
    with patch("sms_claw.agent.llm_factory.get_settings") as ms:
        ms.return_value.default_llm_provider = "unknown"
        ms.return_value.default_llm_model = "x"
        from sms_claw.agent.llm_factory import build_llm

        with pytest.raises(LLMError, match="Unknown LLM provider"):
            build_llm(provider="unknown")

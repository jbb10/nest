"""Tests for LLM provider adapter and factory.

Tests the OpenAIAdapter, create_llm_provider() factory,
and protocol compliance.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from nest.adapters.llm_provider import (
    DEFAULT_AZURE_API_VERSION,
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    AzureOpenAIAdapter,
    OpenAIAdapter,
    _is_azure_endpoint,
    create_llm_provider,
)
from nest.adapters.protocols import LLMProviderProtocol
from nest.core.models import LLMCompletionResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(
    content: str | None = "Hello from LLM",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    *,
    empty_choices: bool = False,
    none_usage: bool = False,
) -> MagicMock:
    """Build a mock openai ChatCompletion response."""
    response = MagicMock()

    if empty_choices:
        response.choices = []
        return response

    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response.choices = [choice]

    if none_usage:
        response.usage = None
    else:
        usage = MagicMock()
        usage.prompt_tokens = prompt_tokens
        usage.completion_tokens = completion_tokens
        response.usage = usage

    return response


# ---------------------------------------------------------------------------
# Factory: create_llm_provider()
# ---------------------------------------------------------------------------


class TestCreateLLMProvider:
    """Tests for create_llm_provider() factory function."""

    def test_create_with_nest_ai_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NEST_AI_API_KEY set → returns adapter with correct config."""
        monkeypatch.setenv("NEST_AI_API_KEY", "nest-key-123")
        monkeypatch.setenv("NEST_AI_ENDPOINT", "https://custom.api/v1")
        monkeypatch.setenv("NEST_AI_MODEL", "gpt-4o")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            result = create_llm_provider()

        assert result is not None
        assert result.model_name == "gpt-4o"
        mock_openai.assert_called_once_with(
            api_key="nest-key-123", base_url="https://custom.api/v1"
        )

    def test_create_with_openai_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only OPENAI_API_KEY set → returns adapter."""
        monkeypatch.delenv("NEST_AI_API_KEY", raising=False)
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key-456")
        monkeypatch.setenv("OPENAI_API_BASE", "https://openai.custom/v1")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-3.5-turbo")

        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            result = create_llm_provider()

        assert result is not None
        assert result.model_name == "gpt-3.5-turbo"
        mock_openai.assert_called_once_with(
            api_key="openai-key-456", base_url="https://openai.custom/v1"
        )

    def test_create_no_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No keys → returns None."""
        monkeypatch.delenv("NEST_AI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        result = create_llm_provider()

        assert result is None

    def test_nest_ai_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Both NEST_AI_API_KEY and OPENAI_API_KEY set → uses NEST_AI_API_KEY."""
        monkeypatch.setenv("NEST_AI_API_KEY", "nest-key")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            result = create_llm_provider()

        assert result is not None
        mock_openai.assert_called_once_with(api_key="nest-key", base_url=DEFAULT_ENDPOINT)

    def test_endpoint_fallback_chain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test all three levels: NEST_AI_ENDPOINT → OPENAI_API_BASE → default."""
        monkeypatch.setenv("NEST_AI_API_KEY", "key")
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        # Level 1: NEST_AI_ENDPOINT wins
        monkeypatch.setenv("NEST_AI_ENDPOINT", "https://nest-ep/v1")
        monkeypatch.setenv("OPENAI_API_BASE", "https://openai-ep/v1")
        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            create_llm_provider()
        mock_openai.assert_called_once_with(api_key="key", base_url="https://nest-ep/v1")

        # Level 2: OPENAI_API_BASE fallback
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            create_llm_provider()
        mock_openai.assert_called_once_with(api_key="key", base_url="https://openai-ep/v1")

        # Level 3: default
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)
        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            create_llm_provider()
        mock_openai.assert_called_once_with(api_key="key", base_url=DEFAULT_ENDPOINT)

    def test_model_fallback_chain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test all three levels: NEST_AI_MODEL → OPENAI_MODEL → default."""
        monkeypatch.setenv("NEST_AI_API_KEY", "key")
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)

        # Level 1: NEST_AI_MODEL wins
        monkeypatch.setenv("NEST_AI_MODEL", "custom-model")
        monkeypatch.setenv("OPENAI_MODEL", "openai-model")
        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            result = create_llm_provider()
        assert result is not None
        assert result.model_name == "custom-model"

        # Level 2: OPENAI_MODEL fallback
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            result = create_llm_provider()
        assert result is not None
        assert result.model_name == "openai-model"

        # Level 3: default
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            result = create_llm_provider()
        assert result is not None
        assert result.model_name == DEFAULT_MODEL

    def test_default_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No endpoint vars → https://api.openai.com/v1."""
        monkeypatch.setenv("NEST_AI_API_KEY", "key")
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            create_llm_provider()
        mock_openai.assert_called_once_with(api_key="key", base_url="https://api.openai.com/v1")

    def test_default_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No model vars → gpt-4o-mini."""
        monkeypatch.setenv("NEST_AI_API_KEY", "key")
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            result = create_llm_provider()
        assert result is not None
        assert result.model_name == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# OpenAIAdapter.complete()
# ---------------------------------------------------------------------------


class TestOpenAIAdapterComplete:
    """Tests for OpenAIAdapter.complete() method."""

    def _make_adapter(self) -> OpenAIAdapter:
        """Create an adapter with a mocked client."""
        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            return OpenAIAdapter(
                api_key="test-key",
                endpoint="https://api.test.com/v1",
                model="test-model",
            )

    def test_complete_success(self) -> None:
        """Mock openai client, verify LLMCompletionResult returned."""
        adapter = self._make_adapter()
        mock_response = _make_mock_response(
            content="Generated text", prompt_tokens=15, completion_tokens=8
        )
        adapter._client.chat.completions.create = MagicMock(return_value=mock_response)

        result = adapter.complete("You are helpful.", "Say hello")

        assert result is not None
        assert isinstance(result, LLMCompletionResult)
        assert result.text == "Generated text"
        assert result.prompt_tokens == 15
        assert result.completion_tokens == 8

    def test_complete_api_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Mock openai raising APIError → returns None, logs warning."""
        adapter = self._make_adapter()
        adapter._client.chat.completions.create = MagicMock(side_effect=Exception("API error"))

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = adapter.complete("system", "user")

        assert result is None
        assert "LLM call failed" in caplog.text

    def test_complete_network_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Mock connection error → returns None, logs warning."""
        adapter = self._make_adapter()
        adapter._client.chat.completions.create = MagicMock(
            side_effect=ConnectionError("Network unreachable")
        )

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = adapter.complete("system", "user")

        assert result is None
        assert "LLM call failed" in caplog.text

    def test_complete_timeout(self, caplog: pytest.LogCaptureFixture) -> None:
        """Mock timeout → returns None, logs warning."""
        adapter = self._make_adapter()
        adapter._client.chat.completions.create = MagicMock(
            side_effect=TimeoutError("Request timed out")
        )

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = adapter.complete("system", "user")

        assert result is None
        assert "LLM call failed" in caplog.text

    def test_complete_empty_choices(self, caplog: pytest.LogCaptureFixture) -> None:
        """Response with empty choices → returns None, logs warning."""
        adapter = self._make_adapter()
        mock_response = _make_mock_response(empty_choices=True)
        adapter._client.chat.completions.create = MagicMock(return_value=mock_response)

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = adapter.complete("system", "user")

        assert result is None
        assert "empty choices" in caplog.text

    def test_complete_none_content(self, caplog: pytest.LogCaptureFixture) -> None:
        """Response content is None → returns None, logs warning."""
        adapter = self._make_adapter()
        mock_response = _make_mock_response(content=None)
        adapter._client.chat.completions.create = MagicMock(return_value=mock_response)

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = adapter.complete("system", "user")

        assert result is None
        assert "None content" in caplog.text

    def test_complete_none_usage(self) -> None:
        """Response usage is None → returns result with 0 tokens."""
        adapter = self._make_adapter()
        mock_response = _make_mock_response(none_usage=True)
        adapter._client.chat.completions.create = MagicMock(return_value=mock_response)

        result = adapter.complete("system", "user")

        assert result is not None
        assert result.text == "Hello from LLM"
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Tests for protocol compliance."""

    def test_adapter_satisfies_protocol(self) -> None:
        """isinstance(adapter, LLMProviderProtocol) is True."""
        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            adapter = OpenAIAdapter(
                api_key="key", endpoint="https://api.test.com/v1", model="model"
            )
        assert isinstance(adapter, LLMProviderProtocol)

    def test_azure_adapter_implements_protocol(self) -> None:
        """isinstance(AzureOpenAIAdapter, LLMProviderProtocol) is True."""
        with patch("nest.adapters.llm_provider.openai.AzureOpenAI"):
            adapter = AzureOpenAIAdapter(
                api_key="key",
                endpoint="https://myorg.openai.azure.com",
                deployment="gpt-4o",
                api_version="2024-12-01-preview",
            )
        assert isinstance(adapter, LLMProviderProtocol)


# ---------------------------------------------------------------------------
# Azure endpoint detection
# ---------------------------------------------------------------------------


class TestIsAzureEndpoint:
    """Tests for _is_azure_endpoint() helper."""

    def test_azure_endpoint_detected(self) -> None:
        assert _is_azure_endpoint("https://myorg.openai.azure.com") is True

    def test_azure_endpoint_with_path(self) -> None:
        assert _is_azure_endpoint("https://myorg.openai.azure.com/openai/deployments") is True

    def test_azure_endpoint_case_insensitive(self) -> None:
        assert _is_azure_endpoint("https://MyOrg.OpenAI.Azure.COM") is True

    def test_standard_openai_not_azure(self) -> None:
        assert _is_azure_endpoint("https://api.openai.com/v1") is False

    def test_custom_endpoint_not_azure(self) -> None:
        assert _is_azure_endpoint("https://custom-llm.example.com/v1") is False

    def test_empty_string_not_azure(self) -> None:
        assert _is_azure_endpoint("") is False


# ---------------------------------------------------------------------------
# Factory: Azure adapter creation
# ---------------------------------------------------------------------------


class TestCreateLLMProviderAzure:
    """Tests for create_llm_provider() with Azure endpoints."""

    def test_create_returns_azure_adapter_for_azure_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Azure endpoint URL → returns AzureOpenAIAdapter."""
        monkeypatch.setenv("NEST_AI_API_KEY", "azure-key-123")
        monkeypatch.setenv("NEST_AI_ENDPOINT", "https://myorg.openai.azure.com")
        monkeypatch.setenv("NEST_AI_MODEL", "gpt-4o")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.AzureOpenAI") as mock_azure:
            result = create_llm_provider()

        assert result is not None
        assert isinstance(result, AzureOpenAIAdapter)
        assert result.model_name == "gpt-4o"
        mock_azure.assert_called_once_with(
            api_key="azure-key-123",
            azure_endpoint="https://myorg.openai.azure.com",
            api_version=DEFAULT_AZURE_API_VERSION,
        )

    def test_create_returns_openai_adapter_for_standard_endpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Standard OpenAI endpoint → returns OpenAIAdapter (not Azure)."""
        monkeypatch.setenv("NEST_AI_API_KEY", "openai-key")
        monkeypatch.setenv("NEST_AI_ENDPOINT", "https://api.openai.com/v1")
        monkeypatch.setenv("NEST_AI_MODEL", "gpt-4o-mini")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            result = create_llm_provider()

        assert result is not None
        assert isinstance(result, OpenAIAdapter)


# ---------------------------------------------------------------------------
# AzureOpenAIAdapter.complete()
# ---------------------------------------------------------------------------


class TestAzureOpenAIAdapterComplete:
    """Tests for AzureOpenAIAdapter.complete() method."""

    def _make_adapter(self) -> AzureOpenAIAdapter:
        """Create an Azure adapter with a mocked client."""
        with patch("nest.adapters.llm_provider.openai.AzureOpenAI"):
            return AzureOpenAIAdapter(
                api_key="test-key",
                endpoint="https://myorg.openai.azure.com",
                deployment="gpt-4o",
                api_version="2024-12-01-preview",
            )

    def test_complete_success(self) -> None:
        """Mock Azure client, verify LLMCompletionResult returned."""
        adapter = self._make_adapter()
        mock_response = _make_mock_response(
            content="Azure response", prompt_tokens=20, completion_tokens=10
        )
        adapter._client.chat.completions.create = MagicMock(return_value=mock_response)

        result = adapter.complete("You are helpful.", "Say hello")

        assert result is not None
        assert isinstance(result, LLMCompletionResult)
        assert result.text == "Azure response"
        assert result.prompt_tokens == 20
        assert result.completion_tokens == 10

    def test_complete_error_returns_none(self, caplog: pytest.LogCaptureFixture) -> None:
        """Azure API error → returns None, logs warning."""
        adapter = self._make_adapter()
        adapter._client.chat.completions.create = MagicMock(
            side_effect=Exception("Azure API error")
        )

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = adapter.complete("system", "user")

        assert result is None
        assert "LLM call failed" in caplog.text

    def test_complete_empty_choices(self, caplog: pytest.LogCaptureFixture) -> None:
        """Response with empty choices → returns None."""
        adapter = self._make_adapter()
        mock_response = _make_mock_response(empty_choices=True)
        adapter._client.chat.completions.create = MagicMock(return_value=mock_response)

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = adapter.complete("system", "user")

        assert result is None
        assert "empty choices" in caplog.text

    def test_complete_none_content(self, caplog: pytest.LogCaptureFixture) -> None:
        """Response content is None → returns None."""
        adapter = self._make_adapter()
        mock_response = _make_mock_response(content=None)
        adapter._client.chat.completions.create = MagicMock(return_value=mock_response)

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = adapter.complete("system", "user")

        assert result is None
        assert "None content" in caplog.text

    def test_model_name_returns_deployment(self) -> None:
        """model_name property returns deployment name."""
        adapter = self._make_adapter()
        assert adapter.model_name == "gpt-4o"

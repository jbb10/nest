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
    AzureOpenAIAdapter,
    AzureOpenAIVisionAdapter,
    OpenAIAdapter,
    OpenAIVisionAdapter,
    _is_azure_endpoint,
    create_llm_provider,
    create_vision_provider,
)
from nest.adapters.protocols import LLMProviderProtocol, VisionLLMProviderProtocol
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
        monkeypatch.setenv("NEST_AI_API_KEY", "nest-ai-key-123")
        monkeypatch.setenv("NEST_AI_ENDPOINT", "https://custom.api/v1")
        monkeypatch.setenv("NEST_AI_MODEL", "gpt-4o")
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            result = create_llm_provider()

        assert result is not None
        assert result.model_name == "gpt-4o"
        mock_openai.assert_called_once_with(
            api_key="nest-ai-key-123", base_url="https://custom.api/v1"
        )

    def test_create_with_openai_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only OPENAI_API_KEY set → returns adapter."""
        monkeypatch.delenv("NEST_AI_API_KEY", raising=False)
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key-456")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.custom/v1")
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
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        result = create_llm_provider()

        assert result is None

    def test_nest_ai_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NEST_AI_API_KEY takes precedence over NEST_API_KEY and OPENAI_API_KEY."""
        monkeypatch.setenv("NEST_AI_API_KEY", "nest-ai-key")
        monkeypatch.setenv("NEST_API_KEY", "nest-key")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
        monkeypatch.setenv("NEST_AI_MODEL", "gpt-4o")
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            result = create_llm_provider()

        assert result is not None
        mock_openai.assert_called_once_with(api_key="nest-ai-key", base_url=DEFAULT_ENDPOINT)

    def test_endpoint_fallback_chain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test all four levels: NEST_AI_ENDPOINT → NEST_BASE_URL → OPENAI_BASE_URL → default."""
        monkeypatch.setenv("NEST_AI_API_KEY", "key")
        monkeypatch.setenv("NEST_AI_MODEL", "gpt-4o")
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        # Level 1: NEST_AI_ENDPOINT wins
        monkeypatch.setenv("NEST_AI_ENDPOINT", "https://nest-ai-ep/v1")
        monkeypatch.setenv("NEST_BASE_URL", "https://nest-ep/v1")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://openai-ep/v1")
        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            create_llm_provider()
        mock_openai.assert_called_once_with(api_key="key", base_url="https://nest-ai-ep/v1")

        # Level 2: NEST_BASE_URL fallback
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            create_llm_provider()
        mock_openai.assert_called_once_with(api_key="key", base_url="https://nest-ep/v1")

        # Level 3: OPENAI_BASE_URL fallback
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            create_llm_provider()
        mock_openai.assert_called_once_with(api_key="key", base_url="https://openai-ep/v1")

        # Level 4: default
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            create_llm_provider()
        mock_openai.assert_called_once_with(api_key="key", base_url=DEFAULT_ENDPOINT)

    def test_model_fallback_chain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test all four levels: NEST_AI_MODEL → NEST_TEXT_MODEL → OPENAI_MODEL → None."""
        monkeypatch.setenv("NEST_AI_API_KEY", "key")
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

        # Level 1: NEST_AI_MODEL wins
        monkeypatch.setenv("NEST_AI_MODEL", "nest-ai-model")
        monkeypatch.setenv("NEST_TEXT_MODEL", "nest-model")
        monkeypatch.setenv("OPENAI_MODEL", "openai-model")
        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            result = create_llm_provider()
        assert result is not None
        assert result.model_name == "nest-ai-model"

        # Level 2: NEST_TEXT_MODEL fallback
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            result = create_llm_provider()
        assert result is not None
        assert result.model_name == "nest-model"

        # Level 3: OPENAI_MODEL fallback
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            result = create_llm_provider()
        assert result is not None
        assert result.model_name == "openai-model"

        # Level 4: no model → None
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            result = create_llm_provider()
        assert result is None

    def test_default_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No endpoint vars → https://api.openai.com/v1."""
        monkeypatch.setenv("NEST_AI_API_KEY", "key")
        monkeypatch.setenv("NEST_AI_MODEL", "gpt-4o")
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            create_llm_provider()
        mock_openai.assert_called_once_with(api_key="key", base_url="https://api.openai.com/v1")

    def test_no_model_configured_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No model vars → returns None and logs a warning."""
        monkeypatch.setenv("NEST_AI_API_KEY", "key")
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = create_llm_provider()
        assert result is None
        assert "No LLM model configured" in caplog.text


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
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
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
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
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


# ---------------------------------------------------------------------------
# Vision adapters: protocol compliance
# ---------------------------------------------------------------------------


class TestVisionProtocolCompliance:
    """Tests for VisionLLMProviderProtocol compliance."""

    def test_openai_vision_adapter_satisfies_protocol(self) -> None:
        """isinstance(OpenAIVisionAdapter(...), VisionLLMProviderProtocol) is True."""
        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            adapter = OpenAIVisionAdapter(
                api_key="key", endpoint="https://api.test.com/v1", model="gpt-4.1"
            )
        assert isinstance(adapter, VisionLLMProviderProtocol)

    def test_azure_vision_adapter_satisfies_protocol(self) -> None:
        """isinstance(AzureOpenAIVisionAdapter(...), VisionLLMProviderProtocol) is True."""
        with patch("nest.adapters.llm_provider.openai.AzureOpenAI"):
            adapter = AzureOpenAIVisionAdapter(
                api_key="key",
                endpoint="https://myorg.openai.azure.com",
                deployment="gpt-4.1",
                api_version="2024-12-01-preview",
            )
        assert isinstance(adapter, VisionLLMProviderProtocol)


# ---------------------------------------------------------------------------
# Vision adapters: OpenAIVisionAdapter.complete_with_image()
# ---------------------------------------------------------------------------


class TestVisionAdapters:
    """Tests for OpenAIVisionAdapter and AzureOpenAIVisionAdapter."""

    def _make_openai_adapter(self) -> OpenAIVisionAdapter:
        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            return OpenAIVisionAdapter(
                api_key="test-key",
                endpoint="https://api.test.com/v1",
                model="gpt-4.1",
            )

    def _make_azure_adapter(self) -> AzureOpenAIVisionAdapter:
        with patch("nest.adapters.llm_provider.openai.AzureOpenAI"):
            return AzureOpenAIVisionAdapter(
                api_key="test-key",
                endpoint="https://myorg.openai.azure.com",
                deployment="gpt-4.1",
                api_version="2024-12-01-preview",
            )

    # 6.3 — success (OpenAI)
    def test_complete_with_image_success_openai(self) -> None:
        """Mock client returns valid response — LLMCompletionResult with correct fields."""
        adapter = self._make_openai_adapter()
        mock_response = _make_mock_response(
            content="A dog in a park", prompt_tokens=20, completion_tokens=8
        )
        adapter._client.chat.completions.create = MagicMock(return_value=mock_response)

        result = adapter.complete_with_image("Describe this image", "abc123", "image/png")

        assert result is not None
        assert isinstance(result, LLMCompletionResult)
        assert result.text == "A dog in a park"
        assert result.prompt_tokens == 20
        assert result.completion_tokens == 8

    # 6.4 — correct payload structure
    def test_complete_with_image_correct_payload(self) -> None:
        """Verify exact multi-modal message payload sent to API."""
        adapter = self._make_openai_adapter()
        mock_response = _make_mock_response(content="ok")
        mock_create = MagicMock(return_value=mock_response)
        adapter._client.chat.completions.create = mock_create

        adapter.complete_with_image("Describe this", "base64data", "image/jpeg")

        # Extract messages from keyword args
        messages = mock_create.call_args.kwargs["messages"]
        assert len(messages) == 1
        msg = messages[0]
        assert msg["role"] == "user"
        content_blocks = msg["content"]
        assert len(content_blocks) == 2
        assert content_blocks[0] == {"type": "text", "text": "Describe this"}
        assert content_blocks[1] == {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64,base64data"},
        }

    # 6.5 — default mime_type
    def test_complete_with_image_default_mime_type(self) -> None:
        """Calling without mime_type → image/png appears in the URL."""
        adapter = self._make_openai_adapter()
        mock_response = _make_mock_response(content="ok")
        mock_create = MagicMock(return_value=mock_response)
        adapter._client.chat.completions.create = mock_create

        adapter.complete_with_image("Describe this", "imgdata")

        messages = mock_create.call_args.kwargs["messages"]
        url = messages[0]["content"][1]["image_url"]["url"]
        assert "image/png" in url

    # 6.6 — API exception
    def test_complete_with_image_api_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """Exception raised by API → returns None, logs 'Vision LLM call failed'."""
        adapter = self._make_openai_adapter()
        adapter._client.chat.completions.create = MagicMock(side_effect=Exception("boom"))

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = adapter.complete_with_image("prompt", "data")

        assert result is None
        assert "Vision LLM call failed" in caplog.text

    # 6.7 — empty choices
    def test_complete_with_image_empty_choices(self, caplog: pytest.LogCaptureFixture) -> None:
        """Empty choices → returns None, logs warning."""
        adapter = self._make_openai_adapter()
        mock_response = _make_mock_response(empty_choices=True)
        adapter._client.chat.completions.create = MagicMock(return_value=mock_response)

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = adapter.complete_with_image("prompt", "data")

        assert result is None
        assert "empty choices" in caplog.text

    # 6.8 — None content
    def test_complete_with_image_none_content(self, caplog: pytest.LogCaptureFixture) -> None:
        """None content → returns None, logs warning."""
        adapter = self._make_openai_adapter()
        mock_response = _make_mock_response(content=None)
        adapter._client.chat.completions.create = MagicMock(return_value=mock_response)

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = adapter.complete_with_image("prompt", "data")

        assert result is None
        assert "None content" in caplog.text

    # 6.9 — None usage
    def test_complete_with_image_none_usage(self) -> None:
        """None usage → returns result with prompt_tokens=0, completion_tokens=0."""
        adapter = self._make_openai_adapter()
        mock_response = _make_mock_response(none_usage=True)
        adapter._client.chat.completions.create = MagicMock(return_value=mock_response)

        result = adapter.complete_with_image("prompt", "data")

        assert result is not None
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0

    # 6.9.1 — model_name property (OpenAI)
    def test_openai_vision_adapter_model_name(self) -> None:
        """OpenAIVisionAdapter.model_name returns the configured model."""
        adapter = self._make_openai_adapter()
        assert adapter.model_name == "gpt-4.1"

    # 6.10 — Azure success
    def test_complete_with_image_azure_success(self) -> None:
        """AzureOpenAIVisionAdapter — same scenario passes correctly."""
        adapter = self._make_azure_adapter()
        mock_response = _make_mock_response(
            content="Azure vision response", prompt_tokens=30, completion_tokens=12
        )
        adapter._client.chat.completions.create = MagicMock(return_value=mock_response)

        result = adapter.complete_with_image("Describe this image", "abc123", "image/png")

        assert result is not None
        assert isinstance(result, LLMCompletionResult)
        assert result.text == "Azure vision response"
        assert result.prompt_tokens == 30
        assert result.completion_tokens == 12

    # 6.10.1 — Azure payload structure (AC2 parity)
    def test_complete_with_image_azure_correct_payload(self) -> None:
        """AzureOpenAIVisionAdapter — exact multi-modal message payload sent to API."""
        adapter = self._make_azure_adapter()
        mock_response = _make_mock_response(content="ok")
        mock_create = MagicMock(return_value=mock_response)
        adapter._client.chat.completions.create = mock_create

        adapter.complete_with_image("Describe this", "base64data", "image/jpeg")

        messages = mock_create.call_args.kwargs["messages"]
        assert len(messages) == 1
        msg = messages[0]
        assert msg["role"] == "user"
        content_blocks = msg["content"]
        assert len(content_blocks) == 2
        assert content_blocks[0] == {"type": "text", "text": "Describe this"}
        assert content_blocks[1] == {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64,base64data"},
        }


# ---------------------------------------------------------------------------
# Factory: create_vision_provider()
# ---------------------------------------------------------------------------


class TestCreateVisionProvider:
    """Tests for create_vision_provider() factory function."""

    # 6.11 — no API key
    def test_no_api_key_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Both key env vars unset → returns None."""
        monkeypatch.delenv("NEST_AI_API_KEY", raising=False)
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_AI_VISION_MODEL", raising=False)
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.delenv("NEST_VISION_MODEL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        result = create_vision_provider()

        assert result is None

    # 6.12 — NEST_AI_VISION_MODEL wins
    def test_nest_ai_vision_model_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NEST_AI_VISION_MODEL set → adapter uses that model."""
        monkeypatch.setenv("NEST_AI_API_KEY", "key")
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.setenv("NEST_AI_VISION_MODEL", "gpt-4-vision-primary")
        monkeypatch.setenv("NEST_VISION_MODEL", "gpt-4-vision-preview")
        monkeypatch.setenv("OPENAI_VISION_MODEL", "other-model")

        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            result = create_vision_provider()

        assert result is not None
        assert result.model_name == "gpt-4-vision-primary"

    # 6.13 — OPENAI_VISION_MODEL fallback
    def test_openai_vision_model_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NEST_VISION_MODEL unset, OPENAI_VISION_MODEL set → uses OPENAI value."""
        monkeypatch.setenv("NEST_API_KEY", "key")
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_VISION_MODEL", raising=False)
        monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o-vision")

        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            result = create_vision_provider()

        assert result is not None
        assert result.model_name == "gpt-4o-vision"

    # 6.14 — no vision model and no text model → None
    def test_no_vision_model_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No vision or text model vars set → returns None and logs a warning."""
        monkeypatch.setenv("NEST_AI_API_KEY", "key")
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_AI_VISION_MODEL", raising=False)
        monkeypatch.delenv("NEST_VISION_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = create_vision_provider()

        assert result is None
        assert "No vision model configured" in caplog.text

    # 6.14b — NEST_AI_MODEL fallback for non-Azure endpoint
    def test_nest_ai_model_fallback_non_azure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-Azure + NEST_AI_MODEL set, no vision vars → uses NEST_AI_MODEL for vision."""
        monkeypatch.setenv("NEST_AI_API_KEY", "key")
        monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_AI_VISION_MODEL", raising=False)
        monkeypatch.delenv("NEST_VISION_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)
        monkeypatch.setenv("NEST_AI_MODEL", "gpt-4.1")
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.OpenAI"):
            result = create_vision_provider()

        assert result is not None
        assert isinstance(result, OpenAIVisionAdapter)
        assert result.model_name == "gpt-4.1"

    # 6.15 — Azure routing
    def test_azure_endpoint_returns_azure_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Azure endpoint with a text model set → AzureOpenAIVisionAdapter."""
        monkeypatch.setenv("NEST_AI_API_KEY", "azure-key")
        monkeypatch.setenv("NEST_AI_ENDPOINT", "https://myorg.openai.azure.com")
        monkeypatch.setenv("NEST_AI_MODEL", "gpt-4o")
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_AI_VISION_MODEL", raising=False)
        monkeypatch.delenv("NEST_VISION_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.AzureOpenAI") as mock_azure:
            result = create_vision_provider()

        assert result is not None
        assert isinstance(result, AzureOpenAIVisionAdapter)
        assert result.model_name == "gpt-4o"
        mock_azure.assert_called_once_with(
            api_key="azure-key",
            azure_endpoint="https://myorg.openai.azure.com",
            api_version=DEFAULT_AZURE_API_VERSION,
        )

    # 6.15z — Azure with no model at all → None
    def test_azure_no_model_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Azure endpoint with no model configured → returns None."""
        monkeypatch.setenv("NEST_AI_API_KEY", "azure-key")
        monkeypatch.setenv("NEST_AI_ENDPOINT", "https://myorg.openai.azure.com")
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_AI_VISION_MODEL", raising=False)
        monkeypatch.delenv("NEST_VISION_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with caplog.at_level(logging.WARNING, logger="nest.adapters.llm_provider"):
            result = create_vision_provider()

        assert result is None
        assert "No vision model configured" in caplog.text

    # 6.15b — Azure falls back to NEST_AI_MODEL when no vision model is set
    def test_azure_falls_back_to_nest_ai_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Azure + NEST_AI_MODEL set, no vision vars → uses NEST_AI_MODEL as deployment."""
        monkeypatch.setenv("NEST_AI_API_KEY", "azure-key")
        monkeypatch.setenv("NEST_AI_ENDPOINT", "https://myorg.openai.azure.com")
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_AI_VISION_MODEL", raising=False)
        monkeypatch.delenv("NEST_VISION_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)
        monkeypatch.setenv("NEST_AI_MODEL", "gpt-4o")
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.AzureOpenAI"):
            result = create_vision_provider()

        assert result is not None
        assert isinstance(result, AzureOpenAIVisionAdapter)
        assert result.model_name == "gpt-4o"

    # 6.15c — Azure falls back to OPENAI_MODEL when NEST_AI_MODEL unset
    def test_azure_falls_back_to_openai_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Azure + OPENAI_MODEL set, no vision or NEST_AI_MODEL vars → uses OPENAI_MODEL."""
        monkeypatch.setenv("NEST_AI_API_KEY", "azure-key")
        monkeypatch.setenv("NEST_AI_ENDPOINT", "https://myorg.openai.azure.com")
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_AI_VISION_MODEL", raising=False)
        monkeypatch.delenv("NEST_VISION_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)
        monkeypatch.delenv("NEST_AI_MODEL", raising=False)
        monkeypatch.delenv("NEST_TEXT_MODEL", raising=False)
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-2024-11")

        with patch("nest.adapters.llm_provider.openai.AzureOpenAI"):
            result = create_vision_provider()

        assert result is not None
        assert isinstance(result, AzureOpenAIVisionAdapter)
        assert result.model_name == "gpt-4o-2024-11"

    # 6.15d — NEST_AI_VISION_MODEL always wins on Azure too
    def test_azure_explicit_vision_model_wins_over_text_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Azure + explicit NEST_AI_VISION_MODEL → vision model overrides NEST_AI_MODEL."""
        monkeypatch.setenv("NEST_AI_API_KEY", "azure-key")
        monkeypatch.setenv("NEST_AI_ENDPOINT", "https://myorg.openai.azure.com")
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.setenv("NEST_AI_VISION_MODEL", "gpt-4o-vision-deploy")
        monkeypatch.setenv("NEST_VISION_MODEL", "ignored")
        monkeypatch.setenv("OPENAI_VISION_MODEL", "ignored")
        monkeypatch.setenv("NEST_AI_MODEL", "gpt-4o-mini-deploy")
        monkeypatch.setenv("NEST_TEXT_MODEL", "gpt-4o-mini-deploy")

        with patch("nest.adapters.llm_provider.openai.AzureOpenAI"):
            result = create_vision_provider()

        assert result is not None
        assert isinstance(result, AzureOpenAIVisionAdapter)
        assert result.model_name == "gpt-4o-vision-deploy"

    # 6.16 — NEST_AI_ENDPOINT propagates to vision adapter
    def test_nest_ai_endpoint_propagates_to_vision_adapter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NEST_AI_ENDPOINT → vision adapter uses same endpoint."""
        monkeypatch.setenv("NEST_AI_API_KEY", "key")
        monkeypatch.setenv("NEST_AI_ENDPOINT", "https://custom-vision.api/v1")
        monkeypatch.setenv("NEST_AI_VISION_MODEL", "gpt-4-vision")
        monkeypatch.delenv("NEST_API_KEY", raising=False)
        monkeypatch.delenv("NEST_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.delenv("NEST_VISION_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)

        with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
            result = create_vision_provider()

        assert result is not None
        assert isinstance(result, OpenAIVisionAdapter)
        mock_openai.assert_called_once_with(api_key="key", base_url="https://custom-vision.api/v1")

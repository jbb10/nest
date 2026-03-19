"""OpenAI-compatible LLM provider adapter.

Wraps the openai Python SDK for chat completions.
Provides auto-detection of API credentials from environment variables.
Supports both standard OpenAI and Azure OpenAI endpoints.
"""

from __future__ import annotations

import logging
import os

import openai

from nest.core.models import LLMCompletionResult

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_VISION_MODEL = "gpt-4.1"
DEFAULT_AZURE_API_VERSION = "2024-12-01-preview"


def _is_azure_endpoint(endpoint: str) -> bool:
    """Check if an endpoint URL is an Azure OpenAI endpoint."""
    return ".openai.azure.com" in endpoint.lower()


class OpenAIAdapter:
    """OpenAI-compatible LLM adapter.

    Wraps the openai Python SDK for chat completions.
    Handles errors gracefully — returns None on failure, never raises.
    """

    def __init__(self, api_key: str, endpoint: str, model: str) -> None:
        self._client = openai.OpenAI(api_key=api_key, base_url=endpoint)
        self._model = model

    @property
    def model_name(self) -> str:
        """Return the configured model name."""
        return self._model

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMCompletionResult | None:
        """Send a chat completion request.

        Args:
            system_prompt: System-level instructions for the model.
            user_prompt: User message content.

        Returns:
            LLMCompletionResult with response text and token usage,
            or None if the call failed (error is logged internally).
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            if not response.choices:
                logger.warning("LLM call returned empty choices")
                return None

            content = response.choices[0].message.content
            if content is None:
                logger.warning("LLM call returned None content")
                return None

            prompt_tokens = 0
            completion_tokens = 0
            if response.usage is not None:
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens

            return LLMCompletionResult(
                text=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

        except Exception as e:
            logger.warning("LLM call failed: %s", e)
            return None


class AzureOpenAIAdapter:
    """Azure OpenAI LLM adapter.

    Wraps the openai Python SDK's AzureOpenAI client for chat completions.
    Handles errors gracefully — returns None on failure, never raises.
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str,
    ) -> None:
        self._client = openai.AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        self._deployment = deployment

    @property
    def model_name(self) -> str:
        """Return the configured deployment name."""
        return self._deployment

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMCompletionResult | None:
        """Send a chat completion request to Azure OpenAI.

        Args:
            system_prompt: System-level instructions for the model.
            user_prompt: User message content.

        Returns:
            LLMCompletionResult with response text and token usage,
            or None if the call failed (error is logged internally).
        """
        try:
            response = self._client.chat.completions.create(
                model=self._deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            if not response.choices:
                logger.warning("LLM call returned empty choices")
                return None

            content = response.choices[0].message.content
            if content is None:
                logger.warning("LLM call returned None content")
                return None

            prompt_tokens = 0
            completion_tokens = 0
            if response.usage is not None:
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens

            return LLMCompletionResult(
                text=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

        except Exception as e:
            logger.warning("LLM call failed: %s", e)
            return None


def create_llm_provider() -> OpenAIAdapter | AzureOpenAIAdapter | None:
    """Auto-detect AI credentials from environment variables.

    Fallback chain:
        API key:  NEST_AI_API_KEY → OPENAI_API_KEY → None
        Endpoint: NEST_AI_ENDPOINT → OPENAI_API_BASE → https://api.openai.com/v1
        Model:    NEST_AI_MODEL → OPENAI_MODEL → gpt-4o-mini

    If the resolved endpoint contains `.openai.azure.com`, an AzureOpenAIAdapter
    is returned instead of the standard OpenAIAdapter.

    Returns:
        Configured adapter if API key found, None otherwise.
    """
    api_key = os.environ.get("NEST_AI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    endpoint = (
        os.environ.get("NEST_AI_ENDPOINT") or os.environ.get("OPENAI_API_BASE") or DEFAULT_ENDPOINT
    )
    model = os.environ.get("NEST_AI_MODEL") or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL

    if _is_azure_endpoint(endpoint):
        return AzureOpenAIAdapter(
            api_key=api_key,
            endpoint=endpoint,
            deployment=model,
            api_version=DEFAULT_AZURE_API_VERSION,
        )

    return OpenAIAdapter(api_key=api_key, endpoint=endpoint, model=model)


class OpenAIVisionAdapter:
    """OpenAI-compatible vision LLM adapter.

    Wraps the openai Python SDK for multi-modal (image + text) chat completions.
    Handles errors gracefully — returns None on failure, never raises.
    """

    def __init__(self, api_key: str, endpoint: str, model: str) -> None:
        self._client = openai.OpenAI(api_key=api_key, base_url=endpoint)
        self._model = model

    @property
    def model_name(self) -> str:
        """Return the configured model name."""
        return self._model

    def complete_with_image(
        self,
        prompt: str,
        image_base64: str,
        mime_type: str = "image/png",
    ) -> LLMCompletionResult | None:
        """Send a multi-modal completion request with an image.

        Args:
            prompt: User prompt text accompanying the image.
            image_base64: Base64-encoded image bytes.
            mime_type: MIME type of the image (e.g. "image/png", "image/jpeg").

        Returns:
            LLMCompletionResult with response text and token usage,
            or None if the call failed (error is logged internally).
        """
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                        },
                    ],
                }
            ]
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
            )

            if not response.choices:
                logger.warning("Vision LLM call returned empty choices")
                return None

            content = response.choices[0].message.content
            if content is None:
                logger.warning("Vision LLM call returned None content")
                return None

            prompt_tokens = 0
            completion_tokens = 0
            if response.usage is not None:
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens

            return LLMCompletionResult(
                text=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

        except Exception as e:
            logger.warning("Vision LLM call failed: %s", e)
            return None


class AzureOpenAIVisionAdapter:
    """Azure OpenAI vision LLM adapter.

    Wraps the openai Python SDK's AzureOpenAI client for multi-modal
    (image + text) chat completions.
    Handles errors gracefully — returns None on failure, never raises.
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str,
    ) -> None:
        self._client = openai.AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        self._deployment = deployment

    @property
    def model_name(self) -> str:
        """Return the configured deployment name."""
        return self._deployment

    def complete_with_image(
        self,
        prompt: str,
        image_base64: str,
        mime_type: str = "image/png",
    ) -> LLMCompletionResult | None:
        """Send a multi-modal completion request with an image via Azure OpenAI.

        Args:
            prompt: User prompt text accompanying the image.
            image_base64: Base64-encoded image bytes.
            mime_type: MIME type of the image (e.g. "image/png", "image/jpeg").

        Returns:
            LLMCompletionResult with response text and token usage,
            or None if the call failed (error is logged internally).
        """
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                        },
                    ],
                }
            ]
            response = self._client.chat.completions.create(
                model=self._deployment,
                messages=messages,  # type: ignore[arg-type]
            )

            if not response.choices:
                logger.warning("Vision LLM call returned empty choices")
                return None

            content = response.choices[0].message.content
            if content is None:
                logger.warning("Vision LLM call returned None content")
                return None

            prompt_tokens = 0
            completion_tokens = 0
            if response.usage is not None:
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens

            return LLMCompletionResult(
                text=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

        except Exception as e:
            logger.warning("Vision LLM call failed: %s", e)
            return None


def create_vision_provider() -> OpenAIVisionAdapter | AzureOpenAIVisionAdapter | None:
    """Auto-detect AI credentials from environment variables for vision use.

    Fallback chain:
        API key:      NEST_AI_API_KEY → OPENAI_API_KEY → None
        Endpoint:     NEST_AI_ENDPOINT → OPENAI_API_BASE → https://api.openai.com/v1
        Vision model: NEST_AI_VISION_MODEL → OPENAI_VISION_MODEL → gpt-4.1

    If the resolved endpoint contains `.openai.azure.com`, an
    AzureOpenAIVisionAdapter is returned instead of OpenAIVisionAdapter.

    Returns:
        Configured vision adapter if API key found, None otherwise.
    """
    api_key = os.environ.get("NEST_AI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    endpoint = (
        os.environ.get("NEST_AI_ENDPOINT") or os.environ.get("OPENAI_API_BASE") or DEFAULT_ENDPOINT
    )
    vision_model = (
        os.environ.get("NEST_AI_VISION_MODEL")
        or os.environ.get("OPENAI_VISION_MODEL")
        or DEFAULT_VISION_MODEL
    )

    if _is_azure_endpoint(endpoint):
        return AzureOpenAIVisionAdapter(
            api_key=api_key,
            endpoint=endpoint,
            deployment=vision_model,
            api_version=DEFAULT_AZURE_API_VERSION,
        )

    return OpenAIVisionAdapter(api_key=api_key, endpoint=endpoint, model=vision_model)

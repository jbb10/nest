"""OpenAI-compatible LLM provider adapter.

Wraps the openai Python SDK for chat completions.
Provides auto-detection of API credentials from environment variables.
Supports both standard OpenAI and Azure OpenAI endpoints.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import openai

from nest.core.models import LLMCompletionResult

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://api.openai.com/v1"
DEFAULT_AZURE_API_VERSION = "2024-12-01-preview"


def _is_azure_endpoint(endpoint: str) -> bool:
    """Check if an endpoint URL is an Azure OpenAI endpoint."""
    return ".openai.azure.com" in endpoint.lower()


# Seconds allowed per request before the SDK retries. The SDK default of 600s
# lets one stalled connection block a sync for many minutes.
LLM_REQUEST_TIMEOUT = 120.0


class OpenAIAdapter:
    """OpenAI-compatible LLM adapter.

    Wraps the openai Python SDK for chat completions.
    Handles errors gracefully — returns None on failure, never raises.
    """

    def __init__(self, api_key: str, endpoint: str, model: str) -> None:
        self._client = openai.OpenAI(
            api_key=api_key, base_url=endpoint, timeout=LLM_REQUEST_TIMEOUT
        )
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
            timeout=LLM_REQUEST_TIMEOUT,
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


@dataclass(frozen=True)
class LLMConfig:
    """LLM settings resolved from the environment.

    Attributes:
        api_key: The API key.
        api_key_var: Name of the environment variable the key came from.
        endpoint: Base URL of the OpenAI-compatible or Azure endpoint.
        text_model: Model for text completions, if configured.
        vision_model: Model for image description, if configured.
    """

    api_key: str = field(repr=False)
    api_key_var: str
    endpoint: str
    text_model: str | None
    vision_model: str | None

    @property
    def is_azure(self) -> bool:
        return _is_azure_endpoint(self.endpoint)


def _first_env(*names: str) -> tuple[str, str] | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return name, value
    return None


# Variable names read before the AI-to-LLM rename. Their values are never used;
# they are only detected so an upgraded user learns why nothing is configured.
LEGACY_LLM_ENV_VARS = (
    "NEST_AI_API_KEY",
    "NEST_AI_ENDPOINT",
    "NEST_AI_MODEL",
    "NEST_AI_VISION_MODEL",
)


def legacy_llm_env_vars() -> list[str]:
    """Names of pre-rename ``NEST_AI_*`` variables present in the environment."""
    return [name for name in LEGACY_LLM_ENV_VARS if os.environ.get(name)]


def resolve_llm_config() -> LLMConfig | None:
    """Resolve LLM settings from Nest-prefixed environment variables.

    Fallback chains:
        API key:      NEST_LLM_API_KEY → NEST_API_KEY
        Endpoint:     NEST_LLM_ENDPOINT → NEST_BASE_URL → https://api.openai.com/v1
        Text model:   NEST_LLM_MODEL → NEST_TEXT_MODEL
        Vision model: NEST_LLM_VISION_MODEL → NEST_VISION_MODEL → the text model

    Returns:
        The resolved configuration, or None when no API key is set.
    """
    key = _first_env("NEST_LLM_API_KEY", "NEST_API_KEY")
    if key is None:
        return None
    endpoint = _first_env("NEST_LLM_ENDPOINT", "NEST_BASE_URL")
    text_model = _first_env("NEST_LLM_MODEL", "NEST_TEXT_MODEL")
    vision_model = _first_env("NEST_LLM_VISION_MODEL", "NEST_VISION_MODEL") or text_model
    return LLMConfig(
        api_key=key[1],
        api_key_var=key[0],
        endpoint=endpoint[1] if endpoint else DEFAULT_ENDPOINT,
        text_model=text_model[1] if text_model else None,
        vision_model=vision_model[1] if vision_model else None,
    )


def create_llm_provider(
    config: LLMConfig | None = None,
) -> OpenAIAdapter | AzureOpenAIAdapter | None:
    """Create a text LLM adapter from the resolved LLM configuration.

    Returns None when no API key or text model is configured, so callers skip
    LLM features rather than sending a wrong model name to the API. Azure
    endpoints (``.openai.azure.com``) get an ``AzureOpenAIAdapter``.

    Args:
        config: Pre-resolved configuration; resolved from the environment when omitted.
    """
    config = config or resolve_llm_config()
    if config is None:
        return None
    if not config.text_model:
        logger.warning(
            "No LLM model configured. Set NEST_LLM_MODEL"
            " (or run 'nest config llm') to enable LLM features."
        )
        return None

    if config.is_azure:
        return AzureOpenAIAdapter(
            api_key=config.api_key,
            endpoint=config.endpoint,
            deployment=config.text_model,
            api_version=DEFAULT_AZURE_API_VERSION,
        )

    return OpenAIAdapter(api_key=config.api_key, endpoint=config.endpoint, model=config.text_model)


class OpenAIVisionAdapter:
    """OpenAI-compatible vision LLM adapter.

    Wraps the openai Python SDK for multi-modal (image + text) chat completions.
    Handles errors gracefully — returns None on failure, never raises.
    """

    def __init__(self, api_key: str, endpoint: str, model: str) -> None:
        self._client = openai.OpenAI(
            api_key=api_key, base_url=endpoint, timeout=LLM_REQUEST_TIMEOUT
        )
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
            timeout=LLM_REQUEST_TIMEOUT,
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


def create_vision_provider(
    config: LLMConfig | None = None,
) -> OpenAIVisionAdapter | AzureOpenAIVisionAdapter | None:
    """Create a vision LLM adapter from the resolved LLM configuration.

    Returns None when no API key or vision model is configured. The vision
    model falls back to the text model, so a single ``NEST_LLM_MODEL`` enables
    both text and vision features. Azure endpoints get an
    ``AzureOpenAIVisionAdapter``.

    Args:
        config: Pre-resolved configuration; resolved from the environment when omitted.
    """
    config = config or resolve_llm_config()
    if config is None:
        return None
    if not config.vision_model:
        logger.warning(
            "No vision model configured. Set NEST_LLM_VISION_MODEL"
            " (or run 'nest config llm') to enable vision features."
        )
        return None

    if config.is_azure:
        return AzureOpenAIVisionAdapter(
            api_key=config.api_key,
            endpoint=config.endpoint,
            deployment=config.vision_model,
            api_version=DEFAULT_AZURE_API_VERSION,
        )

    return OpenAIVisionAdapter(
        api_key=config.api_key, endpoint=config.endpoint, model=config.vision_model
    )

"""Unit tests for shared UI message helpers."""

import pytest

from nest.ui.messages import (
    LLM_LEGACY_CONFIG_NOTE,
    LLM_NOT_CONFIGURED_NOTE,
    llm_not_configured_note,
)

_VARS = ("NEST_AI_API_KEY", "NEST_AI_ENDPOINT", "NEST_AI_MODEL", "NEST_AI_VISION_MODEL")


class TestLLMNotConfiguredNote:
    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in _VARS:
            monkeypatch.delenv(name, raising=False)

    def test_generic_note_without_legacy_vars(self) -> None:
        assert llm_not_configured_note() == LLM_NOT_CONFIGURED_NOTE

    def test_legacy_note_when_nest_ai_vars_linger(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A stale `nest config ai` block must not read as a fresh install."""
        monkeypatch.setenv("NEST_AI_API_KEY", "stale")

        note = llm_not_configured_note()

        assert note == LLM_LEGACY_CONFIG_NOTE
        assert "nest config llm" in note

"""Tests for AIEnrichmentService."""

from __future__ import annotations

from nest.core.models import (
    FileMetadata,
    HeadingInfo,
    LLMCompletionResult,
)
from nest.services.ai_enrichment_service import (
    ENRICHMENT_SYSTEM_PROMPT,
    AIEnrichmentService,
)


class MockLLMProvider:
    """Mock LLM provider for testing AI enrichment."""

    def __init__(self, responses: list[LLMCompletionResult | None] | None = None) -> None:
        self._responses = responses or []
        self._call_index = 0
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletionResult | None:
        self.calls.append((system_prompt, user_prompt))
        if self._call_index < len(self._responses):
            result = self._responses[self._call_index]
            self._call_index += 1
            return result
        return None

    @property
    def model_name(self) -> str:
        return "mock-model"


def _make_file(
    path: str = "doc.md",
    content_hash: str = "abc123",
    lines: int = 50,
    headings: list[HeadingInfo] | None = None,
    first_paragraph: str = "",
    table_columns: list[str] | None = None,
) -> FileMetadata:
    """Helper to create a FileMetadata fixture."""
    return FileMetadata(
        path=path,
        content_hash=content_hash,
        lines=lines,
        headings=headings or [],
        first_paragraph=first_paragraph,
        table_columns=table_columns or [],
    )


def _make_result(
    text: str = "A concise description",
    prompt_tokens: int = 100,
    completion_tokens: int = 10,
) -> LLMCompletionResult:
    """Helper to create an LLMCompletionResult fixture."""
    return LLMCompletionResult(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


class TestEnrichGeneratesDescriptions:
    """Tests for basic enrichment of new files."""

    def test_enrich_generates_descriptions_for_new_files(self) -> None:
        """All new files should trigger LLM calls."""
        files = [_make_file("a.md", "hash1"), _make_file("b.md", "hash2")]
        responses = [
            _make_result("Description for A"),
            _make_result("Description for B"),
        ]
        provider = MockLLMProvider(responses)
        service = AIEnrichmentService(llm_provider=provider)

        result = service.enrich(files, old_descriptions={}, old_hints={})

        assert result.descriptions["a.md"] == "Description for A"
        assert result.descriptions["b.md"] == "Description for B"
        assert len(provider.calls) == 2
        assert result.files_enriched == 2

    def test_enrich_returns_descriptions_and_token_counts(self) -> None:
        """Result should contain correct token aggregation."""
        files = [_make_file("a.md"), _make_file("b.md")]
        responses = [
            _make_result("Desc A", prompt_tokens=50, completion_tokens=5),
            _make_result("Desc B", prompt_tokens=60, completion_tokens=8),
        ]
        provider = MockLLMProvider(responses)
        service = AIEnrichmentService(llm_provider=provider)

        result = service.enrich(files, old_descriptions={}, old_hints={})

        assert result.prompt_tokens == 110
        assert result.completion_tokens == 13
        assert result.files_enriched == 2


class TestIncrementalLogic:
    """Tests for incremental enrichment (AC2, AC3, AC4)."""

    def test_enrich_skips_unchanged_files(self) -> None:
        """File with same content_hash and existing description → no LLM call."""
        files = [_make_file("doc.md", content_hash="same_hash")]
        old_hints = {"doc.md": "same_hash"}
        old_descriptions = {"doc.md": "Existing description"}
        provider = MockLLMProvider([])
        service = AIEnrichmentService(llm_provider=provider)

        result = service.enrich(files, old_descriptions, old_hints)

        assert len(provider.calls) == 0
        assert result.files_skipped == 1
        assert result.files_enriched == 0
        assert "doc.md" not in result.descriptions

    def test_enrich_calls_llm_for_changed_files(self) -> None:
        """Content_hash changed → LLM called with fresh description."""
        files = [_make_file("doc.md", content_hash="new_hash")]
        old_hints = {"doc.md": "old_hash"}
        old_descriptions = {"doc.md": "Old description"}
        responses = [_make_result("Updated description")]
        provider = MockLLMProvider(responses)
        service = AIEnrichmentService(llm_provider=provider)

        result = service.enrich(files, old_descriptions, old_hints)

        assert len(provider.calls) == 1
        assert result.descriptions["doc.md"] == "Updated description"
        assert result.files_enriched == 1

    def test_enrich_calls_llm_for_missing_descriptions(self) -> None:
        """Same content_hash but empty description → LLM called."""
        files = [_make_file("doc.md", content_hash="same_hash")]
        old_hints = {"doc.md": "same_hash"}
        old_descriptions = {"doc.md": ""}
        responses = [_make_result("New description")]
        provider = MockLLMProvider(responses)
        service = AIEnrichmentService(llm_provider=provider)

        result = service.enrich(files, old_descriptions, old_hints)

        assert len(provider.calls) == 1
        assert result.descriptions["doc.md"] == "New description"
        assert result.files_enriched == 1

    def test_enrich_calls_llm_for_new_files(self) -> None:
        """File not in old_hints → LLM called."""
        files = [_make_file("new.md", content_hash="brand_new")]
        responses = [_make_result("Brand new file description")]
        provider = MockLLMProvider(responses)
        service = AIEnrichmentService(llm_provider=provider)

        result = service.enrich(files, old_descriptions={}, old_hints={})

        assert len(provider.calls) == 1
        assert result.descriptions["new.md"] == "Brand new file description"
        assert result.files_enriched == 1

    def test_enrich_calls_llm_when_description_missing_from_dict(self) -> None:
        """Same content_hash, file path not in old_descriptions → LLM called."""
        files = [_make_file("doc.md", content_hash="same_hash")]
        old_hints = {"doc.md": "same_hash"}
        old_descriptions: dict[str, str] = {}  # Missing entirely
        responses = [_make_result("Generated description")]
        provider = MockLLMProvider(responses)
        service = AIEnrichmentService(llm_provider=provider)

        result = service.enrich(files, old_descriptions, old_hints)

        assert len(provider.calls) == 1
        assert result.files_enriched == 1


class TestGracefulFailure:
    """Tests for graceful per-file failure (AC5)."""

    def test_enrich_handles_llm_failure_gracefully(self) -> None:
        """LLM returns None → empty description, files_failed incremented."""
        files = [_make_file("fail.md")]
        provider = MockLLMProvider([None])
        service = AIEnrichmentService(llm_provider=provider)

        result = service.enrich(files, old_descriptions={}, old_hints={})

        assert result.descriptions["fail.md"] == ""
        assert result.files_failed == 1
        assert result.files_enriched == 0

    def test_enrich_continues_after_failure(self) -> None:
        """Failure on file 1, success on file 2 → both processed."""
        files = [_make_file("fail.md", "h1"), _make_file("ok.md", "h2")]
        responses = [None, _make_result("Success")]
        provider = MockLLMProvider(responses)
        service = AIEnrichmentService(llm_provider=provider)

        result = service.enrich(files, old_descriptions={}, old_hints={})

        assert result.descriptions["fail.md"] == ""
        assert result.descriptions["ok.md"] == "Success"
        assert result.files_failed == 1
        assert result.files_enriched == 1


class TestPromptConstruction:
    """Tests for prompt building (AC8)."""

    def test_build_user_prompt_includes_all_metadata(self) -> None:
        """Prompt should include path, lines, headings, first_paragraph."""
        file = _make_file(
            path="contracts/alpha.md",
            lines=142,
            headings=[
                HeadingInfo(level=1, text="Alpha Contract Overview"),
                HeadingInfo(level=2, text="Payment Terms"),
            ],
            first_paragraph="This document outlines the agreement.",
        )
        service = AIEnrichmentService(llm_provider=MockLLMProvider())

        prompt = service._build_user_prompt(file)

        assert "File: contracts/alpha.md" in prompt
        assert "Lines: 142" in prompt
        assert "Headings: Alpha Contract Overview, Payment Terms" in prompt
        assert "Content preview: This document outlines the agreement." in prompt

    def test_build_user_prompt_handles_missing_headings(self) -> None:
        """No headings → 'Headings:' line not included."""
        file = _make_file(path="flat.md", lines=10, headings=[])
        service = AIEnrichmentService(llm_provider=MockLLMProvider())

        prompt = service._build_user_prompt(file)

        assert "Headings:" not in prompt
        assert "File: flat.md" in prompt
        assert "Lines: 10" in prompt

    def test_build_user_prompt_handles_csv_columns(self) -> None:
        """Table columns should be included in prompt."""
        file = _make_file(
            path="data.csv",
            lines=500,
            table_columns=["id", "name", "amount"],
        )
        service = AIEnrichmentService(llm_provider=MockLLMProvider())

        prompt = service._build_user_prompt(file)

        assert "Table columns: id, name, amount" in prompt

    def test_build_user_prompt_limits_headings_to_five(self) -> None:
        """Only first 5 headings should be included."""
        headings = [HeadingInfo(level=1, text=f"H{i}") for i in range(8)]
        file = _make_file(path="big.md", headings=headings)
        service = AIEnrichmentService(llm_provider=MockLLMProvider())

        prompt = service._build_user_prompt(file)

        assert "H0, H1, H2, H3, H4" in prompt
        assert "H5" not in prompt

    def test_system_prompt_used_in_llm_call(self) -> None:
        """Verify system prompt is the enrichment constant."""
        files = [_make_file("doc.md")]
        responses = [_make_result("Desc")]
        provider = MockLLMProvider(responses)
        service = AIEnrichmentService(llm_provider=provider)

        service.enrich(files, old_descriptions={}, old_hints={})

        assert provider.calls[0][0] == ENRICHMENT_SYSTEM_PROMPT


class TestSanitization:
    """Tests for description sanitization."""

    def test_sanitize_removes_pipe_chars(self) -> None:
        """Pipe characters should be replaced with dashes."""
        service = AIEnrichmentService(llm_provider=MockLLMProvider())

        result = service._sanitize_description("Alpha | Beta | Gamma overview")

        assert "|" not in result
        assert "Alpha - Beta - Gamma overview" == result

    def test_sanitize_truncates_to_10_words(self) -> None:
        """Descriptions longer than 10 words should be truncated."""
        service = AIEnrichmentService(llm_provider=MockLLMProvider())
        long_text = " ".join(f"word{i}" for i in range(20))

        result = service._sanitize_description(long_text)

        assert len(result.split()) == 10

    def test_sanitize_strips_quotes(self) -> None:
        """Leading/trailing quotes should be removed."""
        service = AIEnrichmentService(llm_provider=MockLLMProvider())

        assert service._sanitize_description('"A quoted description"') == "A quoted description"
        assert service._sanitize_description("'Single quoted'") == "Single quoted"

    def test_sanitize_strips_whitespace(self) -> None:
        """Leading/trailing whitespace should be removed."""
        service = AIEnrichmentService(llm_provider=MockLLMProvider())

        assert service._sanitize_description("  spaces around  ") == "spaces around"

    def test_sanitize_replaces_newlines(self) -> None:
        """Newlines in LLM output should be replaced with spaces."""
        service = AIEnrichmentService(llm_provider=MockLLMProvider())

        assert service._sanitize_description("Line one\nLine two") == "Line one Line two"
        assert service._sanitize_description("A\n\nB") == "A  B"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_enrich_empty_file_list(self) -> None:
        """No files → empty result, zero tokens."""
        provider = MockLLMProvider()
        service = AIEnrichmentService(llm_provider=provider)

        result = service.enrich([], old_descriptions={}, old_hints={})

        assert result.descriptions == {}
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.files_enriched == 0
        assert result.files_skipped == 0
        assert result.files_failed == 0
        assert len(provider.calls) == 0

    def test_enrich_all_files_cached(self) -> None:
        """All unchanged → zero LLM calls, zero tokens."""
        files = [
            _make_file("a.md", content_hash="h1"),
            _make_file("b.md", content_hash="h2"),
        ]
        old_hints = {"a.md": "h1", "b.md": "h2"}
        old_descriptions = {"a.md": "Desc A", "b.md": "Desc B"}
        provider = MockLLMProvider()
        service = AIEnrichmentService(llm_provider=provider)

        result = service.enrich(files, old_descriptions, old_hints)

        assert len(provider.calls) == 0
        assert result.files_skipped == 2
        assert result.files_enriched == 0
        assert result.prompt_tokens == 0

    def test_enrich_mixed_cached_and_new(self) -> None:
        """Mix of cached and new files → only new files get LLM calls."""
        files = [
            _make_file("cached.md", content_hash="h1"),
            _make_file("new.md", content_hash="h2"),
        ]
        old_hints = {"cached.md": "h1"}
        old_descriptions = {"cached.md": "Existing desc"}
        responses = [_make_result("New file desc")]
        provider = MockLLMProvider(responses)
        service = AIEnrichmentService(llm_provider=provider)

        result = service.enrich(files, old_descriptions, old_hints)

        assert len(provider.calls) == 1
        assert result.files_skipped == 1
        assert result.files_enriched == 1
        assert result.descriptions["new.md"] == "New file desc"
        assert "cached.md" not in result.descriptions

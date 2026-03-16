"""Tests for AIGlossaryService (unified per-document pipeline)."""

from __future__ import annotations

from pathlib import Path

from nest.core.models import AIGlossaryResult, LLMCompletionResult
from nest.services.ai_glossary_service import (
    GLOSSARY_HEADER,
    GLOSSARY_TABLE_HEADER,
    AIGlossaryService,
)

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockLLMProvider:
    """Mock LLM provider for testing AI glossary."""

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


class MockFileSystem:
    """Mock filesystem for glossary file I/O testing."""

    def __init__(self, files: dict[str, str] | None = None) -> None:
        self._files: dict[str, str] = files or {}

    def exists(self, path: Path) -> bool:
        return str(path) in self._files

    def read_text(self, path: Path) -> str:
        if str(path) not in self._files:
            raise FileNotFoundError(str(path))
        return self._files[str(path)]

    def write_text(self, path: Path, content: str) -> None:
        self._files[str(path)] = content

    def get_content(self, path: Path) -> str:
        """Helper for tests to inspect written content."""
        return self._files.get(str(path), "")


def _make_llm_table_response(
    rows: list[str],
    prompt_tokens: int = 100,
    completion_tokens: int = 20,
) -> LLMCompletionResult:
    """Helper to create an LLMCompletionResult with table row text."""
    text = "\n".join(rows)
    return LLMCompletionResult(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


GLOSSARY_PATH = Path("/project/_nest_context/glossary.md")
CONTEXT_DIR = Path("/project/_nest_context")


def _existing_glossary_content(*rows: str) -> str:
    """Build a glossary.md string with given table rows."""
    row_text = "\n".join(rows) + "\n" if rows else ""
    return (
        GLOSSARY_HEADER
        + "<!-- nest:glossary-start -->\n"
        + GLOSSARY_TABLE_HEADER
        + "\n"
        + row_text
        + "<!-- nest:glossary-end -->\n"
    )


def _make_file(fs: MockFileSystem, name: str, content: str) -> Path:
    """Register a file in mock FS and return its path."""
    path = CONTEXT_DIR / name
    fs._files[str(path)] = content
    return path


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestGenerateNewTerms:
    """Tests for glossary generation with new terms from documents."""

    def test_single_file_extraction(self) -> None:
        """Single file -> LLM called once -> glossary rows created."""
        fs = MockFileSystem()
        file_path = _make_file(fs, "doc.md", "The PDC board meets weekly.")
        responses = [
            _make_llm_table_response(
                [
                    "| PDC | Acronym | Project Delivery Committee, the governance board. |",
                ]
            ),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        result = service.generate([file_path], CONTEXT_DIR, GLOSSARY_PATH)

        assert result.terms_added == 1
        assert result.files_processed == 1
        assert result.chunks_processed == 1
        assert len(provider.calls) == 1
        content = fs.get_content(GLOSSARY_PATH)
        assert "PDC" in content
        assert "doc.md" in content  # Source(s) column

    def test_multiple_files(self) -> None:
        """Multiple files -> separate LLM calls, all terms merged."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "a.md", "The PDC board.")
        f2 = _make_file(fs, "b.md", "ACME Corp partnership.")
        responses = [
            _make_llm_table_response(["| PDC | Acronym | Project Delivery Committee. |"]),
            _make_llm_table_response(["| ACME | Organization | The client organization. |"]),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        result = service.generate([f1, f2], CONTEXT_DIR, GLOSSARY_PATH)

        assert result.terms_added == 2
        assert result.files_processed == 2
        assert len(provider.calls) == 2
        content = fs.get_content(GLOSSARY_PATH)
        assert "PDC" in content
        assert "ACME" in content

    def test_token_counts_accumulated(self) -> None:
        """Token counts aggregated across files and chunks."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "a.md", "Content A")
        f2 = _make_file(fs, "b.md", "Content B")
        responses = [
            _make_llm_table_response(
                ["| PDC | Acronym | Def. |"],
                prompt_tokens=50,
                completion_tokens=5,
            ),
            _make_llm_table_response(
                ["| ACME | Organization | Def. |"],
                prompt_tokens=60,
                completion_tokens=8,
            ),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        result = service.generate([f1, f2], CONTEXT_DIR, GLOSSARY_PATH)

        assert result.prompt_tokens == 110
        assert result.completion_tokens == 13
        assert result.terms_added == 2


class TestIncrementalLogic:
    """Tests for dedup against existing glossary (AC3, AC7)."""

    def test_existing_terms_skipped(self) -> None:
        """Terms already in glossary.md -> skipped."""
        existing_content = _existing_glossary_content(
            "| PDC | Abbreviation | Existing definition. | a.md |"
        )
        fs = MockFileSystem({str(GLOSSARY_PATH): existing_content})
        f1 = _make_file(fs, "doc.md", "The PDC board meets.")
        responses = [
            _make_llm_table_response(["| PDC | Acronym | New def (should skip). |"]),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        result = service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        assert result.terms_skipped_existing == 1
        assert result.terms_added == 0
        content = fs.get_content(GLOSSARY_PATH)
        assert "Existing definition." in content

    def test_cross_file_dedup(self) -> None:
        """Same term from two files -> kept once (first definition wins)."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "a.md", "PDC meeting")
        f2 = _make_file(fs, "b.md", "PDC review")
        responses = [
            _make_llm_table_response(["| PDC | Acronym | First definition. |"]),
            _make_llm_table_response(["| PDC | Acronym | Second definition. |"]),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        result = service.generate([f1, f2], CONTEXT_DIR, GLOSSARY_PATH)

        assert result.terms_added == 1
        assert result.terms_skipped_existing == 1
        content = fs.get_content(GLOSSARY_PATH)
        assert "First definition." in content

    def test_case_insensitive_dedup(self) -> None:
        """Dedup is case-insensitive."""
        existing_content = _existing_glossary_content("| pdc | Abbreviation | Existing. | a.md |")
        fs = MockFileSystem({str(GLOSSARY_PATH): existing_content})
        f1 = _make_file(fs, "doc.md", "The PDC board.")
        responses = [
            _make_llm_table_response(["| PDC | Acronym | New def. |"]),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        result = service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        assert result.terms_skipped_existing == 1
        assert result.terms_added == 0


class TestGracefulFailure:
    """Tests for graceful per-file failure (AC8)."""

    def test_llm_failure_increments_terms_failed(self) -> None:
        """LLM returns None -> terms_failed incremented."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "doc.md", "Some content.")
        provider = MockLLMProvider([None])
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        result = service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        assert result.terms_failed == 1
        assert result.terms_added == 0

    def test_continues_after_failure(self) -> None:
        """Failure on file 1, success on file 2."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "fail.md", "Will fail.")
        f2 = _make_file(fs, "ok.md", "Will succeed.")
        responses: list[LLMCompletionResult | None] = [
            None,
            _make_llm_table_response(["| ACME | Organization | The client. |"]),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        result = service.generate([f1, f2], CONTEXT_DIR, GLOSSARY_PATH)

        assert result.terms_failed == 1
        assert result.terms_added == 1

    def test_malformed_llm_output_skipped(self) -> None:
        """Lines without enough pipes are skipped gracefully."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "doc.md", "Content")
        responses = [
            _make_llm_table_response(
                [
                    "This is just random text",
                    "| Missing columns |",
                    "| PDC | Acronym | Valid definition. |",
                ]
            ),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        result = service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        assert result.terms_added == 1

    def test_empty_document_no_llm_call(self) -> None:
        """Empty file content -> no LLM call."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "empty.md", "   ")
        provider = MockLLMProvider([])
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        result = service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        assert len(provider.calls) == 0
        assert result.files_processed == 1


class TestHumanEditPreservation:
    """Tests for human edit preservation (AC3)."""

    def test_preserves_existing_definitions(self) -> None:
        """Existing rows untouched after adding new terms."""
        existing_row = "| Alpha | Domain Term | Human-written definition. | alpha.md |"
        existing_content = _existing_glossary_content(existing_row)
        fs = MockFileSystem({str(GLOSSARY_PATH): existing_content})
        f1 = _make_file(fs, "doc.md", "Bravo protocol")
        responses = [
            _make_llm_table_response(["| Bravo | Domain Term | A new term. |"]),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        content = fs.get_content(GLOSSARY_PATH)
        assert "Human-written definition." in content
        assert "A new term." in content

    def test_sorts_terms_alphabetically(self) -> None:
        """Merged output sorted by term."""
        existing_row = "| Charlie | Domain Term | Charlie def. | c.md |"
        existing_content = _existing_glossary_content(existing_row)
        fs = MockFileSystem({str(GLOSSARY_PATH): existing_content})
        f1 = _make_file(fs, "doc.md", "Alpha and Echo")
        responses = [
            _make_llm_table_response(
                [
                    "| Alpha | Domain Term | Alpha def. |",
                    "| Echo | Domain Term | Echo def. |",
                ]
            ),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        content = fs.get_content(GLOSSARY_PATH)
        lines = [
            row
            for row in content.splitlines()
            if row.startswith("| ") and not row.startswith("| Term") and "---" not in row
        ]
        term_names = [row.split("|")[1].strip() for row in lines]
        assert term_names == ["Alpha", "Charlie", "Echo"]


class TestFirstRunCreation:
    """Tests for first-run glossary creation (AC13)."""

    def test_creates_glossary_when_not_exists(self) -> None:
        """File created with header + markers."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "doc.md", "PDC content")
        responses = [
            _make_llm_table_response(["| PDC | Acronym | Project Delivery Committee. |"]),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        content = fs.get_content(GLOSSARY_PATH)
        assert "# Project Glossary" in content
        assert "<!-- nest:glossary-start -->" in content
        assert "<!-- nest:glossary-end -->" in content
        assert "| Term | Category | Definition | Source(s) |" in content
        assert "PDC" in content


class TestNoOpConditions:
    """Tests for no-op conditions (AC5)."""

    def test_no_changed_files_immediate_return(self) -> None:
        """Empty changed_files -> empty result, zero tokens."""
        provider = MockLLMProvider([])
        fs = MockFileSystem()
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        result = service.generate([], CONTEXT_DIR, GLOSSARY_PATH)

        assert result == AIGlossaryResult()
        assert len(provider.calls) == 0


class TestSourceColumn:
    """Tests for Source(s) column population (AC2)."""

    def test_source_populated_with_filename(self) -> None:
        """Source(s) column populated with relative filename."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "contracts/alpha.md", "PDC content")
        responses = [
            _make_llm_table_response(["| PDC | Acronym | Def. |"]),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        content = fs.get_content(GLOSSARY_PATH)
        assert "contracts/alpha.md" in content


class TestCategoryValidation:
    """Tests for category validation (AC12)."""

    def test_valid_categories_preserved(self) -> None:
        """Valid categories remain as-is."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "doc.md", "Content")
        responses = [
            _make_llm_table_response(
                [
                    "| PDC | Acronym | Def1. |",
                    "| ACME | Organization | Def2. |",
                    "| Widget | Product/Platform | Def3. |",
                ]
            ),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        result = service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        assert result.terms_added == 3
        content = fs.get_content(GLOSSARY_PATH)
        assert "Acronym" in content
        assert "Organization" in content
        assert "Product/Platform" in content

    def test_invalid_category_defaults_to_domain_term(self) -> None:
        """Unknown category defaults to Domain Term."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "doc.md", "Content")
        responses = [
            _make_llm_table_response(["| PDC | UnknownCat | Some definition. |"]),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        content = fs.get_content(GLOSSARY_PATH)
        assert "Domain Term" in content


class TestPromptConstruction:
    """Tests for system prompt construction (AC12)."""

    def test_system_prompt_without_context(self) -> None:
        """Without project context, placeholder replaced with empty string."""
        prompt = AIGlossaryService._build_system_prompt()
        assert "{PROJECT_CONTEXT_BLOCK}" not in prompt
        assert "Project context:" not in prompt

    def test_system_prompt_with_context(self) -> None:
        """With project context, block inserted."""
        prompt = AIGlossaryService._build_system_prompt("This is a billing project.")
        assert "Project context:" in prompt
        assert "This is a billing project." in prompt

    def test_system_prompt_used_in_llm_call(self) -> None:
        """Verify LLM receives the system prompt."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "doc.md", "Content")
        responses = [_make_llm_table_response(["| PDC | Acronym | Def. |"])]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        system_prompt_sent = provider.calls[0][0]
        assert "technical glossary assistant" in system_prompt_sent
        assert "Categories:" in system_prompt_sent


class TestChunking:
    """Tests for _chunk_content() boundary conditions (AC6)."""

    def test_under_limit_single_chunk(self) -> None:
        """Content under limit -> single chunk."""
        content = "Short content"
        chunks = AIGlossaryService._chunk_content(content, max_chars=100)
        assert len(chunks) == 1
        assert chunks[0] == content

    def test_over_limit_splits_on_paragraphs(self) -> None:
        """Content over limit -> split on double-newline."""
        p1 = "A" * 50
        p2 = "B" * 50
        p3 = "C" * 50
        content = f"{p1}\n\n{p2}\n\n{p3}"
        chunks = AIGlossaryService._chunk_content(content, max_chars=110)
        assert len(chunks) >= 2
        # All content should be preserved
        reconstructed = "\n\n".join(chunks)
        assert p1 in reconstructed
        assert p2 in reconstructed
        assert p3 in reconstructed

    def test_single_huge_paragraph_own_chunk(self) -> None:
        """Single paragraph larger than max_chars goes in its own chunk."""
        huge = "X" * 200
        content = f"short\n\n{huge}\n\nshort2"
        chunks = AIGlossaryService._chunk_content(content, max_chars=50)
        assert any(huge in c for c in chunks)

    def test_chunked_file_dedup_across_chunks(self) -> None:
        """Terms from multiple chunks of same file are deduplicated."""
        from unittest.mock import patch

        fs = MockFileSystem()
        big_content = ("A" * 100) + "\n\n" + ("B" * 100)
        f1 = _make_file(fs, "big.md", big_content)
        responses = [
            _make_llm_table_response(["| PDC | Acronym | Chunk 1 def. |"]),
            _make_llm_table_response(["| PDC | Acronym | Chunk 2 def. |"]),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        # Force chunking by patching _chunk_content to split into two chunks
        with patch.object(
            AIGlossaryService,
            "_chunk_content",
            return_value=["A" * 100, "B" * 100],
        ):
            result = service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        assert result.terms_added == 1
        assert result.terms_skipped_existing == 1
        content = fs.get_content(GLOSSARY_PATH)
        assert "Chunk 1 def." in content


class TestResponseParsing:
    """Tests for _parse_table_rows() parsing."""

    def test_parse_valid_rows(self) -> None:
        """Standard table rows parsed correctly."""
        text = (
            "| PDC | Acronym | Project Delivery Committee. |\n| ACME | Organization | The client. |"
        )
        results = AIGlossaryService._parse_table_rows(text)
        assert len(results) == 2
        assert results[0] == ("PDC", "Acronym", "Project Delivery Committee.")
        assert results[1] == ("ACME", "Organization", "The client.")

    def test_parse_skips_header_separator(self) -> None:
        """Header and separator rows are skipped."""
        text = (
            "| Term | Category | Definition |\n"
            "|------|----------|------------|\n"
            "| PDC | Acronym | Def. |"
        )
        results = AIGlossaryService._parse_table_rows(text)
        assert len(results) == 1
        assert results[0][0] == "PDC"

    def test_parse_skips_malformed(self) -> None:
        """Lines without enough pipes are skipped."""
        text = "Some random text\n| Only two |\n| PDC | Acronym | Valid. |"
        results = AIGlossaryService._parse_table_rows(text)
        assert len(results) == 1


class TestSanitization:
    """Tests for definition sanitization."""

    def test_sanitize_removes_pipe_chars(self) -> None:
        """| replaced with -."""
        result = AIGlossaryService._sanitize_definition("Alpha | Beta | Gamma")
        assert "|" not in result
        assert result == "Alpha - Beta - Gamma"

    def test_sanitize_replaces_newlines(self) -> None:
        """newline replaced with space."""
        result = AIGlossaryService._sanitize_definition("Line one\nLine two")
        assert result == "Line one Line two"

    def test_sanitize_strips_quotes(self) -> None:
        """Leading/trailing quotes removed."""
        assert AIGlossaryService._sanitize_definition('"Quoted def"') == "Quoted def"
        assert AIGlossaryService._sanitize_definition("'Single quoted'") == "Single quoted"


class TestGlossaryFileIO:
    """Tests for glossary file I/O."""

    def test_write_glossary_creates_correct_format(self) -> None:
        """Header, markers, table format all present."""
        fs = MockFileSystem()
        f1 = _make_file(fs, "doc.md", "Content")
        responses = [
            _make_llm_table_response(["| PDC | Acronym | Project Delivery Committee. |"]),
        ]
        provider = MockLLMProvider(responses)
        service = AIGlossaryService(llm_provider=provider, filesystem=fs)

        service.generate([f1], CONTEXT_DIR, GLOSSARY_PATH)

        content = fs.get_content(GLOSSARY_PATH)
        assert content.startswith("# Project Glossary")
        assert "<!-- nest:glossary-start -->" in content
        assert "<!-- nest:glossary-end -->" in content
        assert "| Term | Category | Definition | Source(s) |" in content
        assert "|------|----------|------------|-----------|" in content

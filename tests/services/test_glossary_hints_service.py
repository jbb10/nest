"""Tests for GlossaryHintsService."""

from pathlib import Path
from unittest.mock import Mock

import yaml

from conftest import MockFileSystem
from nest.adapters.protocols import FileSystemProtocol
from nest.core.models import CandidateTerm, GlossaryHints
from nest.services.glossary_hints_service import (
    GENERIC_TERM_FILTER,
    GlossaryHintsService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _service(fs: FileSystemProtocol | None = None) -> GlossaryHintsService:
    return GlossaryHintsService(
        filesystem=fs or Mock(spec=FileSystemProtocol),
        project_root=Path("/app"),
    )


# ---------------------------------------------------------------------------
# extract_terms_from_file — abbreviation detection
# ---------------------------------------------------------------------------


class TestAbbreviationDetection:
    """Tests for abbreviation pattern detection."""

    def test_detects_uppercase_abbreviations(self):
        """PDC, SOW, SME should be detected as abbreviations."""
        svc = _service()
        content = "The PDC meets weekly. SOW is signed. SME reviews the PDC output."
        terms = svc.extract_terms_from_file(Path("doc.md"), content)
        names = {t.term for t in terms}
        assert "PDC" in names
        assert "SOW" in names
        assert "SME" in names

    def test_filters_generic_abbreviations(self):
        """API, URL, PDF should be filtered by GENERIC_TERM_FILTER."""
        svc = _service()
        content = "The API uses REST over HTTP. Download the PDF via URL."
        terms = svc.extract_terms_from_file(Path("doc.md"), content)
        names = {t.term for t in terms}
        assert "API" not in names
        assert "REST" not in names
        assert "HTTP" not in names
        assert "PDF" not in names
        assert "URL" not in names

    def test_occurrence_counting(self):
        """Occurrences should count matches within the file."""
        svc = _service()
        content = "PDC meets weekly. The PDC board. PDC review."
        terms = svc.extract_terms_from_file(Path("doc.md"), content)
        pdc = next(t for t in terms if t.term == "PDC")
        assert pdc.occurrences == 3

    def test_abbreviation_category(self):
        """Abbreviations should have category='abbreviation'."""
        svc = _service()
        content = "The XYZ committee meets monthly."
        terms = svc.extract_terms_from_file(Path("doc.md"), content)
        xyz = next(t for t in terms if t.term == "XYZ")
        assert xyz.category == "abbreviation"


# ---------------------------------------------------------------------------
# extract_terms_from_file — proper noun detection
# ---------------------------------------------------------------------------


class TestProperNounDetection:
    """Tests for proper noun (capitalized multi-word) detection."""

    def test_detects_proper_nouns(self):
        """Capitalized multi-word sequences after lowercase/punctuation detected."""
        svc = _service()
        content = "the lead is Sarah Mitchell on this project."
        terms = svc.extract_terms_from_file(Path("doc.md"), content)
        names = {t.term for t in terms}
        assert "Sarah Mitchell" in names

    def test_proper_noun_category(self):
        """Proper nouns should have category='proper_noun'."""
        svc = _service()
        content = "reports to John Smith regularly."
        terms = svc.extract_terms_from_file(Path("doc.md"), content)
        js = next(t for t in terms if t.term == "John Smith")
        assert js.category == "proper_noun"


# ---------------------------------------------------------------------------
# Context snippet extraction
# ---------------------------------------------------------------------------


class TestContextSnippets:
    """Tests for context snippet extraction and truncation."""

    def test_snippets_truncated_to_100_chars(self):
        """Context snippets must not exceed 100 characters."""
        svc = _service()
        long_sentence = "A" * 200 + " XYZ " + "B" * 200 + "."
        terms = svc.extract_terms_from_file(Path("doc.md"), long_sentence)
        for t in terms:
            for s in t.context_snippets:
                assert len(s) <= 100

    def test_max_three_snippets(self):
        """At most 3 context snippets per term."""
        svc = _service()
        content = ". ".join([f"The XYZ group met {i}" for i in range(10)]) + "."
        terms = svc.extract_terms_from_file(Path("doc.md"), content)
        xyz = next(t for t in terms if t.term == "XYZ")
        assert len(xyz.context_snippets) <= 3


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and empty/no-term inputs."""

    def test_empty_file_produces_no_terms(self):
        """Empty content returns empty list."""
        svc = _service()
        terms = svc.extract_terms_from_file(Path("empty.md"), "")
        assert terms == []

    def test_whitespace_only_produces_no_terms(self):
        """Whitespace-only content returns empty list."""
        svc = _service()
        terms = svc.extract_terms_from_file(Path("ws.md"), "   \n\n  \t ")
        assert terms == []

    def test_no_qualifying_terms(self):
        """Content without abbreviations or proper nouns returns empty."""
        svc = _service()
        content = "this is all lowercase text with no relevant patterns."
        terms = svc.extract_terms_from_file(Path("doc.md"), content)
        assert terms == []


# ---------------------------------------------------------------------------
# extract_all — occurrence thresholds
# ---------------------------------------------------------------------------


class TestOccurrenceThresholds:
    """Tests for occurrence threshold filtering in extract_all."""

    def test_abbreviations_below_threshold_filtered(self):
        """Abbreviations with < 2 occurrences should be filtered out."""
        fs = MockFileSystem()
        fs.file_contents[Path("/app/_nest_context/doc.md")] = "The XYZ thing."

        # Add list_files support
        fs.list_files = lambda d: [Path("/app/_nest_context/doc.md")]
        svc = GlossaryHintsService(filesystem=fs, project_root=Path("/app"))
        result = svc.extract_all(Path("/app/_nest_context"))
        # XYZ appears only once → filtered
        names = {t.term for t in result.terms}
        assert "XYZ" not in names

    def test_abbreviations_at_threshold_included(self):
        """Abbreviations with >= 2 occurrences should be included."""
        fs = MockFileSystem()
        fs.file_contents[Path("/app/_nest_context/doc.md")] = "The XYZ met. XYZ again."
        fs.list_files = lambda d: [Path("/app/_nest_context/doc.md")]
        svc = GlossaryHintsService(filesystem=fs, project_root=Path("/app"))
        result = svc.extract_all(Path("/app/_nest_context"))
        names = {t.term for t in result.terms}
        assert "XYZ" in names


# ---------------------------------------------------------------------------
# extract_all — incremental processing
# ---------------------------------------------------------------------------


class TestIncrementalProcessing:
    """Tests for incremental (changed_files) processing."""

    def test_skips_unchanged_files(self):
        """Files not in changed_files set should not be scanned."""
        fs = MockFileSystem()
        fs.file_contents[Path("/app/_nest_context/old.md")] = "PDC PDC PDC"
        fs.file_contents[Path("/app/_nest_context/new.md")] = "XYZ XYZ"
        fs.list_files = lambda d: [
            Path("/app/_nest_context/old.md"),
            Path("/app/_nest_context/new.md"),
        ]
        svc = GlossaryHintsService(filesystem=fs, project_root=Path("/app"))
        result = svc.extract_all(Path("/app/_nest_context"), changed_files={"new.md"})
        names = {t.term for t in result.terms}
        assert "XYZ" in names
        assert "PDC" not in names  # old.md was skipped

    def test_scans_all_when_changed_files_none(self):
        """When changed_files is None, all files are scanned."""
        fs = MockFileSystem()
        fs.file_contents[Path("/app/_nest_context/a.md")] = "PDC PDC"
        fs.file_contents[Path("/app/_nest_context/b.md")] = "XYZ XYZ"
        fs.list_files = lambda d: [
            Path("/app/_nest_context/a.md"),
            Path("/app/_nest_context/b.md"),
        ]
        svc = GlossaryHintsService(filesystem=fs, project_root=Path("/app"))
        result = svc.extract_all(Path("/app/_nest_context"), changed_files=None)
        names = {t.term for t in result.terms}
        assert "PDC" in names
        assert "XYZ" in names


# ---------------------------------------------------------------------------
# Deduplication across files
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Tests for term deduplication across multiple files."""

    def test_same_term_multiple_files(self):
        """Same term from different files should be one entry with both sources."""
        fs = MockFileSystem()
        fs.file_contents[Path("/app/_nest_context/a.md")] = "PDC meeting."
        fs.file_contents[Path("/app/_nest_context/b.md")] = "PDC review."
        fs.list_files = lambda d: [
            Path("/app/_nest_context/a.md"),
            Path("/app/_nest_context/b.md"),
        ]
        svc = GlossaryHintsService(filesystem=fs, project_root=Path("/app"))
        result = svc.extract_all(Path("/app/_nest_context"))
        pdc_terms = [t for t in result.terms if t.term == "PDC"]
        assert len(pdc_terms) == 1
        assert pdc_terms[0].occurrences == 2
        assert "a.md" in pdc_terms[0].source_files
        assert "b.md" in pdc_terms[0].source_files


# ---------------------------------------------------------------------------
# load_previous_hints / write_hints round-trip
# ---------------------------------------------------------------------------


class TestHintsRoundTrip:
    """Tests for hints YAML writing and reading."""

    def test_write_and_load_round_trip(self):
        """Written hints should be loadable back."""
        fs = MockFileSystem()
        fs.existing_paths.add(Path("/app/.nest"))
        svc = GlossaryHintsService(filesystem=fs, project_root=Path("/app"))

        hints = GlossaryHints(
            terms=[
                CandidateTerm(
                    term="PDC",
                    category="abbreviation",
                    occurrences=5,
                    source_files=["alpha.md", "beta.md"],
                    context_snippets=["The PDC board meets weekly"],
                ),
            ]
        )
        hints_path = Path("/app/.nest/00_GLOSSARY_HINTS.yaml")
        svc.write_hints(hints, hints_path)

        # Now load back
        written_content = fs.written_files[hints_path]
        fs.file_contents[hints_path] = written_content
        fs.existing_paths.add(hints_path)

        loaded = svc.load_previous_hints(hints_path)
        assert loaded is not None
        assert len(loaded.terms) == 1
        assert loaded.terms[0].term == "PDC"
        assert loaded.terms[0].category == "abbreviation"
        assert loaded.terms[0].occurrences == 5
        assert loaded.terms[0].source_files == ["alpha.md", "beta.md"]

    def test_corrupt_yaml_returns_none(self):
        """Corrupt YAML should return None gracefully."""
        fs = MockFileSystem()
        fs.existing_paths.add(Path("/app/.nest/hints.yaml"))
        fs.file_contents[Path("/app/.nest/hints.yaml")] = "{{invalid yaml::"
        svc = GlossaryHintsService(filesystem=fs, project_root=Path("/app"))
        result = svc.load_previous_hints(Path("/app/.nest/hints.yaml"))
        assert result is None

    def test_invalid_structure_returns_none(self):
        """YAML without 'terms' key should return None."""
        fs = MockFileSystem()
        path = Path("/app/.nest/hints.yaml")
        fs.existing_paths.add(path)
        fs.file_contents[path] = yaml.safe_dump({"other_key": "value"})
        svc = GlossaryHintsService(filesystem=fs, project_root=Path("/app"))
        result = svc.load_previous_hints(path)
        assert result is None

    def test_nonexistent_file_returns_none(self):
        """Non-existent hints file should return None."""
        fs = MockFileSystem()
        svc = GlossaryHintsService(filesystem=fs, project_root=Path("/app"))
        result = svc.load_previous_hints(Path("/app/.nest/missing.yaml"))
        assert result is None

    def test_write_creates_parent_directory(self):
        """write_hints should create parent directory if it doesn't exist."""
        fs = MockFileSystem()
        svc = GlossaryHintsService(filesystem=fs, project_root=Path("/app"))
        hints = GlossaryHints(terms=[])
        svc.write_hints(hints, Path("/app/.nest/00_GLOSSARY_HINTS.yaml"))
        assert Path("/app/.nest") in fs.created_dirs

    def test_write_includes_header_comment(self):
        """Written YAML should start with auto-generated header."""
        fs = MockFileSystem()
        fs.existing_paths.add(Path("/app/.nest"))
        svc = GlossaryHintsService(filesystem=fs, project_root=Path("/app"))
        hints = GlossaryHints(terms=[])
        path = Path("/app/.nest/00_GLOSSARY_HINTS.yaml")
        svc.write_hints(hints, path)
        content = fs.written_files[path]
        assert "Auto-generated by nest sync" in content


# ---------------------------------------------------------------------------
# merge_with_previous
# ---------------------------------------------------------------------------


class TestMergeWithPrevious:
    """Tests for merge_with_previous logic."""

    def test_first_run_returns_new_hints(self):
        """When old_hints is None, returns new_hints unchanged."""
        svc = _service()
        new = GlossaryHints(
            terms=[
                CandidateTerm(
                    term="PDC",
                    category="abbreviation",
                    occurrences=3,
                    source_files=["doc.md"],
                    context_snippets=["The PDC board"],
                )
            ]
        )
        merged = svc.merge_with_previous(new, None, set())
        assert len(merged.terms) == 1
        assert merged.terms[0].term == "PDC"

    def test_carries_forward_unchanged_files(self):
        """Terms from files not in new extraction are carried forward."""
        svc = _service()
        old = GlossaryHints(
            terms=[
                CandidateTerm(
                    term="OLD",
                    category="abbreviation",
                    occurrences=2,
                    source_files=["old.md"],
                    context_snippets=["old context"],
                )
            ]
        )
        new = GlossaryHints(
            terms=[
                CandidateTerm(
                    term="NEW",
                    category="abbreviation",
                    occurrences=2,
                    source_files=["new.md"],
                    context_snippets=["new context"],
                )
            ]
        )
        merged = svc.merge_with_previous(new, old, set())
        names = {t.term for t in merged.terms}
        assert "OLD" in names
        assert "NEW" in names

    def test_removes_terms_from_deleted_files(self):
        """Terms whose only source file was deleted should be removed."""
        svc = _service()
        old = GlossaryHints(
            terms=[
                CandidateTerm(
                    term="GONE",
                    category="abbreviation",
                    occurrences=2,
                    source_files=["deleted.md"],
                    context_snippets=["gone context"],
                )
            ]
        )
        new = GlossaryHints(terms=[])
        merged = svc.merge_with_previous(new, old, {"deleted.md"})
        names = {t.term for t in merged.terms}
        assert "GONE" not in names

    def test_merges_terms_across_old_and_new(self):
        """Same term from old (unchanged file) and new file → merged."""
        svc = _service()
        old = GlossaryHints(
            terms=[
                CandidateTerm(
                    term="PDC",
                    category="abbreviation",
                    occurrences=3,
                    source_files=["old.md"],
                    context_snippets=["old PDC context"],
                )
            ]
        )
        new = GlossaryHints(
            terms=[
                CandidateTerm(
                    term="PDC",
                    category="abbreviation",
                    occurrences=2,
                    source_files=["new.md"],
                    context_snippets=["new PDC context"],
                )
            ]
        )
        merged = svc.merge_with_previous(new, old, set())
        pdc = [t for t in merged.terms if t.term == "PDC"]
        assert len(pdc) == 1
        assert pdc[0].occurrences == 5
        assert "old.md" in pdc[0].source_files
        assert "new.md" in pdc[0].source_files


# ---------------------------------------------------------------------------
# Generic term filter
# ---------------------------------------------------------------------------


class TestGenericTermFilter:
    """Tests for the GENERIC_TERM_FILTER constant."""

    def test_common_tech_abbreviations_in_filter(self):
        """Well-known tech abbreviations should be in the filter."""
        for term in ["API", "URL", "PDF", "SQL", "HTML", "CSS", "JSON", "YAML", "HTTP"]:
            assert term in GENERIC_TERM_FILTER

    def test_filter_is_set(self):
        """GENERIC_TERM_FILTER should be a set for O(1) lookups."""
        assert isinstance(GENERIC_TERM_FILTER, set)

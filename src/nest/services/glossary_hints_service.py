"""Service for extracting candidate glossary terms from context files.

Scans text files in the context directory for abbreviations, proper nouns,
and repeated domain terms. Produces hints for the glossary agent.
"""

import logging
import re
from pathlib import Path

import yaml

from nest.adapters.protocols import FileSystemProtocol
from nest.core.models import CandidateTerm, GlossaryHints
from nest.core.paths import (
    CONTEXT_TEXT_EXTENSIONS,
    GLOSSARY_HINTS_FILE,
    INDEX_HINTS_FILE,
    MASTER_INDEX_FILE,
)

logger = logging.getLogger(__name__)

# Regex patterns for term extraction
ABBREVIATION_PATTERN = re.compile(r"\b[A-Z]{2,}\b")

# Proper noun: capitalized multi-word sequences not at sentence start.
# Requires a lowercase char or punctuation before the name.
PROPER_NOUN_PATTERN = re.compile(r"(?<=[a-z.,:;]\s)([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)")

# Common generic abbreviations to filter out — not project-specific
GENERIC_TERM_FILTER = {
    "API",
    "URL",
    "PDF",
    "SQL",
    "HTML",
    "CSS",
    "JSON",
    "YAML",
    "HTTP",
    "REST",
    "CLI",
    "IDE",
    "SDK",
    "SSH",
    "TCP",
    "UDP",
    "DNS",
    "TLS",
    "SSL",
    "JWT",
    "OAuth",
    "UUID",
    "GUID",
    "XML",
    "CSV",
    "TOML",
    "AWS",
    "GCP",
    "GPU",
    "CPU",
    "RAM",
    "SSD",
    "HDD",
    "USB",
    "HDMI",
    "TODO",
    "FIXME",
    "NOTE",
    "INFO",
    "WARN",
    "DEBUG",
    "ERROR",
    "README",
    "CHANGELOG",
    "LICENSE",
}


class GlossaryHintsService:
    """Service for extracting and managing candidate glossary terms.

    Scans text files for abbreviations, proper nouns, and domain terms.
    Supports incremental processing — only re-scans changed files.
    """

    def __init__(self, filesystem: FileSystemProtocol, project_root: Path) -> None:
        """Initialize GlossaryHintsService.

        Args:
            filesystem: FileSystemProtocol implementation for file I/O.
            project_root: Root directory of the project.
        """
        self._fs = filesystem
        self._project_root = project_root

    def extract_terms_from_file(self, file_path: Path, content: str) -> list[CandidateTerm]:
        """Extract candidate glossary terms from a single file's content.

        Detects abbreviations, proper nouns, and tracks occurrences
        with context snippets.

        Args:
            file_path: Path to the file (for source tracking).
            content: Text content of the file.

        Returns:
            List of CandidateTerm objects found in the content.
        """
        return self._extract_terms_for_file(file_path.name, content)

    def extract_all(
        self,
        context_dir: Path,
        changed_files: set[str] | None = None,
    ) -> GlossaryHints:
        """Extract candidate terms from context files, only scanning changed files.

        Args:
            context_dir: Path to _nest_context/.
            changed_files: Set of relative paths within context dir that changed.
                           If None, scan all files (first run).

        Returns:
            GlossaryHints with aggregated candidate terms.
        """
        all_files = self._fs.list_files(context_dir)
        supported = {ext.lower() for ext in CONTEXT_TEXT_EXTENSIONS}
        excluded = {MASTER_INDEX_FILE, INDEX_HINTS_FILE, GLOSSARY_HINTS_FILE}

        # Per-file term collection: term -> aggregated data
        term_map: dict[str, CandidateTerm] = {}

        for file_path in all_files:
            if file_path.suffix.lower() not in supported:
                continue
            if file_path.name in excluded:
                continue

            try:
                relative = file_path.relative_to(context_dir).as_posix()
            except ValueError:
                continue

            # Skip unchanged files if tracking changes
            if changed_files is not None and relative not in changed_files:
                continue

            try:
                content = self._fs.read_text(file_path)
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Cannot read %s for glossary extraction: %s", file_path, e)
                continue

            file_terms = self._extract_terms_for_file(relative, content)
            for ct in file_terms:
                self._merge_term(term_map, ct)

        # Apply occurrence thresholds per AC2
        # Note: domain_term category threshold (< 3) is reserved for future use;
        # currently only abbreviation and proper_noun categories are produced.
        # The glossary agent performs deeper domain-term analysis via LLM.
        filtered = []
        for ct in term_map.values():
            if ct.category == "abbreviation" and ct.occurrences < 2:
                continue
            if ct.category == "domain_term" and ct.occurrences < 3:
                continue
            filtered.append(ct)

        return GlossaryHints(terms=filtered)

    def load_previous_hints(self, hints_path: Path) -> GlossaryHints | None:
        """Load previous glossary hints from YAML file.

        Args:
            hints_path: Absolute path to the glossary hints YAML file.

        Returns:
            GlossaryHints if file exists and is valid, None otherwise.
        """
        if not self._fs.exists(hints_path):
            return None

        try:
            content = self._fs.read_text(hints_path)
            data = yaml.safe_load(content)
            if not isinstance(data, dict) or "terms" not in data:
                logger.warning("Invalid glossary hints structure at %s", hints_path)
                return None

            terms = []
            for entry in data["terms"]:
                if not isinstance(entry, dict) or "term" not in entry:
                    continue
                terms.append(
                    CandidateTerm(
                        term=entry["term"],
                        category=entry.get("category", "abbreviation"),
                        occurrences=entry.get("occurrences", 0),
                        source_files=entry.get("source_files", []),
                        context_snippets=entry.get("context_snippets", []),
                    )
                )
            return GlossaryHints(terms=terms)
        except (OSError, yaml.YAMLError) as e:
            logger.warning("Cannot parse glossary hints %s: %s", hints_path, e)
            return None

    def merge_with_previous(
        self,
        new_hints: GlossaryHints,
        old_hints: GlossaryHints | None,
        removed_files: set[str],
    ) -> GlossaryHints:
        """Merge new extraction results with previous hints.

        Carries forward terms from unchanged files, removes terms whose
        only source files were deleted, and merges new terms.

        Args:
            new_hints: Freshly extracted terms from changed/new files.
            old_hints: Previous hints (None on first run).
            removed_files: Set of relative paths that were deleted/orphaned.

        Returns:
            Merged GlossaryHints.
        """
        if old_hints is None:
            return new_hints

        # Build set of files covered by new extraction
        new_files_covered: set[str] = set()
        for ct in new_hints.terms:
            new_files_covered.update(ct.source_files)

        # Start with a fresh term map
        term_map: dict[str, CandidateTerm] = {}

        # Carry forward old terms from files NOT in new extraction and NOT removed
        for old_term in old_hints.terms:
            remaining_sources = [
                src
                for src in old_term.source_files
                if src not in new_files_covered and src not in removed_files
            ]
            if remaining_sources:
                carried = CandidateTerm(
                    term=old_term.term,
                    category=old_term.category,
                    occurrences=old_term.occurrences,
                    source_files=remaining_sources,
                    context_snippets=old_term.context_snippets,
                )
                self._merge_term(term_map, carried)

        # Add all new terms
        for new_term in new_hints.terms:
            self._merge_term(term_map, new_term)

        return GlossaryHints(terms=list(term_map.values()))

    def write_hints(self, hints: GlossaryHints, hints_path: Path) -> None:
        """Write glossary hints to YAML file.

        Args:
            hints: GlossaryHints to serialize.
            hints_path: Absolute path to write the YAML file.
        """
        data = {
            "terms": [
                {
                    "term": ct.term,
                    "category": ct.category,
                    "occurrences": ct.occurrences,
                    "source_files": ct.source_files,
                    "context_snippets": ct.context_snippets,
                }
                for ct in hints.terms
            ]
        }
        header = "# Auto-generated by nest sync \u2014 do not edit manually\n"
        yaml_content = yaml.safe_dump(
            data, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
        content = header + yaml_content

        # Ensure parent directory exists
        parent = hints_path.parent
        if not self._fs.exists(parent):
            self._fs.create_directory(parent)

        self._fs.write_text(hints_path, content)

    def _extract_terms_for_file(self, relative_path: str, content: str) -> list[CandidateTerm]:
        """Extract candidate terms from file content with relative path tracking.

        Args:
            relative_path: Relative path of the file within context dir.
            content: File text content.

        Returns:
            List of CandidateTerm with source_files set to [relative_path].
        """
        if not content.strip():
            return []

        terms: list[CandidateTerm] = []

        # Extract abbreviations
        abbr_results = self._find_abbreviations(content)
        for term_text, snippets in abbr_results.items():
            terms.append(
                CandidateTerm(
                    term=term_text,
                    category="abbreviation",
                    occurrences=len(snippets),
                    source_files=[relative_path],
                    context_snippets=snippets[:3],
                )
            )

        # Extract proper nouns
        noun_results = self._find_proper_nouns(content)
        for term_text, snippets in noun_results.items():
            terms.append(
                CandidateTerm(
                    term=term_text,
                    category="proper_noun",
                    occurrences=len(snippets),
                    source_files=[relative_path],
                    context_snippets=snippets[:3],
                )
            )

        return terms

    def _find_abbreviations(self, content: str) -> dict[str, list[str]]:
        """Find uppercase abbreviation patterns with context snippets.

        Args:
            content: Text content to scan.

        Returns:
            Dict mapping term string to list of context snippets.
        """
        results: dict[str, list[str]] = {}
        for match in ABBREVIATION_PATTERN.finditer(content):
            term = match.group()
            if term in GENERIC_TERM_FILTER:
                continue
            # Extract surrounding sentence as context
            start = max(0, content.rfind(".", 0, match.start()) + 1)
            end = content.find(".", match.end())
            if end == -1:
                end = min(len(content), match.end() + 50)
            snippet = content[start:end].strip()[:100]
            results.setdefault(term, []).append(snippet)
        return results

    def _find_proper_nouns(self, content: str) -> dict[str, list[str]]:
        """Find capitalized multi-word sequences (proper nouns).

        Uses a conservative heuristic requiring a lowercase char or
        punctuation before the name to avoid false positives at sentence start.

        Args:
            content: Text content to scan.

        Returns:
            Dict mapping term string to list of context snippets.
        """
        results: dict[str, list[str]] = {}
        for match in PROPER_NOUN_PATTERN.finditer(content):
            term = match.group()
            # Extract surrounding sentence
            start = max(0, content.rfind(".", 0, match.start()) + 1)
            end = content.find(".", match.end())
            if end == -1:
                end = min(len(content), match.end() + 50)
            snippet = content[start:end].strip()[:100]
            results.setdefault(term, []).append(snippet)
        return results

    @staticmethod
    def _merge_term(term_map: dict[str, CandidateTerm], new_term: CandidateTerm) -> None:
        """Merge a term into the term map, aggregating occurrences and sources.

        Args:
            term_map: Existing term map to merge into.
            new_term: New term to merge.
        """
        key = new_term.term
        if key in term_map:
            existing = term_map[key]
            merged_sources = list(dict.fromkeys(existing.source_files + new_term.source_files))
            merged_snippets = list(
                dict.fromkeys(existing.context_snippets + new_term.context_snippets)
            )[:3]
            term_map[key] = CandidateTerm(
                term=key,
                category=existing.category,
                occurrences=existing.occurrences + new_term.occurrences,
                source_files=merged_sources,
                context_snippets=merged_snippets,
            )
        else:
            term_map[key] = new_term

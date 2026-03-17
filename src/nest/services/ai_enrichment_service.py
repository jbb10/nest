"""AI-powered index enrichment service.

Generates short descriptions for files in the master index using LLM calls.
Operates incrementally — only files with changed or missing content_hash
trigger LLM calls. Unchanged files carry forward existing descriptions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from nest.core.models import AIEnrichmentResult, FileMetadata

if TYPE_CHECKING:
    from nest.adapters.protocols import LLMProviderProtocol

logger = logging.getLogger(__name__)

ENRICHMENT_SYSTEM_PROMPT = (
    "You are a technical documentation assistant. "
    "Write a concise description of the given document in at most 10 words. "
    "Output ONLY the description text, nothing else. "
    "Do NOT use pipe characters (|) in your output. "
    "Do NOT include quotes around the description."
)


class AIEnrichmentService:
    """Generates AI-powered descriptions for index files.

    Uses an LLM provider to generate ≤10-word descriptions for each file.
    Operates incrementally: unchanged files with existing descriptions
    are skipped to avoid wasting tokens.
    """

    def __init__(self, llm_provider: LLMProviderProtocol) -> None:
        self._llm = llm_provider

    def enrich(
        self,
        files: list[FileMetadata],
        old_descriptions: dict[str, str],
        old_hints: dict[str, str],
    ) -> AIEnrichmentResult:
        """Generate descriptions for files needing enrichment.

        Args:
            files: Metadata for all current context files.
            old_descriptions: Previous descriptions keyed by file path.
            old_hints: Previous content hashes keyed by file path.

        Returns:
            AIEnrichmentResult with generated descriptions and token usage.
        """
        descriptions: dict[str, str] = {}
        prompt_tokens = 0
        completion_tokens = 0
        files_enriched = 0
        files_skipped = 0
        files_failed = 0

        for file in files:
            if not self._needs_enrichment(file, old_descriptions, old_hints):
                files_skipped += 1
                continue

            user_prompt = self._build_user_prompt(file)
            result = self._llm.complete(ENRICHMENT_SYSTEM_PROMPT, user_prompt)

            if result is None:
                logger.warning("AI enrichment failed for %s", file.path)
                descriptions[file.path] = ""
                files_failed += 1
                continue

            descriptions[file.path] = self._sanitize_description(result.text)
            prompt_tokens += result.prompt_tokens
            completion_tokens += result.completion_tokens
            files_enriched += 1

        return AIEnrichmentResult(
            descriptions=descriptions,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            files_enriched=files_enriched,
            files_skipped=files_skipped,
            files_failed=files_failed,
        )

    def _needs_enrichment(
        self,
        file: FileMetadata,
        old_descriptions: dict[str, str],
        old_hints: dict[str, str],
    ) -> bool:
        """Determine if a file needs an LLM call for description.

        Skip if content_hash unchanged AND existing description is non-empty.

        Args:
            file: Current file metadata.
            old_descriptions: Previous descriptions keyed by file path.
            old_hints: Previous content hashes keyed by file path.

        Returns:
            True if LLM call is needed, False to carry forward.
        """
        if file.path in old_hints and old_hints[file.path] == file.content_hash:
            existing = old_descriptions.get(file.path, "")
            if existing.strip():
                return False  # Unchanged + has description → skip
        return True  # Changed, new, or missing description → enrich

    def _build_user_prompt(self, file: FileMetadata) -> str:
        """Build user prompt for a single file.

        Args:
            file: File metadata to describe.

        Returns:
            Formatted user prompt string.
        """
        parts = [f"File: {file.path}", f"Lines: {file.lines}"]
        if file.headings:
            headings_text = ", ".join(h.text for h in file.headings[:5])
            parts.append(f"Headings: {headings_text}")
        if file.first_paragraph:
            parts.append(f"Content preview: {file.first_paragraph}")
        if file.table_columns:
            parts.append(f"Table columns: {', '.join(file.table_columns)}")
        return "\n".join(parts)

    def _sanitize_description(self, text: str) -> str:
        """Sanitize LLM output for Markdown table safety.

        Strips pipe characters, quotes, whitespace, and truncates to 10 words.

        Args:
            text: Raw LLM output.

        Returns:
            Sanitized description string.
        """
        sanitized = text.replace("\n", " ").replace("|", "-").strip().strip('"').strip("'").strip()
        words = sanitized.split()
        if len(words) > 10:
            sanitized = " ".join(words[:10])
        return sanitized

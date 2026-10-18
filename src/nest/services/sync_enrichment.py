"""AI enrichment phase of the sync pipeline.

Runs index description enrichment and glossary generation, concurrently when
both have work. Failures in either task are logged and never abort the sync.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from nest.core.paths import GLOSSARY_FILE, NEST_META_DIR

if TYPE_CHECKING:
    from nest.core.models import AIEnrichmentResult, AIGlossaryResult, FileMetadata
    from nest.services.ai_enrichment_service import AIEnrichmentService
    from nest.services.ai_glossary_service import AIGlossaryService
    from nest.services.sync_outcomes import SyncLedger

logger = logging.getLogger(__name__)

T = TypeVar("T")

PROJECT_CONTEXT_FILE = Path("docs") / "project-context.md"


class EnrichmentPhase:
    """Generates AI index descriptions and glossary terms for changed context files."""

    def __init__(
        self,
        project_root: Path,
        context_dir: Path,
        enrichment: AIEnrichmentService | None = None,
        glossary: AIGlossaryService | None = None,
    ) -> None:
        self._project_root = project_root
        self._context_dir = context_dir
        self._enrichment = enrichment
        self._glossary = glossary

    def run(
        self,
        metadata: list[FileMetadata],
        descriptions: dict[str, str],
        hints: dict[str, str],
        changed_files: list[Path],
        ledger: SyncLedger,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        """Run enrichment and glossary generation, updating ``descriptions`` and ``hints``.

        New descriptions are merged into ``descriptions`` and the matching
        content hashes into ``hints`` so the index carries them forward.
        """
        enrichment = self._enrichment
        glossary = self._glossary if changed_files else None
        if enrichment is None and glossary is None:
            return

        if progress is not None:
            progress("start")

        def enrich() -> AIEnrichmentResult:
            assert enrichment is not None
            return enrichment.enrich(metadata, descriptions, hints)

        def define_terms() -> AIGlossaryResult:
            assert glossary is not None
            return glossary.generate(
                changed_files,
                self._context_dir,
                self._project_root / NEST_META_DIR / GLOSSARY_FILE,
                self._load_project_context(),
            )

        if enrichment is not None and glossary is not None:
            with ThreadPoolExecutor(max_workers=2) as executor:
                enrichment_future = executor.submit(enrich)
                glossary_future = executor.submit(define_terms)
                ledger.enrichment = _safely(enrichment_future.result, "AI enrichment")
                ledger.glossary = _safely(glossary_future.result, "AI glossary generation")
        elif enrichment is not None:
            ledger.enrichment = _safely(enrich, "AI enrichment")
        else:
            ledger.glossary = _safely(define_terms, "AI glossary generation")

        if ledger.enrichment is not None:
            descriptions.update(ledger.enrichment.descriptions)
            for file_meta in metadata:
                if file_meta.path in ledger.enrichment.descriptions:
                    hints[file_meta.path] = file_meta.content_hash

        if progress is not None:
            progress(_summary(ledger))

    def _load_project_context(self) -> str | None:
        """Return the first non-empty project context file, if any."""
        candidates = [
            self._project_root / PROJECT_CONTEXT_FILE,
            self._context_dir / "project-context.md",
        ]
        for path in candidates:
            try:
                if path.exists():
                    text = path.read_text(encoding="utf-8").strip()
                    if text:
                        return text
            except OSError:
                continue
        return None


def _safely(task: Callable[[], T], label: str) -> T | None:
    try:
        return task()
    except Exception:
        logger.exception("%s failed", label)
        return None


def _summary(ledger: SyncLedger) -> str:
    parts: list[str] = []
    if ledger.enrichment is not None and ledger.enrichment.files_enriched > 0:
        parts.append(f"{ledger.enrichment.files_enriched} descriptions")
    if ledger.glossary is not None and ledger.glossary.terms_added > 0:
        parts.append(f"{ledger.glossary.terms_added} glossary terms")
    return ", ".join(parts) if parts else "cached"

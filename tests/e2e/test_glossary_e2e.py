"""E2E tests for glossary pipeline (Story 6.8).

Tests verify legacy glossary hints cleanup and that the old hints
pipeline is fully removed.  These tests use passthrough text files
(no Docling needed).
"""

import os
from pathlib import Path

import pytest

from .conftest import run_cli


def _has_ai_key() -> bool:
    return bool(
        os.environ.get("NEST_AI_API_KEY")
        or os.environ.get("NEST_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("AZURE_OPENAI_API_KEY")
    )


@pytest.mark.e2e
class TestGlossaryE2E:
    """E2E tests for glossary pipeline after 6.8 refactor."""

    def test_sync_glossary_hints_file_not_generated(self, initialized_project: Path) -> None:
        """After sync, 00_GLOSSARY_HINTS.yaml should NOT exist (old pipeline removed)."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"

        content = (
            "The PDC review board meets weekly to approve milestones.\n"
            "PDC members include the VP and the SOW author.\n"
        )
        (sources_dir / "contracts").mkdir(parents=True, exist_ok=True)
        (sources_dir / "contracts" / "alpha.md").write_text(content)

        result = run_cli(["sync"], cwd=project_dir)
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        hints_path = project_dir / ".nest" / "00_GLOSSARY_HINTS.yaml"
        assert not hints_path.exists(), "00_GLOSSARY_HINTS.yaml should NOT exist after sync"

    def test_legacy_glossary_hints_deleted_on_first_sync(self, initialized_project: Path) -> None:
        """If 00_GLOSSARY_HINTS.yaml exists from a previous version, sync deletes it."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"

        (sources_dir / "doc.md").write_text("Some content.\n")

        # Manually create the legacy hints file
        hints_path = project_dir / ".nest" / "00_GLOSSARY_HINTS.yaml"
        hints_path.parent.mkdir(parents=True, exist_ok=True)
        hints_path.write_text("# Legacy hints\nterms: []\n")
        assert hints_path.exists()

        result = run_cli(["sync"], cwd=project_dir)
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        assert not hints_path.exists(), "Legacy 00_GLOSSARY_HINTS.yaml should be deleted"

    def test_glossary_hints_excluded_from_index(self, initialized_project: Path) -> None:
        """00_GLOSSARY_HINTS.yaml must not appear in the master index."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"

        (sources_dir / "doc.md").write_text("The XYZ committee meets. XYZ reviews.\n")

        result = run_cli(["sync"], cwd=project_dir)
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        index_path = project_dir / ".nest" / "00_MASTER_INDEX.md"
        assert index_path.exists()
        index_content = index_path.read_text()

        assert "00_GLOSSARY_HINTS.yaml" not in index_content

    @pytest.mark.skipif(
        not _has_ai_key(),
        reason="AI key not configured for incremental glossary E2E",
    )
    def test_glossary_incremental_file_based(self, initialized_project: Path) -> None:
        """Second sync without source changes should not consume AI glossary tokens."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"

        (sources_dir / "ops.md").write_text(
            "The change order process is owned by the PMO runbook team.\n"
        )

        first = run_cli(["sync"], cwd=project_dir)
        assert first.exit_code == 0, f"First sync failed: {first.stderr}\n{first.stdout}"
        assert "AI tokens:" in first.stdout

        second = run_cli(["sync"], cwd=project_dir)
        assert second.exit_code == 0, f"Second sync failed: {second.stderr}\n{second.stdout}"
        assert "AI tokens:" not in second.stdout

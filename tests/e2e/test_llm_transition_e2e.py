"""E2E tests for LLM transition scenarios.

Tests verify that enabling an LLM after an initial non-LLM sync correctly
backfills glossary and index enrichment even though file hashes are
already recorded.

All tests are gated by LLM API key availability.
"""

import os
from pathlib import Path

import pytest

from .conftest import llm_env_vars, run_cli, skip_without_llm

_SAMPLE_CONTENT = """\
# Alpha Project Overview

The Alpha Project is a cloud migration initiative led by the PDC (Project Delivery Committee).
Our SME team has identified 47 legacy systems requiring migration to Azure.
The SOW covers three phases: assessment, migration, and validation.
"""

_SAMPLE_CONTENT_2 = """\
Q3 Planning Meeting Notes - 2026-02-15

Attendees: Sarah (VP Engineering), PDC members, SME leads
The SOW amendment for Phase 2 was approved by the PDC.
Key decision: migrate CRM database first, then ERP system.
Target completion: Q4 2026.
"""


def _index_descriptions_by_file(index_content: str) -> dict[str, str]:
    """Return description text by filename from the index table section."""
    start = index_content.find("<!-- nest:index-table-start -->")
    end = index_content.find("<!-- nest:index-table-end -->")
    assert start != -1
    assert end != -1

    descriptions: dict[str, str] = {}
    table_section = index_content[start:end]
    for line in table_section.splitlines():
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 5:
            continue
        filename = parts[1]
        if filename.lower() == "file" or set(filename) == {"-"}:
            continue
        descriptions[filename] = parts[-2]
    return descriptions


@pytest.mark.e2e
class TestLLMTransitionE2E:
    """E2E tests for transitioning from non-LLM to LLM-enabled sync."""

    @skip_without_llm
    def test_enable_llm_after_initial_sync_backfills_glossary(
        self, initialized_project: Path
    ) -> None:
        """Enabling LLM after a non-LLM sync creates glossary on next sync.

        Regression test: previously, the second sync saw no changed files
        (hashes matched) and never generated the glossary.
        """
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"

        # Add source files
        (sources_dir / "overview.md").write_text(_SAMPLE_CONTENT)
        (sources_dir / "notes.txt").write_text(_SAMPLE_CONTENT_2)

        # --- First sync: WITHOUT LLM credentials ---
        # Build a clean env that strips all LLM keys so the subprocess sees no LLM config.
        # run_cli starts from os.environ.copy(), so we need to remove keys there temporarily.
        llm_keys = (
            "NEST_LLM_API_KEY",
            "NEST_LLM_ENDPOINT",
            "NEST_LLM_MODEL",
            "NEST_API_KEY",
            "NEST_BASE_URL",
            "NEST_TEXT_MODEL",
        )
        saved = {k: os.environ.pop(k) for k in llm_keys if k in os.environ}
        try:
            first = run_cli(["sync"], cwd=project_dir, timeout=120)
        finally:
            os.environ.update(saved)
        assert first.exit_code == 0, f"First sync failed: {first.stderr}\n{first.stdout}"

        glossary_path = project_dir / ".nest" / "glossary.md"
        assert not glossary_path.exists(), (
            "Glossary should NOT exist after sync without LLM credentials"
        )

        # Index descriptions should be empty (no LLM)
        index_path = project_dir / ".nest" / "00_MASTER_INDEX.md"
        assert index_path.exists()
        first_descriptions = _index_descriptions_by_file(index_path.read_text())
        for filename in ("overview.md", "notes.txt"):
            assert filename in first_descriptions, f"Expected index row for {filename}"
            assert not first_descriptions[filename], (
                f"Expected empty description for {filename} without an LLM"
            )

        # Verify "not configured" message appears
        combined = first.stdout + first.stderr
        assert "not configured" in combined.lower(), (
            "Expected 'not configured' LLM status message in sync output"
        )

        # --- Second sync: WITH LLM credentials ---
        second = run_cli(["sync"], cwd=project_dir, timeout=120, env=llm_env_vars())
        assert second.exit_code == 0, f"Second sync failed: {second.stderr}\n{second.stdout}"

        # Glossary should now exist in .nest/
        assert glossary_path.exists(), (
            "Glossary should be created after enabling an LLM on second sync"
        )
        glossary_content = glossary_path.read_text()
        assert "<!-- nest:glossary-start -->" in glossary_content
        assert "<!-- nest:glossary-end -->" in glossary_content

        # Glossary should have at least one data row
        start = glossary_content.find("<!-- nest:glossary-start -->")
        end = glossary_content.find("<!-- nest:glossary-end -->")
        table_section = glossary_content[start:end]
        data_rows = [
            line
            for line in table_section.splitlines()
            if line.startswith("|") and "---" not in line and "Term" not in line
        ]
        assert len(data_rows) >= 1, "Expected at least one glossary term after LLM backfill"

        # Index descriptions should now be populated
        second_descriptions = _index_descriptions_by_file(index_path.read_text())
        for filename in ("overview.md", "notes.txt"):
            assert filename in second_descriptions, f"Expected index row for {filename}"
            assert second_descriptions[filename], (
                f"Expected non-empty description for {filename} after the LLM was enabled"
            )

        # LLM tokens should be reported
        assert "LLM tokens:" in second.stdout

    @skip_without_llm
    def test_enable_ai_after_no_llm_flag_backfills(self, initialized_project: Path) -> None:
        """Using --no-llm then running without it produces glossary and descriptions.

        Exercises the same backfill path but the first sync explicitly uses --no-llm
        while having LLM credentials available.
        """
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"

        (sources_dir / "overview.md").write_text(_SAMPLE_CONTENT)

        # First sync with --no-llm (credentials present but disabled)
        first = run_cli(["sync", "--no-llm"], cwd=project_dir, timeout=120, env=llm_env_vars())
        assert first.exit_code == 0, f"First sync failed: {first.stderr}\n{first.stdout}"

        glossary_path = project_dir / ".nest" / "glossary.md"
        assert not glossary_path.exists(), "Glossary should NOT exist after --no-llm sync"

        # Second sync with the LLM enabled (no --no-llm flag)
        second = run_cli(["sync"], cwd=project_dir, timeout=120, env=llm_env_vars())
        assert second.exit_code == 0, f"Second sync failed: {second.stderr}\n{second.stdout}"

        assert glossary_path.exists(), "Glossary should be created when the LLM is re-enabled"

        # Index description should be populated
        index_path = project_dir / ".nest" / "00_MASTER_INDEX.md"
        descriptions = _index_descriptions_by_file(index_path.read_text())
        assert "overview.md" in descriptions
        assert descriptions["overview.md"], (
            "Expected non-empty description after the LLM was re-enabled"
        )

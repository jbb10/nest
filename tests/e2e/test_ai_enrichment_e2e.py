"""E2E tests for AI index enrichment (Story 6.7).

Tests verify that sync with a real LLM produces enriched index
descriptions and respects --no-ai and incremental caching.
All tests are gated by AI API key availability.
"""

from pathlib import Path

import pytest

from .conftest import ai_env_vars, run_cli, skip_without_ai

_PROJECT_OVERVIEW = """\
# Alpha Project Overview

The Alpha Project is a cloud migration initiative led by the PDC (Project Delivery Committee).
Our SME team has identified 47 legacy systems requiring migration to Azure.
The SOW covers three phases: assessment, migration, and validation.
"""

_MEETING_NOTES = """\
Q3 Planning Meeting Notes - 2026-02-15

Attendees: Sarah (VP Engineering), PDC members, SME leads
The SOW amendment for Phase 2 was approved by the PDC.
Key decision: migrate CRM database first, then ERP system.
Target completion: Q4 2026.
"""

_TECHNICAL_SPEC = """\
# Technical Specification v2.1

## Architecture
The system uses a microservices architecture deployed on Kubernetes.
The API gateway handles authentication via OAuth 2.0 and mTLS.
Data flows through the ETL pipeline into the data warehouse.
"""


def _add_sample_files(sources_dir: Path) -> None:
    """Create sample passthrough files in the sources directory."""
    (sources_dir / "project-overview.md").write_text(_PROJECT_OVERVIEW)
    (sources_dir / "meeting-notes.txt").write_text(_MEETING_NOTES)
    (sources_dir / "technical-spec.md").write_text(_TECHNICAL_SPEC)


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
class TestAIEnrichmentE2E:
    """E2E tests for AI-powered index enrichment."""

    @skip_without_ai
    def test_sync_produces_enriched_index_with_ai_descriptions(
        self, initialized_project: Path
    ) -> None:
        """AC6: Sync with AI produces non-empty descriptions in master index."""
        project_dir = initialized_project
        _add_sample_files(project_dir / "_nest_sources")

        result = run_cli(["sync"], cwd=project_dir, timeout=120, env=ai_env_vars())
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        # Index should have non-empty descriptions
        index_path = project_dir / ".nest" / "00_MASTER_INDEX.md"
        assert index_path.exists()
        index_content = index_path.read_text()

        descriptions = _index_descriptions_by_file(index_content)

        # Each file row must exist and have a non-empty description.
        for filename in ("project-overview.md", "meeting-notes.txt", "technical-spec.md"):
            assert filename in descriptions, f"Expected index row for {filename}"
            assert descriptions[filename], f"Expected non-empty description for {filename}"

        # Token usage should be reported
        assert "AI tokens:" in result.stdout

        # First-run AI discovery message
        combined = result.stdout + result.stderr
        assert "AI enrichment" in combined or "🤖" in combined

    @skip_without_ai
    def test_sync_incremental_ai_skips_unchanged(self, initialized_project: Path) -> None:
        """AC8: Second sync without changes reports no token usage."""
        project_dir = initialized_project
        _add_sample_files(project_dir / "_nest_sources")
        env = ai_env_vars()

        # First sync — generates descriptions
        first = run_cli(["sync"], cwd=project_dir, timeout=120, env=env)
        assert first.exit_code == 0, f"First sync failed: {first.stderr}\n{first.stdout}"
        assert "AI tokens:" in first.stdout

        # Capture descriptions from first sync
        index_path = project_dir / ".nest" / "00_MASTER_INDEX.md"
        first_index = index_path.read_text()
        first_descriptions = _index_descriptions_by_file(first_index)

        # Second sync — no changes, should skip AI
        second = run_cli(["sync"], cwd=project_dir, timeout=120, env=env)
        assert second.exit_code == 0, f"Second sync failed: {second.stderr}\n{second.stdout}"
        assert "AI tokens:" not in second.stdout

        # Descriptions preserved exactly for unchanged files.
        second_index = index_path.read_text()
        second_descriptions = _index_descriptions_by_file(second_index)
        for filename in ("project-overview.md", "meeting-notes.txt", "technical-spec.md"):
            assert filename in first_descriptions, f"Expected first-sync row for {filename}"
            assert filename in second_descriptions, f"Expected second-sync row for {filename}"
            assert first_descriptions[filename], (
                f"Expected non-empty first-sync description for {filename}"
            )
            assert second_descriptions[filename] == first_descriptions[filename], (
                f"Description changed unexpectedly for {filename}"
            )

    @skip_without_ai
    def test_sync_no_ai_flag_skips_enrichment(self, initialized_project: Path) -> None:
        """AC9: --no-ai flag skips enrichment even with AI keys set."""
        project_dir = initialized_project
        _add_sample_files(project_dir / "_nest_sources")

        result = run_cli(["sync", "--no-ai"], cwd=project_dir, timeout=120, env=ai_env_vars())
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        # Index should exist but descriptions should be empty
        index_path = project_dir / ".nest" / "00_MASTER_INDEX.md"
        assert index_path.exists()
        index_content = index_path.read_text()

        descriptions = _index_descriptions_by_file(index_content)
        for filename in ("project-overview.md", "meeting-notes.txt", "technical-spec.md"):
            assert filename in descriptions, f"Expected index row for {filename}"
            assert not descriptions[filename], (
                f"Expected empty description for {filename} with --no-ai"
            )

        # No token usage reported
        assert "AI tokens:" not in result.stdout

"""E2E tests for the sync command.

Tests run actual CLI commands via subprocess with real file I/O
and real Docling processing.
"""

import json
from pathlib import Path

import pytest

from .conftest import run_cli, skip_without_docling


@pytest.mark.e2e
@skip_without_docling
class TestSyncE2E:
    """E2E tests for nest sync command.

    These tests require Docling models to be downloaded.
    They will be skipped if models are not available.

    Uses fixtures from conftest.py:
    - initialized_project: Runs nest init (each test gets fresh project)
    - sample_documents: Copies test fixtures to _nest_sources/
    """

    def test_sync_processes_nested_documents(self, sample_documents: Path):
        """Test that sync processes nested documents correctly.

        AC5: Given a Nest project is initialized
        And 4 test documents are placed in nested structure under _nest_sources/
        When nest sync is run via subprocess
        Then exit code is 0
        And output structure mirrors input in _nest_context/
        And all output files have .md extension
        And all output files are non-empty
        And manifest contains entries for all 4 files
        And stdout indicates files were processed
        """
        project_dir = sample_documents

        # Act
        result = run_cli(["sync"], cwd=project_dir)

        # Assert exit code
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        # Assert output structure mirrors input
        processed = project_dir / "_nest_context"
        assert (processed / "reports" / "quarterly.md").exists()
        assert (processed / "reports" / "summary.md").exists()
        assert (processed / "presentations" / "deck.md").exists()
        assert (processed / "presentations" / "data.md").exists()

        # Assert all output files are non-empty
        for md_file in processed.rglob("*.md"):
            # Skip index files
            if md_file.name.startswith("00_"):
                continue
            assert md_file.stat().st_size > 0, f"{md_file} should be non-empty"

        # Assert manifest contains entries for all 4 files
        manifest_path = project_dir / ".nest_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert "files" in manifest

        files = manifest["files"]
        assert len(files) == 4, f"Expected 4 files in manifest, got {len(files)}"

        # Check manifest paths (keys are source paths)
        file_paths = set(files.keys())
        expected_paths = {
            "reports/quarterly.pdf",
            "reports/summary.docx",
            "presentations/deck.pptx",
            "presentations/data.xlsx",
        }
        assert file_paths == expected_paths, f"Expected {expected_paths}, got {file_paths}"

        # Assert stdout indicates files were processed
        assert "4" in result.stdout or "processed" in result.stdout.lower()

    def test_sync_idempotent_no_changes(self, sample_documents: Path):
        """Test that running sync twice skips unchanged files."""
        project_dir = sample_documents

        # First sync
        result1 = run_cli(["sync"], cwd=project_dir)
        assert result1.exit_code == 0

        # Second sync should skip everything
        result2 = run_cli(["sync"], cwd=project_dir)
        assert result2.exit_code == 0

        # Should indicate files were skipped (no changes)
        # Output may contain "skip" or show 0 processed
        assert "0" in result2.stdout or "skip" in result2.stdout.lower()


@pytest.mark.e2e
class TestSyncContextTextFilesE2E:
    """E2E tests for non-Markdown text files in context indexing (Story 2.11)."""

    def test_sync_indexes_user_curated_txt_file(self, initialized_project: Path) -> None:
        """AC3: A .txt file added to _nest_context/ should appear in the master index."""
        project_dir = initialized_project

        # Manually create a .txt file in context directory
        context_dir = project_dir / "_nest_context"
        context_dir.mkdir(parents=True, exist_ok=True)
        (context_dir / "notes.txt").write_text("Meeting notes from 2026-02-09")

        # Run sync
        result = run_cli(["sync"], cwd=project_dir)
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        # Verify notes.txt appears in master index
        index_content = (context_dir / "00_MASTER_INDEX.md").read_text()
        assert "notes.txt" in index_content

    def test_sync_indexes_user_curated_yaml_file(self, initialized_project: Path) -> None:
        """AC4: A .yaml file added to _nest_context/ should appear in the master index."""
        project_dir = initialized_project

        # Manually create a .yaml file in context directory
        context_dir = project_dir / "_nest_context"
        context_dir.mkdir(parents=True, exist_ok=True)
        (context_dir / "api-spec.yaml").write_text("openapi: 3.0.0\ninfo:\n  title: Test API")

        # Run sync
        result = run_cli(["sync"], cwd=project_dir)
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        # Verify api-spec.yaml appears in master index
        index_content = (context_dir / "00_MASTER_INDEX.md").read_text()
        assert "api-spec.yaml" in index_content

    def test_sync_ignores_binary_in_context(self, initialized_project: Path) -> None:
        """AC2: A .png file added to _nest_context/ should NOT appear in the master index."""
        project_dir = initialized_project

        # Manually create a .png file in context directory
        context_dir = project_dir / "_nest_context"
        context_dir.mkdir(parents=True, exist_ok=True)
        (context_dir / "diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        # Run sync
        result = run_cli(["sync"], cwd=project_dir)
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        # Verify diagram.png does NOT appear in master index
        index_content = (context_dir / "00_MASTER_INDEX.md").read_text()
        assert "diagram.png" not in index_content

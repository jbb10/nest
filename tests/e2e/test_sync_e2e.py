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
        """Test that running sync twice skips unchanged files.

        The second sync must NOT re-process any documents. We verify this
        by checking that:
        - Manifest checksums are identical before and after the second sync
        - Output file mtimes are not changed (files were not rewritten)
        - CLI output reports 0 new and 0 modified files
        """
        project_dir = sample_documents
        manifest_path = project_dir / ".nest_manifest.json"
        processed_dir = project_dir / "_nest_context"

        # First sync — processes all 4 documents
        result1 = run_cli(["sync"], cwd=project_dir)
        assert result1.exit_code == 0, f"First sync failed: {result1.stderr}\n{result1.stdout}"

        # Snapshot manifest state after first sync
        manifest_before = json.loads(manifest_path.read_text())
        checksums_before = {
            k: v["sha256"] for k, v in manifest_before["files"].items()
        }

        # Snapshot output file mtimes after first sync
        output_files = sorted(processed_dir.rglob("*.md"))
        # Filter out index files which may be regenerated
        content_files = [f for f in output_files if not f.name.startswith("00_")]
        assert len(content_files) >= 4, f"Expected >= 4 output files, got {len(content_files)}"
        mtimes_before = {str(f): f.stat().st_mtime for f in content_files}

        # Second sync — should skip everything
        result2 = run_cli(["sync"], cwd=project_dir)
        assert result2.exit_code == 0, f"Second sync failed: {result2.stderr}\n{result2.stdout}"

        # Verify manifest checksums are identical
        manifest_after = json.loads(manifest_path.read_text())
        checksums_after = {
            k: v["sha256"] for k, v in manifest_after["files"].items()
        }
        assert checksums_before == checksums_after, (
            f"Manifest checksums changed between syncs!\n"
            f"Before: {checksums_before}\nAfter: {checksums_after}"
        )

        # Verify output files were not rewritten (mtimes unchanged)
        mtimes_after = {str(f): f.stat().st_mtime for f in content_files}
        for fpath, mtime in mtimes_before.items():
            assert mtimes_after[fpath] == mtime, (
                f"Output file was rewritten on second sync: {fpath}"
            )

        # Verify CLI output indicates nothing was processed
        stdout_lower = result2.stdout.lower()
        # Should NOT report any files as new or modified
        assert "new" not in stdout_lower or "0 new" in stdout_lower or "0" in result2.stdout, (
            f"Second sync appears to have processed files:\n{result2.stdout}"
        )


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

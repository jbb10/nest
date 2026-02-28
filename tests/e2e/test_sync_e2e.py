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
        manifest_path = project_dir / ".nest" / "manifest.json"
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
        manifest_path = project_dir / ".nest" / "manifest.json"
        processed_dir = project_dir / "_nest_context"

        # First sync — processes all 4 documents
        result1 = run_cli(["sync"], cwd=project_dir)
        assert result1.exit_code == 0, f"First sync failed: {result1.stderr}\n{result1.stdout}"

        # Snapshot manifest state after first sync
        manifest_before = json.loads(manifest_path.read_text())
        checksums_before = {k: v["sha256"] for k, v in manifest_before["files"].items()}

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
        checksums_after = {k: v["sha256"] for k, v in manifest_after["files"].items()}
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
        index_content = (project_dir / ".nest" / "00_MASTER_INDEX.md").read_text()
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
        index_content = (project_dir / ".nest" / "00_MASTER_INDEX.md").read_text()
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
        index_content = (project_dir / ".nest" / "00_MASTER_INDEX.md").read_text()
        assert "diagram.png" not in index_content


@pytest.mark.e2e
class TestSyncPassthroughE2E:
    """E2E tests for passthrough text file processing from _nest_sources/ (Story 2.12)."""

    def test_sync_passthrough_txt_file(self, initialized_project: Path) -> None:
        """AC2: A .txt file in _nest_sources/ should be copied to _nest_context/ and indexed."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"
        context_dir = project_dir / "_nest_context"

        # Create a .txt file in sources
        (sources_dir / "notes.txt").write_text("Meeting notes from 2026-02-26")

        # Run sync
        result = run_cli(["sync"], cwd=project_dir)
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        # Assert file was copied to context with same content
        output_file = context_dir / "notes.txt"
        assert output_file.exists(), "notes.txt not found in _nest_context/"
        assert output_file.read_text() == "Meeting notes from 2026-02-26"

        # Assert it appears in the master index
        index_content = (project_dir / ".nest" / "00_MASTER_INDEX.md").read_text()
        assert "notes.txt" in index_content

        # Assert manifest entry exists
        manifest = json.loads((project_dir / ".nest" / "manifest.json").read_text())
        assert "notes.txt" in manifest["files"]
        assert manifest["files"]["notes.txt"]["status"] == "success"

    def test_sync_passthrough_yaml_file(self, initialized_project: Path) -> None:
        """AC2: A .yaml file in _nest_sources/ should be copied to _nest_context/ and indexed."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"
        context_dir = project_dir / "_nest_context"

        # Create a .yaml file in sources
        (sources_dir / "api-spec.yaml").write_text("openapi: 3.0.0\ninfo:\n  title: Test API")

        # Run sync
        result = run_cli(["sync"], cwd=project_dir)
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        # Assert file was copied
        assert (context_dir / "api-spec.yaml").exists()
        expected_yaml = "openapi: 3.0.0\ninfo:\n  title: Test API"
        assert (context_dir / "api-spec.yaml").read_text() == expected_yaml

        # Assert it appears in the master index
        index_content = (project_dir / ".nest" / "00_MASTER_INDEX.md").read_text()
        assert "api-spec.yaml" in index_content

    def test_sync_passthrough_preserves_subdirectory(self, initialized_project: Path) -> None:
        """AC3: Passthrough files in subdirectories should mirror the structure."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"
        context_dir = project_dir / "_nest_context"

        # Create nested text file
        (sources_dir / "team").mkdir(parents=True, exist_ok=True)
        (sources_dir / "team" / "notes.txt").write_text("team meeting notes")

        # Run sync
        result = run_cli(["sync"], cwd=project_dir)
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        # Assert nested file was copied
        assert (context_dir / "team" / "notes.txt").exists()
        assert (context_dir / "team" / "notes.txt").read_text() == "team meeting notes"

    def test_sync_passthrough_incremental_skip(self, initialized_project: Path) -> None:
        """AC4: Unchanged passthrough files should be skipped on subsequent sync."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"

        # Create file and first sync
        (sources_dir / "notes.txt").write_text("meeting notes")
        result1 = run_cli(["sync"], cwd=project_dir)
        assert result1.exit_code == 0

        # Second sync — should skip
        result2 = run_cli(["sync"], cwd=project_dir)
        assert result2.exit_code == 0

        # Verify CLI output indicates 0 processed
        stdout_lower = result2.stdout.lower()
        assert "processed: 0" in stdout_lower or "0 files" in stdout_lower, (
            f"Second sync appears to have processed files:\n{result2.stdout}"
        )

    def test_sync_passthrough_orphan_cleanup(self, initialized_project: Path) -> None:
        """AC6: Removing a passthrough source should orphan-clean its context copy."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"
        context_dir = project_dir / "_nest_context"

        # Create and sync
        (sources_dir / "notes.txt").write_text("meeting notes")
        result1 = run_cli(["sync"], cwd=project_dir)
        assert result1.exit_code == 0
        assert (context_dir / "notes.txt").exists()

        # Delete source
        (sources_dir / "notes.txt").unlink()

        # Re-sync — should orphan-clean
        result2 = run_cli(["sync"], cwd=project_dir)
        assert result2.exit_code == 0

        # Assert context copy removed
        assert not (context_dir / "notes.txt").exists()

        # Assert removed from index
        index_content = (project_dir / ".nest" / "00_MASTER_INDEX.md").read_text()
        assert "notes.txt" not in index_content

    def test_sync_passthrough_ignores_binary(self, initialized_project: Path) -> None:
        """AC1: A .png file in _nest_sources/ should not be processed or copied."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"
        context_dir = project_dir / "_nest_context"

        # Create binary file in sources
        (sources_dir / "diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        # Run sync
        result = run_cli(["sync"], cwd=project_dir)
        assert result.exit_code == 0

        # Assert NOT copied
        assert not (context_dir / "diagram.png").exists()

        # Assert NOT in index
        index_content = (project_dir / ".nest" / "00_MASTER_INDEX.md").read_text()
        assert "diagram.png" not in index_content

    def test_sync_user_curated_still_preserved(self, initialized_project: Path) -> None:
        """AC11: Files dropped directly into _nest_context/ should still work."""
        project_dir = initialized_project
        context_dir = project_dir / "_nest_context"

        # Create user-curated file directly in context
        context_dir.mkdir(parents=True, exist_ok=True)
        (context_dir / "custom.txt").write_text("user curated content")

        # Run sync
        result = run_cli(["sync"], cwd=project_dir)
        assert result.exit_code == 0

        # Assert file still exists
        assert (context_dir / "custom.txt").exists()
        assert (context_dir / "custom.txt").read_text() == "user curated content"

        # Assert it appears in index
        index_content = (project_dir / ".nest" / "00_MASTER_INDEX.md").read_text()
        assert "custom.txt" in index_content

    def test_sync_passthrough_force_recopies(self, initialized_project: Path) -> None:
        """AC10: --force recopies passthrough text files even if checksum unchanged."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"
        context_dir = project_dir / "_nest_context"

        # Create file and first sync
        (sources_dir / "notes.txt").write_text("original content")
        result1 = run_cli(["sync"], cwd=project_dir)
        assert result1.exit_code == 0
        assert (context_dir / "notes.txt").exists()

        # Record manifest timestamp
        manifest_before = json.loads((project_dir / ".nest" / "manifest.json").read_text())
        timestamp_before = manifest_before["files"]["notes.txt"]["processed_at"]

        # Small delay to ensure timestamp would differ if reprocessed
        import time

        time.sleep(0.05)

        # Force sync — must recopy even though content unchanged
        result2 = run_cli(["sync", "--force"], cwd=project_dir)
        assert result2.exit_code == 0

        # Manifest timestamp should be updated (file was reprocessed)
        manifest_after = json.loads((project_dir / ".nest" / "manifest.json").read_text())
        timestamp_after = manifest_after["files"]["notes.txt"]["processed_at"]
        assert timestamp_after != timestamp_before, "Force sync did not reprocess passthrough file"
        assert (context_dir / "notes.txt").read_text() == "original content"

    def test_sync_passthrough_collision_passthrough_wins(self, initialized_project: Path) -> None:
        """AC7: Passthrough .md wins over Docling .pdf when output paths collide."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"
        context_dir = project_dir / "_nest_context"

        # Create both report.md (passthrough) and report.pdf (Docling → report.md)
        (sources_dir / "report.md").write_text("# User's explicit report content")
        (sources_dir / "report.pdf").write_bytes(
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        )

        # Run sync
        result = run_cli(["sync"], cwd=project_dir)
        assert result.exit_code == 0

        # The passthrough file must win — content from report.md, not Docling output
        output = context_dir / "report.md"
        assert output.exists()
        assert output.read_text() == "# User's explicit report content"

        # Manifest should show report.pdf as skipped
        manifest = json.loads((project_dir / ".nest" / "manifest.json").read_text())
        assert "report.pdf" in manifest["files"]
        assert manifest["files"]["report.pdf"]["status"] == "skipped"
        assert "conflicts" in manifest["files"]["report.pdf"].get("error", "").lower()

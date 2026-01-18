"""E2E tests for the sync command.

Tests run actual CLI commands via subprocess with real file I/O
and real Docling processing.
"""

import json
import shutil
from pathlib import Path

import pytest

from .conftest import run_cli, skip_without_docling


@pytest.mark.e2e
@skip_without_docling
class TestSyncE2E:
    """E2E tests for nest sync command.

    These tests require Docling models to be downloaded.
    They will be skipped if models are not available.
    """

    @pytest.fixture(scope="class")
    def initialized_project(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """Create an initialized Nest project for sync tests."""
        project_dir = tmp_path_factory.mktemp("nest_sync_e2e")
        result = run_cli(["init", "SyncTestProject"], cwd=project_dir)
        assert result.exit_code == 0, f"Init failed: {result.stderr}"
        return project_dir

    @pytest.fixture
    def project_with_documents(self, initialized_project: Path) -> Path:
        """Copy test fixtures to raw_inbox in nested structure.

        Creates:
            raw_inbox/reports/quarterly.pdf
            raw_inbox/reports/summary.docx
            raw_inbox/presentations/deck.pptx
            raw_inbox/presentations/data.xlsx
        """
        fixtures_dir = Path(__file__).parent / "fixtures"
        raw_inbox = initialized_project / "raw_inbox"

        # Create nested structure
        reports_dir = raw_inbox / "reports"
        presentations_dir = raw_inbox / "presentations"
        reports_dir.mkdir(parents=True, exist_ok=True)
        presentations_dir.mkdir(parents=True, exist_ok=True)

        # Copy fixtures to nested structure
        shutil.copy(fixtures_dir / "quarterly.pdf", reports_dir / "quarterly.pdf")
        shutil.copy(fixtures_dir / "summary.docx", reports_dir / "summary.docx")
        shutil.copy(fixtures_dir / "deck.pptx", presentations_dir / "deck.pptx")
        shutil.copy(fixtures_dir / "data.xlsx", presentations_dir / "data.xlsx")

        return initialized_project

    def test_sync_processes_nested_documents(self, project_with_documents: Path):
        """Test that sync processes nested documents correctly.

        AC5: Given a Nest project is initialized
        And 4 test documents are placed in nested structure under raw_inbox/
        When nest sync is run via subprocess
        Then exit code is 0
        And output structure mirrors input in processed_context/
        And all output files have .md extension
        And all output files are non-empty
        And manifest contains entries for all 4 files
        And stdout indicates files were processed
        """
        project_dir = project_with_documents

        # Act
        result = run_cli(["sync"], cwd=project_dir)

        # Assert exit code
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        # Assert output structure mirrors input
        processed = project_dir / "processed_context"
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

    def test_sync_idempotent_no_changes(self, project_with_documents: Path):
        """Test that running sync twice skips unchanged files."""
        project_dir = project_with_documents

        # First sync
        result1 = run_cli(["sync"], cwd=project_dir)
        assert result1.exit_code == 0

        # Second sync should skip everything
        result2 = run_cli(["sync"], cwd=project_dir)
        assert result2.exit_code == 0

        # Should indicate files were skipped (no changes)
        # Output may contain "skip" or show 0 processed
        assert "0" in result2.stdout or "skip" in result2.stdout.lower()

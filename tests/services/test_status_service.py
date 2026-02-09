"""Tests for StatusService."""

from datetime import datetime, timezone
from pathlib import Path

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.core.checksum import compute_sha256
from nest.core.models import FileEntry, Manifest
from nest.core.paths import CONTEXT_DIR, MASTER_INDEX_FILE, SOURCES_DIR
from nest.services.status_service import StatusService


def _write_source_file(project_root: Path, relative: str, content: bytes) -> Path:
    path = project_root / SOURCES_DIR / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _write_context_file(project_root: Path, relative: str, content: str = "# doc\n") -> Path:
    path = project_root / CONTEXT_DIR / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


class TestStatusService:
    def test_get_status_counts_source_and_context(self, tmp_path: Path) -> None:
        project_root = tmp_path

        # Sources
        _write_source_file(project_root, "new.pdf", b"new")
        _write_source_file(project_root, "modified.pdf", b"modified-v2")
        unchanged_file = _write_source_file(project_root, "unchanged.pdf", b"unchanged")

        unchanged_sha = compute_sha256(unchanged_file)

        # Context
        _write_context_file(project_root, MASTER_INDEX_FILE, "# Index\n")
        _write_context_file(project_root, "modified.md")
        _write_context_file(project_root, "unchanged.md")
        _write_context_file(project_root, "orphan.md")

        manifest = Manifest(
            nest_version="0.0.0",
            project_name="TestProject",
            last_sync=datetime(2026, 1, 1, tzinfo=timezone.utc),
            files={
                "modified.pdf": FileEntry(
                    sha256="old-sha",
                    processed_at=datetime.now(timezone.utc),
                    output="modified.md",
                    status="success",
                ),
                "unchanged.pdf": FileEntry(
                    sha256=unchanged_sha,
                    processed_at=datetime.now(timezone.utc),
                    output="unchanged.md",
                    status="success",
                ),
                # Orphan: output exists but source missing
                "orphan.pdf": FileEntry(
                    sha256="deadbeef",
                    processed_at=datetime.now(timezone.utc),
                    output="orphan.md",
                    status="success",
                ),
            },
        )
        ManifestAdapter().save(project_root, manifest)

        service = StatusService(filesystem=FileSystemAdapter(), manifest=ManifestAdapter())
        report = service.get_status(project_root)

        assert report.project_name == "TestProject"
        assert report.source_total == 3
        assert report.source_new == 1
        assert report.source_modified == 1
        assert report.source_unchanged == 1

        # Context files exclude master index
        assert report.context_files == 3
        assert report.context_orphaned == 1
        assert report.pending_count == 2

    def test_get_status_handles_missing_sources_dir(self, tmp_path: Path) -> None:
        project_root = tmp_path
        (project_root / CONTEXT_DIR).mkdir(parents=True)

        manifest = Manifest(
            nest_version="0.0.0",
            project_name="TestProject",
            last_sync=None,
            files={},
        )
        ManifestAdapter().save(project_root, manifest)

        service = StatusService(filesystem=FileSystemAdapter(), manifest=ManifestAdapter())
        report = service.get_status(project_root)

        assert report.source_total == 0
        assert report.source_new == 0
        assert report.source_modified == 0
        assert report.source_unchanged == 0

    def test_context_counts_txt_files(self, tmp_path: Path) -> None:
        """AC5: .txt files in context directory are counted."""
        project_root = tmp_path
        _write_context_file(project_root, MASTER_INDEX_FILE, "# Index\n")
        _write_context_file(project_root, "notes.txt", "some notes")
        _write_context_file(project_root, "doc.md", "# doc")

        manifest = Manifest(
            nest_version="0.0.0",
            project_name="TestProject",
            last_sync=None,
            files={},
        )
        ManifestAdapter().save(project_root, manifest)

        service = StatusService(filesystem=FileSystemAdapter(), manifest=ManifestAdapter())
        report = service.get_status(project_root)

        assert report.context_files == 2  # notes.txt + doc.md

    def test_context_excludes_unsupported_extensions(self, tmp_path: Path) -> None:
        """AC5: .png files are excluded from context file count."""
        project_root = tmp_path
        _write_context_file(project_root, MASTER_INDEX_FILE, "# Index\n")
        _write_context_file(project_root, "doc.md", "# doc")
        # Create a .png file (unsupported)
        png_path = project_root / CONTEXT_DIR / "diagram.png"
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(b"\x89PNG\r\n")

        manifest = Manifest(
            nest_version="0.0.0",
            project_name="TestProject",
            last_sync=None,
            files={},
        )
        ManifestAdapter().save(project_root, manifest)

        service = StatusService(filesystem=FileSystemAdapter(), manifest=ManifestAdapter())
        report = service.get_status(project_root)

        assert report.context_files == 1  # only doc.md, png excluded

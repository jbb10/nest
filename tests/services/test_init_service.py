"""Unit tests for InitService."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from conftest import (
    MockAgentWriter,
    MockFileSystem,
    MockManifest,
    MockModelDownloader,
)
from nest.core.exceptions import NestError
from nest.core.paths import CONTEXT_TEXT_EXTENSIONS, SUPPORTED_EXTENSIONS
from nest.services.init_service import InitService


@patch("nest.services.init_service.InitService._setup_gitattributes")
@patch("nest.services.init_service.InitService._setup_gitignore")
def test_init_service_calls_agent_writer(
    mock_gitignore: MagicMock,
    mock_gitattributes: MagicMock,
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader: MockModelDownloader,
) -> None:
    """Test that InitService calls agent_writer.generate() with correct args."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader,
    )
    target_dir = Path("/project")

    service.execute("Nike", target_dir)

    # Verify agent writer was called
    assert len(mock_agent_writer.generated_agents) == 1
    project_name, output_path = mock_agent_writer.generated_agents[0]
    assert project_name == "Nike"
    assert output_path == target_dir / ".github" / "agents" / "nest.agent.md"


@patch("nest.services.init_service.InitService._setup_gitattributes")
@patch("nest.services.init_service.InitService._setup_gitignore")
def test_init_service_strips_project_name_whitespace(
    mock_gitignore: MagicMock,
    mock_gitattributes: MagicMock,
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader: MockModelDownloader,
) -> None:
    """Test that project name is stripped before passing to agent writer."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader,
    )

    service.execute("  Nike  ", Path("/project"))

    project_name, _ = mock_agent_writer.generated_agents[0]
    assert project_name == "Nike"


def test_init_service_rejects_empty_project_name(
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader: MockModelDownloader,
) -> None:
    """Test that empty project name raises NestError."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader,
    )

    with pytest.raises(NestError, match="Project name required"):
        service.execute("", Path("/project"))


def test_init_service_rejects_whitespace_only_project_name(
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader: MockModelDownloader,
) -> None:
    """Test that whitespace-only project name raises NestError."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader,
    )

    with pytest.raises(NestError, match="Project name required"):
        service.execute("   ", Path("/project"))


def test_init_service_rejects_existing_project(
    mock_filesystem: MockFileSystem,
    mock_manifest_exists: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader: MockModelDownloader,
) -> None:
    """Test that existing project raises NestError."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest_exists,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader,
    )

    with pytest.raises(NestError, match="already exists"):
        service.execute("Nike", Path("/project"))


@patch("nest.services.init_service.InitService._setup_gitattributes")
@patch("nest.services.init_service.InitService._setup_gitignore")
def test_init_service_creates_all_directories(
    mock_gitignore: MagicMock,
    mock_gitattributes: MagicMock,
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader: MockModelDownloader,
) -> None:
    """Test that InitService creates all required directories."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader,
    )
    target_dir = Path("/project")

    service.execute("Nike", target_dir)

    created_dirs = [str(d) for d in mock_filesystem.created_dirs]
    assert str(target_dir / "_nest_sources") in created_dirs
    assert str(target_dir / "_nest_context") in created_dirs
    assert str(target_dir / ".github/agents") in created_dirs


@patch("nest.services.init_service.InitService._setup_gitattributes")
@patch("nest.services.init_service.InitService._setup_gitignore")
def test_init_service_creates_manifest(
    mock_gitignore: MagicMock,
    mock_gitattributes: MagicMock,
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader: MockModelDownloader,
) -> None:
    """Test that InitService creates manifest with correct project name."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader,
    )

    service.execute("Nike", Path("/project"))

    assert len(mock_manifest.created_manifests) == 1
    _, project_name = mock_manifest.created_manifests[0]
    assert project_name == "Nike"


@patch("nest.services.init_service.InitService._setup_gitattributes")
@patch("nest.services.init_service.InitService._setup_gitignore")
def test_init_service_downloads_models_if_needed(
    mock_gitignore: MagicMock,
    mock_gitattributes: MagicMock,
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader: MockModelDownloader,
) -> None:
    """Test that InitService calls model downloader during init."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader,
    )

    service.execute("Nike", Path("/project"))

    assert mock_model_downloader.download_called is True
    assert mock_model_downloader.download_progress is True


@patch("nest.services.init_service.InitService._setup_gitattributes")
@patch("nest.services.init_service.InitService._setup_gitignore")
def test_init_service_skips_download_when_models_cached(
    mock_gitignore: MagicMock,
    mock_gitattributes: MagicMock,
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader_cached: MockModelDownloader,
) -> None:
    """Test that InitService skips download when models already cached."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader_cached,
    )

    service.execute("Nike", Path("/project"))

    # are_models_cached() returns True, so download_if_needed() should not be called
    assert mock_model_downloader_cached.download_called is False


@patch("nest.services.init_service.InitService._setup_gitattributes")
@patch("nest.services.init_service.InitService._setup_gitignore")
@patch("nest.services.init_service.status_start")
@patch("nest.services.init_service.status_done")
def test_init_service_progress_output_sequence_cached(
    mock_status_done: MagicMock,
    mock_status_start: MagicMock,
    mock_gitignore: MagicMock,
    mock_gitattributes: MagicMock,
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader_cached: MockModelDownloader,
) -> None:
    """Test progress output when models are cached (AC2)."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader_cached,
    )

    service.execute("Nike", Path("/project"))

    # Verify progress calls were made in order (AC2)
    assert mock_status_start.call_count == 3
    assert mock_status_done.call_count == 3

    # Verify the status messages match AC2 requirements
    start_calls = [call[0][0] for call in mock_status_start.call_args_list]
    assert "Creating project structure" in start_calls
    assert "Generating agent file" in start_calls
    assert "Checking ML models" in start_calls

    # Verify cached path shows "cached" suffix
    done_calls = [call[0] for call in mock_status_done.call_args_list]
    assert ("cached",) in done_calls


@patch("nest.services.init_service.InitService._setup_gitattributes")
@patch("nest.services.init_service.InitService._setup_gitignore")
@patch("nest.services.init_service.info")
@patch("nest.services.init_service.status_start")
@patch("nest.services.init_service.status_done")
def test_init_service_progress_output_sequence_download(
    mock_status_done: MagicMock,
    mock_status_start: MagicMock,
    mock_info: MagicMock,
    mock_gitignore: MagicMock,
    mock_gitattributes: MagicMock,
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader: MockModelDownloader,
) -> None:
    """Test progress output when models need download (AC2 - download path)."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader,
    )

    service.execute("Nike", Path("/project"))

    # Verify download path shows "downloading" suffix
    done_calls = [call[0] for call in mock_status_done.call_args_list]
    assert ("downloading",) in done_calls

    # Verify info message about cache path is shown
    assert mock_info.call_count == 1
    info_msg = mock_info.call_args[0][0]
    assert "cached at" in info_msg.lower()


# ---- AC1: Gitignore only ignores .nest/errors.log ----


class TestSetupGitignore:
    """Tests for InitService._setup_gitignore() — AC1."""

    def test_creates_gitignore_with_lf_newlines(self, tmp_path: Path) -> None:
        """AC1: .gitignore writes pass newline='\n' explicitly."""
        with patch(
            "pathlib.Path.write_text",
            autospec=True,
            wraps=Path.write_text,
        ) as mock_write_text:
            InitService._setup_gitignore(tmp_path)

        assert mock_write_text.call_args is not None
        assert mock_write_text.call_args.kwargs["newline"] == "\n"

    def test_creates_gitignore_with_only_errors_log(self, tmp_path: Path) -> None:
        """AC1: New .gitignore contains only .nest/errors.log."""
        InitService._setup_gitignore(tmp_path)

        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert lines == [".nest/errors.log"]

    def test_gitignore_does_not_ignore_nest_sources(self, tmp_path: Path) -> None:
        """AC1: _nest_sources/ is NOT ignored."""
        InitService._setup_gitignore(tmp_path)

        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert "_nest_sources/" not in content

    def test_gitignore_does_not_ignore_full_nest_dir(self, tmp_path: Path) -> None:
        """AC1: .nest/ (full directory) is NOT ignored."""
        InitService._setup_gitignore(tmp_path)

        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert ".nest/" not in lines

    def test_appends_to_existing_gitignore(self, tmp_path: Path) -> None:
        """Entries appended to existing .gitignore without duplicates."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n", encoding="utf-8")

        InitService._setup_gitignore(tmp_path)

        content = gitignore.read_text(encoding="utf-8")
        assert "*.pyc" in content
        assert ".nest/errors.log" in content

    def test_does_not_duplicate_existing_entry(self, tmp_path: Path) -> None:
        """Entries not duplicated when already present."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".nest/errors.log\n", encoding="utf-8")

        InitService._setup_gitignore(tmp_path)

        content = gitignore.read_text(encoding="utf-8")
        assert content.count(".nest/errors.log") == 1


# ---- AC2: Gitattributes generation ----


class TestSetupGitattributes:
    """Tests for InitService._setup_gitattributes() — AC2."""

    def test_creates_gitattributes_with_lf_newlines(self, tmp_path: Path) -> None:
        """AC2: .gitattributes writes pass newline='\n' explicitly."""
        with patch(
            "pathlib.Path.write_text",
            autospec=True,
            wraps=Path.write_text,
        ) as mock_write_text:
            InitService._setup_gitattributes(tmp_path)

        assert mock_write_text.call_args is not None
        assert mock_write_text.call_args.kwargs["newline"] == "\n"

    def test_creates_new_gitattributes(self, tmp_path: Path) -> None:
        """AC2: Creates .gitattributes with binary and text eol=lf entries."""
        InitService._setup_gitattributes(tmp_path)

        content = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
        assert "_nest_sources/**/*.pdf binary" in content
        assert "_nest_sources/**/*.docx binary" in content
        assert "_nest_sources/**/*.md text eol=lf" in content
        assert "_nest_context/**/*.md text eol=lf" in content
        assert ".nest/**/*.json text eol=lf" in content

    def test_appends_to_existing_gitattributes(self, tmp_path: Path) -> None:
        """AC2: Appends Nest entries when .gitattributes already exists."""
        gitattributes = tmp_path / ".gitattributes"
        gitattributes.write_text("*.jpg binary\n", encoding="utf-8")

        InitService._setup_gitattributes(tmp_path)

        content = gitattributes.read_text(encoding="utf-8")
        assert "*.jpg binary" in content
        assert "_nest_sources/**/*.pdf binary" in content

    def test_idempotent_does_not_duplicate(self, tmp_path: Path) -> None:
        """AC2: Running twice does not duplicate Nest entries."""
        InitService._setup_gitattributes(tmp_path)
        InitService._setup_gitattributes(tmp_path)

        content = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
        assert content.count("_nest_sources/**/*.pdf binary") == 1

    def test_contains_all_text_extensions(self, tmp_path: Path) -> None:
        """AC2: All CONTEXT_TEXT_EXTENSIONS are covered."""
        InitService._setup_gitattributes(tmp_path)

        content = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
        for ext in CONTEXT_TEXT_EXTENSIONS:
            assert f"_nest_sources/**/*{ext} text eol=lf" in content
            assert f"_nest_context/**/*{ext} text eol=lf" in content

    def test_contains_all_binary_extensions(self, tmp_path: Path) -> None:
        """AC2: All binary document extensions are covered."""
        InitService._setup_gitattributes(tmp_path)

        content = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
        for ext in SUPPORTED_EXTENSIONS:
            assert f"_nest_sources/**/*{ext} binary" in content

    def test_contains_nest_metadata_entries(self, tmp_path: Path) -> None:
        """AC2: .nest/ metadata entries are present."""
        InitService._setup_gitattributes(tmp_path)

        content = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
        assert ".nest/**/*.json text eol=lf" in content
        assert ".nest/**/*.md text eol=lf" in content
        assert ".nest/**/*.yaml text eol=lf" in content

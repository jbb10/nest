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
from nest.services.init_service import InitService


def test_init_service_calls_agent_writer(
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


def test_init_service_strips_project_name_whitespace(
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


def test_init_service_creates_all_directories(
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
    assert str(target_dir / "raw_inbox") in created_dirs
    assert str(target_dir / "processed_context") in created_dirs
    assert str(target_dir / ".github/agents") in created_dirs


def test_init_service_creates_manifest(
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


def test_init_service_creates_gitignore(
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader: MockModelDownloader,
) -> None:
    """Test that InitService creates .gitignore with raw_inbox entry."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader,
    )
    target_dir = Path("/project")

    service.execute("Nike", target_dir)

    gitignore_path = target_dir / ".gitignore"
    assert gitignore_path in mock_filesystem.written_files
    content = mock_filesystem.written_files[gitignore_path]
    assert "raw_inbox/" in content


def test_init_service_appends_to_existing_gitignore(
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader: MockModelDownloader,
) -> None:
    """Test that InitService appends to existing .gitignore."""
    target_dir = Path("/project")
    gitignore_path = target_dir / ".gitignore"

    # Simulate existing gitignore
    mock_filesystem.existing_paths.add(gitignore_path)
    mock_filesystem.file_contents[gitignore_path] = "node_modules/\n"

    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader,
    )

    service.execute("Nike", target_dir)

    content = mock_filesystem.written_files[gitignore_path]
    assert "node_modules/" in content
    assert "raw_inbox/" in content


def test_init_service_skips_gitignore_if_entry_exists(
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader: MockModelDownloader,
) -> None:
    """Test that InitService doesn't duplicate raw_inbox entry."""
    target_dir = Path("/project")
    gitignore_path = target_dir / ".gitignore"

    # Simulate existing gitignore with entry already present
    mock_filesystem.existing_paths.add(gitignore_path)
    mock_filesystem.file_contents[gitignore_path] = "raw_inbox/\n"

    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
        model_downloader=mock_model_downloader,
    )

    service.execute("Nike", target_dir)

    # Should not have written to gitignore since entry exists
    assert gitignore_path not in mock_filesystem.written_files


def test_init_service_downloads_models_if_needed(
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


def test_init_service_skips_download_when_models_cached(
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


@patch("nest.services.init_service.status_start")
@patch("nest.services.init_service.status_done")
def test_init_service_progress_output_sequence(
    mock_status_done: MagicMock,
    mock_status_start: MagicMock,
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
    mock_model_downloader_cached: MockModelDownloader,
) -> None:
    """Test that InitService calls status_start/status_done in correct sequence (AC2)."""
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


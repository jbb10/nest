"""Unit tests for InitService."""
from pathlib import Path

import pytest

from conftest import MockAgentWriter, MockFileSystem, MockManifest
from nest.core.exceptions import NestError
from nest.services.init_service import InitService


def test_init_service_calls_agent_writer(
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
) -> None:
    """Test that InitService calls agent_writer.generate() with correct args."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
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
) -> None:
    """Test that project name is stripped before passing to agent writer."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
    )

    service.execute("  Nike  ", Path("/project"))

    project_name, _ = mock_agent_writer.generated_agents[0]
    assert project_name == "Nike"


def test_init_service_rejects_empty_project_name(
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
) -> None:
    """Test that empty project name raises NestError."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
    )

    with pytest.raises(NestError, match="Project name required"):
        service.execute("", Path("/project"))


def test_init_service_rejects_whitespace_only_project_name(
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
) -> None:
    """Test that whitespace-only project name raises NestError."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
    )

    with pytest.raises(NestError, match="Project name required"):
        service.execute("   ", Path("/project"))


def test_init_service_rejects_existing_project(
    mock_filesystem: MockFileSystem,
    mock_manifest_exists: MockManifest,
    mock_agent_writer: MockAgentWriter,
) -> None:
    """Test that existing project raises NestError."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest_exists,
        agent_writer=mock_agent_writer,
    )

    with pytest.raises(NestError, match="already exists"):
        service.execute("Nike", Path("/project"))


def test_init_service_creates_all_directories(
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
) -> None:
    """Test that InitService creates all required directories."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
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
) -> None:
    """Test that InitService creates manifest with correct project name."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
    )

    service.execute("Nike", Path("/project"))

    assert len(mock_manifest.created_manifests) == 1
    _, project_name = mock_manifest.created_manifests[0]
    assert project_name == "Nike"


def test_init_service_creates_gitignore(
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
) -> None:
    """Test that InitService creates .gitignore with raw_inbox entry."""
    service = InitService(
        filesystem=mock_filesystem,
        manifest=mock_manifest,
        agent_writer=mock_agent_writer,
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
    )

    service.execute("Nike", target_dir)

    content = mock_filesystem.written_files[gitignore_path]
    assert "node_modules/" in content
    assert "raw_inbox/" in content


def test_init_service_skips_gitignore_if_entry_exists(
    mock_filesystem: MockFileSystem,
    mock_manifest: MockManifest,
    mock_agent_writer: MockAgentWriter,
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
    )

    service.execute("Nike", target_dir)

    # Should not have written to gitignore since entry exists
    assert gitignore_path not in mock_filesystem.written_files

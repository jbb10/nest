"""Integration tests for nest init command."""
from pathlib import Path
from unittest.mock import MagicMock

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.agents.vscode_writer import VSCodeAgentWriter
from nest.services.init_service import InitService


def test_init_creates_agent_file(tmp_path: Path) -> None:
    """Test that init creates the agent file."""
    # Setup service with real adapters (mock model downloader)
    filesystem = FileSystemAdapter()
    manifest = ManifestAdapter()
    agent_writer = VSCodeAgentWriter(filesystem=filesystem)

    # Mock model downloader to avoid actual downloads in tests
    mock_downloader = MagicMock()
    mock_downloader.are_models_cached.return_value = True  # Skip download
    mock_downloader.download_if_needed.return_value = None

    service = InitService(
        filesystem=filesystem,
        manifest=manifest,
        agent_writer=agent_writer,
        model_downloader=mock_downloader,
    )

    # Execute init
    service.execute("Nike", tmp_path)

    # Verify agent file exists
    agent_path = tmp_path / ".github" / "agents" / "nest.agent.md"
    assert agent_path.exists()

    # Verify agent file content
    content = agent_path.read_text()
    assert content.startswith("---\nname: nest\n")
    assert "Nike" in content
    assert "processed_context/00_MASTER_INDEX.md" in content
    assert "raw_inbox/" in content

    # Verify downloader methods were called appropriately
    mock_downloader.are_models_cached.assert_called_once()


def test_init_creates_all_directories(tmp_path: Path) -> None:
    """Test that init creates all required directories."""
    filesystem = FileSystemAdapter()
    manifest = ManifestAdapter()
    agent_writer = VSCodeAgentWriter(filesystem=filesystem)

    mock_downloader = MagicMock()
    mock_downloader.are_models_cached.return_value = True  # Skip download
    mock_downloader.download_if_needed.return_value = None

    service = InitService(
        filesystem=filesystem,
        manifest=manifest,
        agent_writer=agent_writer,
        model_downloader=mock_downloader,
    )

    service.execute("TestProject", tmp_path)

    assert (tmp_path / "raw_inbox").exists()
    assert (tmp_path / "processed_context").exists()
    assert (tmp_path / ".github" / "agents").exists()


def test_init_creates_manifest(tmp_path: Path) -> None:
    """Test that init creates manifest file."""
    filesystem = FileSystemAdapter()
    manifest = ManifestAdapter()
    agent_writer = VSCodeAgentWriter(filesystem=filesystem)

    mock_downloader = MagicMock()
    mock_downloader.are_models_cached.return_value = True  # Skip download
    mock_downloader.download_if_needed.return_value = None

    service = InitService(
        filesystem=filesystem,
        manifest=manifest,
        agent_writer=agent_writer,
        model_downloader=mock_downloader,
    )

    service.execute("Nike", tmp_path)

    manifest_path = tmp_path / ".nest_manifest.json"
    assert manifest_path.exists()

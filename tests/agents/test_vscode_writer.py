"""Unit tests for VS Code agent writer."""

from pathlib import Path

from conftest import MockFileSystem
from nest.agents.vscode_writer import VSCodeAgentWriter


def test_generate_creates_agent_file(mock_filesystem: MockFileSystem) -> None:
    """Test that generate() creates an agent file with proper content."""
    writer = VSCodeAgentWriter(filesystem=mock_filesystem)
    output_path = Path("/project/.github/agents/nest.agent.md")

    writer.generate("Nike", output_path)

    content = mock_filesystem.written_files[output_path]
    assert "name: nest" in content
    assert "description: Expert analyst for Nike project documents" in content
    assert "icon: book" in content


def test_generate_creates_parent_directory(mock_filesystem: MockFileSystem) -> None:
    """Test that generate() creates parent directory if it doesn't exist."""
    writer = VSCodeAgentWriter(filesystem=mock_filesystem)
    output_path = Path("/project/.github/agents/nest.agent.md")

    writer.generate("Nike", output_path)

    assert Path("/project/.github/agents") in mock_filesystem.created_dirs


def test_generate_skips_directory_creation_if_exists(mock_filesystem: MockFileSystem) -> None:
    """Test that generate() doesn't recreate existing directory."""
    mock_filesystem.existing_paths.add(Path("/project/.github/agents"))
    writer = VSCodeAgentWriter(filesystem=mock_filesystem)
    output_path = Path("/project/.github/agents/nest.agent.md")

    writer.generate("Nike", output_path)

    assert Path("/project/.github/agents") not in mock_filesystem.created_dirs


def test_template_interpolates_project_name(mock_filesystem: MockFileSystem) -> None:
    """Test that project name is correctly interpolated throughout template."""
    writer = VSCodeAgentWriter(filesystem=mock_filesystem)
    output_path = Path("/project/.github/agents/nest.agent.md")

    writer.generate("Acme Corp", output_path)

    content = mock_filesystem.written_files[output_path]
    assert "Acme Corp" in content
    # Check multiple occurrences
    assert content.count("Acme Corp") >= 2


def test_generate_includes_required_instructions(mock_filesystem: MockFileSystem) -> None:
    """Test that agent file includes all required instructions."""
    writer = VSCodeAgentWriter(filesystem=mock_filesystem)
    output_path = Path("/project/.github/agents/nest.agent.md")

    writer.generate("TestProject", output_path)

    content = mock_filesystem.written_files[output_path]
    # Check for key instruction elements
    assert "00_MASTER_INDEX.md" in content
    assert "processed_context/" in content
    assert "raw_inbox/" in content
    assert "cite" in content.lower() or "citation" in content.lower()


def test_generate_handles_special_characters_in_project_name(
    mock_filesystem: MockFileSystem,
) -> None:
    """Test that special characters in project name don't break template."""
    writer = VSCodeAgentWriter(filesystem=mock_filesystem)
    output_path = Path("/project/.github/agents/nest.agent.md")

    # Project name with special chars that could break YAML/Markdown
    writer.generate("O'Reilly & Associates", output_path)

    content = mock_filesystem.written_files[output_path]
    assert "O'Reilly & Associates" in content
    # Should still have valid frontmatter
    assert content.startswith("---\n")

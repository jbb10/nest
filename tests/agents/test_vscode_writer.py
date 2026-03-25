"""Unit tests for VS Code agent writer."""

from pathlib import Path

from conftest import MockFileSystem
from nest.agents.vscode_writer import VSCodeAgentWriter

# --- render() tests ---


class TestRender:
    """Tests for the render() method (AC1, AC2, AC8)."""

    def test_render_returns_string(self, mock_filesystem: MockFileSystem) -> None:
        """Test that render() returns a string."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render()

        assert isinstance(result, str)

    def test_render_contains_static_description(self, mock_filesystem: MockFileSystem) -> None:
        """Test that render() uses the static folder-agnostic description (AC5)."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render()

        assert "description: Expert analyst for documents in this project folder" in result

    def test_render_contains_no_project_name_variable(
        self, mock_filesystem: MockFileSystem
    ) -> None:
        """Test that render() does not contain any Jinja variable placeholders."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render()

        assert "{{" not in result
        assert "}}" not in result

    def test_render_does_not_write_to_filesystem(self, mock_filesystem: MockFileSystem) -> None:
        """Test that render() does NOT write to filesystem."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        writer.render()

        assert len(mock_filesystem.written_files) == 0
        assert len(mock_filesystem.created_dirs) == 0

    def test_render_matches_generate_output(self, mock_filesystem: MockFileSystem) -> None:
        """Test that render() produces same content as generate() writes."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        output_path = Path("/project/.github/agents/nest.agent.md")

        rendered = writer.render()
        writer.generate(output_path)

        assert rendered == mock_filesystem.written_files[output_path]

    def test_render_is_deterministic(self, mock_filesystem: MockFileSystem) -> None:
        """Test that render() produces identical output on repeated calls."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result1 = writer.render()
        result2 = writer.render()

        assert result1 == result2


# --- generate() tests ---


def test_generate_creates_agent_file(mock_filesystem: MockFileSystem) -> None:
    """Test that generate() creates an agent file with proper content."""
    writer = VSCodeAgentWriter(filesystem=mock_filesystem)
    output_path = Path("/project/.github/agents/nest.agent.md")

    writer.generate(output_path)

    content = mock_filesystem.written_files[output_path]
    assert "name: nest" in content
    assert "description: Expert analyst for documents in this project folder" in content
    assert "icon: book" in content


def test_generate_creates_parent_directory(mock_filesystem: MockFileSystem) -> None:
    """Test that generate() creates parent directory if it doesn't exist."""
    writer = VSCodeAgentWriter(filesystem=mock_filesystem)
    output_path = Path("/project/.github/agents/nest.agent.md")

    writer.generate(output_path)

    assert Path("/project/.github/agents") in mock_filesystem.created_dirs


def test_generate_skips_directory_creation_if_exists(mock_filesystem: MockFileSystem) -> None:
    """Test that generate() doesn't recreate existing directory."""
    mock_filesystem.existing_paths.add(Path("/project/.github/agents"))
    writer = VSCodeAgentWriter(filesystem=mock_filesystem)
    output_path = Path("/project/.github/agents/nest.agent.md")

    writer.generate(output_path)

    assert Path("/project/.github/agents") not in mock_filesystem.created_dirs


def test_generate_includes_required_instructions(mock_filesystem: MockFileSystem) -> None:
    """Test that agent file includes all required instructions."""
    writer = VSCodeAgentWriter(filesystem=mock_filesystem)
    output_path = Path("/project/.github/agents/nest.agent.md")

    writer.generate(output_path)

    content = mock_filesystem.written_files[output_path]
    # Check for key instruction elements
    assert "00_MASTER_INDEX.md" in content
    assert "_nest_context/" in content
    assert "_nest_sources/" in content
    assert "cite" in content.lower() or "citation" in content.lower()


def test_generate_body_uses_folder_agnostic_text(mock_filesystem: MockFileSystem) -> None:
    """Test that body text references 'documents in this project folder' (AC5)."""
    writer = VSCodeAgentWriter(filesystem=mock_filesystem)
    output_path = Path("/project/.github/agents/nest.agent.md")

    writer.generate(output_path)

    content = mock_filesystem.written_files[output_path]
    assert "documents in this project folder" in content
    # Should still have valid frontmatter
    assert content.startswith("---\n")

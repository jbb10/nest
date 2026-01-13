"""Unit tests for VS Code agent writer."""
from pathlib import Path

from nest.agents.vscode_writer import VSCodeAgentWriter


class MockFileSystem:
    """Mock filesystem for testing."""

    def __init__(self) -> None:
        self._files: dict[Path, str] = {}
        self._directories: set[Path] = set()

    def exists(self, path: Path) -> bool:
        """Check if path exists."""
        return path in self._files or path in self._directories

    def create_directory(self, path: Path) -> None:
        """Create directory."""
        self._directories.add(path)

    def write_text(self, path: Path, content: str) -> None:
        """Write text to file."""
        self._files[path] = content

    def read_text(self, path: Path) -> str:
        """Read text from file."""
        return self._files[path]


def test_generate_creates_agent_file() -> None:
    """Test that generate() creates an agent file with proper content."""
    # Arrange
    mock_fs = MockFileSystem()
    writer = VSCodeAgentWriter(filesystem=mock_fs)
    output_path = Path("/project/.github/agents/nest.agent.md")

    # Act
    writer.generate("Nike", output_path)

    # Assert
    content = mock_fs.read_text(output_path)
    assert "name: nest" in content
    assert "description: Expert analyst for Nike project documents" in content
    assert "icon: book" in content


def test_generate_creates_parent_directory() -> None:
    """Test that generate() creates parent directory if it doesn't exist."""
    # Arrange
    mock_fs = MockFileSystem()
    writer = VSCodeAgentWriter(filesystem=mock_fs)
    output_path = Path("/project/.github/agents/nest.agent.md")

    # Act
    writer.generate("Nike", output_path)

    # Assert
    assert mock_fs.exists(Path("/project/.github/agents"))


def test_template_interpolates_project_name() -> None:
    """Test that project name is correctly interpolated throughout template."""
    # Arrange
    mock_fs = MockFileSystem()
    writer = VSCodeAgentWriter(filesystem=mock_fs)
    output_path = Path("/project/.github/agents/nest.agent.md")

    # Act
    writer.generate("Acme Corp", output_path)

    # Assert
    content = mock_fs.read_text(output_path)
    assert "Acme Corp" in content
    # Check multiple occurrences
    assert content.count("Acme Corp") >= 2


def test_generate_includes_required_instructions() -> None:
    """Test that agent file includes all required instructions."""
    # Arrange
    mock_fs = MockFileSystem()
    writer = VSCodeAgentWriter(filesystem=mock_fs)
    output_path = Path("/project/.github/agents/nest.agent.md")

    # Act
    writer.generate("TestProject", output_path)

    # Assert
    content = mock_fs.read_text(output_path)
    # Check for key instruction elements
    assert "00_MASTER_INDEX.md" in content
    assert "processed_context/" in content
    assert "raw_inbox/" in content
    assert "cite" in content.lower() or "citation" in content.lower()

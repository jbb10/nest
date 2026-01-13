"""Shared test fixtures and mock factories.

This module provides reusable fixtures for testing Nest components.
"""

from pathlib import Path

import pytest

from nest.core.models import Manifest


class MockFileSystem:
    """Mock filesystem for testing.

    Implements FileSystemProtocol for unit tests without real I/O.
    """

    def __init__(self) -> None:
        self.created_dirs: list[Path] = []
        self.written_files: dict[Path, str] = {}
        self.existing_paths: set[Path] = set()
        self.file_contents: dict[Path, str] = {}

    def create_directory(self, path: Path) -> None:
        self.created_dirs.append(path)

    def write_text(self, path: Path, content: str) -> None:
        self.written_files[path] = content

    def read_text(self, path: Path) -> str:
        if path in self.file_contents:
            return self.file_contents[path]
        raise FileNotFoundError(f"File not found: {path}")

    def exists(self, path: Path) -> bool:
        return path in self.existing_paths

    def append_text(self, path: Path, content: str) -> None:
        existing = self.written_files.get(path, "")
        self.written_files[path] = existing + content


class MockManifest:
    """Mock manifest adapter for testing.

    Implements ManifestProtocol for unit tests without real I/O.
    """

    def __init__(self, *, manifest_exists: bool = False) -> None:
        self._exists = manifest_exists
        self.created_manifests: list[tuple[Path, str]] = []
        self.saved_manifests: list[tuple[Path, Manifest]] = []

    def exists(self, project_dir: Path) -> bool:
        return self._exists

    def create(self, project_dir: Path, project_name: str) -> Manifest:
        self.created_manifests.append((project_dir, project_name))
        return Manifest(nest_version="1.0.0", project_name=project_name)

    def load(self, project_dir: Path) -> Manifest:
        raise FileNotFoundError("No manifest")

    def save(self, project_dir: Path, manifest: Manifest) -> None:
        self.saved_manifests.append((project_dir, manifest))


@pytest.fixture
def mock_filesystem() -> MockFileSystem:
    """Provide a fresh MockFileSystem instance."""
    return MockFileSystem()


@pytest.fixture
def mock_manifest() -> MockManifest:
    """Provide a fresh MockManifest instance."""
    return MockManifest()


@pytest.fixture
def mock_manifest_exists() -> MockManifest:
    """Provide a MockManifest that reports manifest exists."""
    return MockManifest(manifest_exists=True)


class MockAgentWriter:
    """Mock agent writer for testing.

    Implements AgentWriterProtocol for unit tests without real I/O.
    """

    def __init__(self) -> None:
        self.generated_agents: list[tuple[str, Path]] = []

    def generate(self, project_name: str, output_path: Path) -> None:
        self.generated_agents.append((project_name, output_path))


@pytest.fixture
def mock_agent_writer() -> MockAgentWriter:
    """Provide a fresh MockAgentWriter instance."""
    return MockAgentWriter()

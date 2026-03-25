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
        self._manifest: Manifest | None = None
        self.created_manifests: list[Path] = []
        self.saved_manifests: list[tuple[Path, Manifest]] = []

    def exists(self, project_dir: Path) -> bool:
        return self._exists

    def create(self, project_dir: Path) -> Manifest:
        self.created_manifests.append(project_dir)
        return Manifest(nest_version="1.0.0")

    def load(self, project_dir: Path) -> Manifest:
        if self._manifest is not None:
            return self._manifest
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

    def __init__(self, template_content: str = "rendered-template") -> None:
        self.template_content = template_content
        self.generated_agents: list[Path] = []

    def render(self) -> str:
        return self.template_content

    def generate(self, output_path: Path) -> None:
        self.generated_agents.append(output_path)


@pytest.fixture
def mock_agent_writer() -> MockAgentWriter:
    """Provide a fresh MockAgentWriter instance."""
    return MockAgentWriter()


@pytest.fixture
def mock_manifest_with_project() -> MockManifest:
    """Provide a MockManifest that exists and returns a manifest."""
    mock = MockManifest(manifest_exists=True)
    mock._manifest = Manifest(nest_version="1.0.0")
    return mock


class MockModelDownloader:
    """Mock model downloader for testing.

    Implements ModelDownloaderProtocol for unit tests without real downloads.
    """

    def __init__(self, *, models_cached: bool = False) -> None:
        self._cached = models_cached
        self.download_called = False
        self.download_progress = True

    def are_models_cached(self) -> bool:
        return self._cached

    def download_if_needed(self, progress: bool = True) -> bool:
        self.download_called = True
        self.download_progress = progress
        if self._cached:
            return False  # Already cached, no download
        return True  # Downloaded

    def get_cache_path(self) -> Path:
        return Path.home() / ".cache" / "docling" / "models"


@pytest.fixture
def mock_model_downloader() -> MockModelDownloader:
    """Provide a fresh MockModelDownloader instance."""
    return MockModelDownloader()


@pytest.fixture
def mock_model_downloader_cached() -> MockModelDownloader:
    """Provide a MockModelDownloader with models already cached."""
    return MockModelDownloader(models_cached=True)

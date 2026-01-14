"""Protocol definitions for adapter interfaces.

These protocols define the contracts that adapters must implement.
Services depend on these protocols, not concrete implementations.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from nest.core.models import Manifest, ProcessingResult


@runtime_checkable
class DocumentProcessorProtocol(Protocol):
    """Protocol for document processing operations.

    Implementations handle converting documents (PDF, DOCX, PPTX, XLSX, HTML)
    to Markdown format for LLM consumption.

    Note:
        Output Markdown should exclude base64-encoded images to keep
        content token-efficient for LLM context usage.
    """

    def process(self, source: Path, output: Path) -> ProcessingResult:
        """Convert a document to Markdown.

        Args:
            source: Path to the source document file.
            output: Path where Markdown output should be written.

        Returns:
            ProcessingResult indicating success, failure, or skip status.
            On failure, the error field contains the error message.

        Note:
            Individual file failures should NOT raise exceptions.
            Instead, return a ProcessingResult with status="failed".
        """
        ...


@runtime_checkable
class ManifestProtocol(Protocol):
    """Protocol for manifest file operations.

    Implementations handle reading, writing, and checking manifest files.
    """

    def exists(self, project_dir: Path) -> bool:
        """Check if a manifest file exists in the project directory.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if .nest_manifest.json exists, False otherwise.
        """
        ...

    def create(self, project_dir: Path, project_name: str) -> Manifest:
        """Create a new manifest file with initial values.

        Args:
            project_dir: Path to the project root directory.
            project_name: Human-readable project name.

        Returns:
            The newly created Manifest instance.
        """
        ...

    def load(self, project_dir: Path) -> Manifest:
        """Load an existing manifest from file.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            The loaded Manifest instance.

        Raises:
            FileNotFoundError: If manifest file doesn't exist.
            json.JSONDecodeError: If manifest file is invalid JSON.
        """
        ...

    def save(self, project_dir: Path, manifest: Manifest) -> None:
        """Save manifest to file.

        Args:
            project_dir: Path to the project root directory.
            manifest: The Manifest instance to save.
        """
        ...


@runtime_checkable
class FileSystemProtocol(Protocol):
    """Protocol for filesystem operations.

    Implementations handle directory and file operations.
    """

    def create_directory(self, path: Path) -> None:
        """Create a directory, including parent directories.

        Args:
            path: Path to the directory to create.
        """
        ...

    def write_text(self, path: Path, content: str) -> None:
        """Write text content to a file.

        Args:
            path: Path to the file to write.
            content: Text content to write.
        """
        ...

    def read_text(self, path: Path) -> str:
        """Read text content from a file.

        Args:
            path: Path to the file to read.

        Returns:
            The text content of the file.

        Raises:
            FileNotFoundError: If file doesn't exist.
        """
        ...

    def exists(self, path: Path) -> bool:
        """Check if a path exists.

        Args:
            path: Path to check.

        Returns:
            True if path exists, False otherwise.
        """
        ...

    def append_text(self, path: Path, content: str) -> None:
        """Append text content to a file.

        Args:
            path: Path to the file to append to.
            content: Text content to append.
        """
        ...


@runtime_checkable
class AgentWriterProtocol(Protocol):
    """Protocol for generating agent instruction files.

    Extensibility: Implementations can support different platforms
    (VS Code, Cursor, generic Markdown, etc.).
    """

    def generate(self, project_name: str, output_path: Path) -> None:
        """Generate agent file at specified path.

        Args:
            project_name: Name of the project for interpolation.
            output_path: Full path where agent file should be written.

        Raises:
            IOError: If file cannot be written.
        """
        ...


@runtime_checkable
class ModelDownloaderProtocol(Protocol):
    """Protocol for ML model download operations.

    Implementations handle checking cache status and downloading
    required models for document processing.
    """

    def are_models_cached(self) -> bool:
        """Check if required models are already cached.

        Returns:
            True if all required models are present, False otherwise.
        """
        ...

    def download_if_needed(self, progress: bool = True) -> bool:
        """Download models if not already cached.

        Args:
            progress: Whether to show download progress bars.

        Returns:
            True if download occurred, False if already cached.

        Raises:
            ModelError: If download fails after retries.
        """
        ...

    def get_cache_path(self) -> Path:
        """Get the path to the model cache directory.

        Returns:
            Path to the cache directory.
        """
        ...


@runtime_checkable
class FileDiscoveryProtocol(Protocol):
    """Protocol for file discovery operations.

    Implementations handle recursive file discovery with extension filtering.
    Used to find documents in raw_inbox/ for processing.
    """

    def discover(self, directory: Path, extensions: set[str]) -> list[Path]:
        """Discover files recursively in a directory, filtered by extension.

        Searches the given directory and all subdirectories for files
        matching the specified extensions. Hidden files and directories
        (starting with '.') are excluded.

        Args:
            directory: Root directory to search.
            extensions: Set of allowed file extensions (e.g., {".pdf", ".docx"}).
                        Extensions should be lowercase with leading dot.

        Returns:
            Sorted list of absolute paths to discovered files.
            Sorting ensures deterministic ordering.

        Example:
            >>> adapter = FileDiscoveryAdapter()
            >>> files = adapter.discover(
            ...     Path("raw_inbox"),
            ...     {".pdf", ".docx"}
            ... )
        """
        ...

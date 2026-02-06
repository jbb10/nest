"""Protocol definitions for adapter interfaces.

These protocols define the contracts that adapters must implement.
Services depend on these protocols, not concrete implementations.
"""

from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

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
            ManifestError: If manifest file is invalid JSON or has invalid structure.
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

    def get_relative_path(self, source: Path, base: Path) -> Path:
        """Get path of source relative to base directory.

        Used for computing mirrored output paths by extracting the
        relative subdirectory structure from source files.

        Args:
            source: Absolute path to compute relative path for.
            base: Base directory to compute relative from.

        Returns:
            Relative Path from base to source.
        """
        ...

    def compute_output_path(
        self,
        source: Path,
        raw_dir: Path,
        output_dir: Path,
    ) -> Path:
        """Compute mirrored output path for a source file.

        Preserves subdirectory structure from raw_dir and changes
        extension to .md for the output in output_dir.

        Args:
            source: Absolute path to source file.
            raw_dir: Root of sources directory.
            output_dir: Root of context directory.

        Returns:
            Absolute path where output Markdown should be written.

        Example:
            source = /project/_nest_sources/contracts/2024/alpha.pdf
            raw_dir = /project/_nest_sources
            output_dir = /project/_nest_context
            Result: /project/_nest_context/contracts/2024/alpha.md
        """
        ...

    def delete_file(self, path: Path) -> None:
        """Delete a file from the filesystem.

        Args:
            path: Path to the file to delete.

        Note:
            Should handle missing files gracefully (missing_ok=True).
            Used for orphan cleanup when source files are removed.
        """
        ...

    def list_files(self, directory: Path) -> list[Path]:
        """List all files recursively in a directory.

        Args:
            directory: Root directory to search.

        Returns:
            Sorted list of absolute paths to all files (not directories).
            Hidden files (starting with '.') are excluded.
            Results are sorted for deterministic behavior.

        Note:
            Used for scanning processed_context/ to detect orphan files.
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


@runtime_checkable
class ModelCheckerProtocol(Protocol):
    """Protocol for ML model cache operations.

    Implementations handle checking model cache status, calculating sizes,
    and determining cache directory state for diagnostics.
    """

    def are_models_cached(self) -> bool:
        """Check if models are cached.

        Returns:
            True if all required models are cached, False otherwise.
        """
        ...

    def get_cache_path(self) -> Path:
        """Get cache directory path.

        Returns:
            Path to the model cache directory.
        """
        ...

    def get_cache_size(self) -> int:
        """Get total cache size in bytes.

        Returns:
            Total size of cached models in bytes, 0 if cache doesn't exist.
        """
        ...

    def get_cache_status(self) -> Literal["exists", "empty", "not_created"]:
        """Get cache directory status.

        Returns:
            "exists" if cache has files, "empty" if directory exists but empty,
            "not_created" if directory doesn't exist.
        """
        ...


@runtime_checkable
class ProjectCheckerProtocol(Protocol):
    """Protocol for project state validation.

    Implementations handle checking project manifest, agent file,
    and folder structure for diagnostics.
    """

    def manifest_exists(self, project_dir: Path) -> bool:
        """Check if manifest file exists.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if .nest_manifest.json exists, False otherwise.
        """
        ...

    def load_manifest(self, project_dir: Path) -> Manifest:
        """Load manifest from file.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            The loaded Manifest instance.

        Raises:
            ManifestError: If manifest file is invalid or corrupt.
        """
        ...

    def agent_file_exists(self, project_dir: Path) -> bool:
        """Check if agent file exists.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if .github/agents/nest.agent.md exists, False otherwise.
        """
        ...

    def source_folder_exists(self, project_dir: Path) -> bool:
        """Check if source folder exists.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if _nest_sources/ directory exists, False otherwise.
        """
        ...

    def context_folder_exists(self, project_dir: Path) -> bool:
        """Check if context folder exists.

        Args:
            project_dir: Path to the project root directory.

        Returns:
            True if _nest_context/ directory exists, False otherwise.
        """
        ...

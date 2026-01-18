"""E2E-specific fixtures for CLI testing.

Provides fixtures for running CLI commands via subprocess and managing
temporary project directories.
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


def docling_available() -> bool:
    """Check if Docling models are downloaded."""
    cache_dir = Path.home() / ".cache" / "docling"
    return cache_dir.exists() and any(cache_dir.iterdir())


skip_without_docling = pytest.mark.skipif(
    not docling_available(),
    reason="Docling models not downloaded. Run 'nest init' first.",
)


@dataclass
class CLIResult:
    """Result from running a CLI command."""

    exit_code: int
    stdout: str
    stderr: str


def run_cli(args: list[str], cwd: Path, timeout: int = 300) -> CLIResult:
    """Run a nest CLI command via subprocess.

    Args:
        args: Command arguments (without 'nest' prefix).
        cwd: Working directory for the command.
        timeout: Timeout in seconds. Default 300s for Docling processing.

    Returns:
        CLIResult with exit code, stdout, and stderr.
    """
    result = subprocess.run(
        ["nest", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return CLIResult(
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


@pytest.fixture
def cli_runner() -> type[CLIResult]:
    """Provide the CLIResult class for type hints in tests."""
    return CLIResult


@pytest.fixture(scope="class")
def temp_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a temp directory shared across test class.

    Uses class scope to share init overhead within the test class.
    Automatically cleaned up by pytest after all tests in class complete.
    """
    return tmp_path_factory.mktemp("nest_e2e")


@pytest.fixture
def fresh_temp_dir(tmp_path: Path) -> Path:
    """Create a fresh temp directory for a single test.

    Use this when tests need isolated directories that don't share state.
    """
    return tmp_path


@pytest.fixture
def sample_documents(temp_project: Path) -> Path:
    """Copy fixture files to raw_inbox in nested structure.

    Creates:
        raw_inbox/reports/quarterly.pdf
        raw_inbox/reports/summary.docx
        raw_inbox/presentations/deck.pptx
        raw_inbox/presentations/data.xlsx

    Returns:
        Path to the raw_inbox directory.
    """
    fixtures_dir = Path(__file__).parent / "fixtures"
    raw_inbox = temp_project / "raw_inbox"

    # Create nested structure
    reports_dir = raw_inbox / "reports"
    presentations_dir = raw_inbox / "presentations"
    reports_dir.mkdir(parents=True, exist_ok=True)
    presentations_dir.mkdir(parents=True, exist_ok=True)

    # Copy fixtures to nested structure
    shutil.copy(fixtures_dir / "quarterly.pdf", reports_dir / "quarterly.pdf")
    shutil.copy(fixtures_dir / "summary.docx", reports_dir / "summary.docx")
    shutil.copy(fixtures_dir / "deck.pptx", presentations_dir / "deck.pptx")
    shutil.copy(fixtures_dir / "data.xlsx", presentations_dir / "data.xlsx")

    return raw_inbox

"""E2E tests for nest doctor command."""

import subprocess


def test_doctor_command_runs_successfully() -> None:
    """Test that nest doctor command executes without errors."""
    result = subprocess.run(
        ["nest", "doctor"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0


def test_doctor_shows_environment_section() -> None:
    """Test that doctor displays Environment section with key components."""
    result = subprocess.run(
        ["nest", "doctor"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "Environment" in result.stdout
    assert "Python:" in result.stdout
    assert "uv:" in result.stdout
    assert "Nest:" in result.stdout


def test_doctor_shows_model_status() -> None:
    """Test that doctor displays ML Models section.

    Note: In CI/dev environments, models are typically cached, so we expect
    to see either "cached" or "not found" status. The important thing is
    that the section appears.
    """
    result = subprocess.run(
        ["nest", "doctor"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "ML Models" in result.stdout
    assert "Models:" in result.stdout


def test_doctor_shows_model_cache_path() -> None:
    """Test that doctor displays cache path for ML models."""
    result = subprocess.run(
        ["nest", "doctor"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "Cache path:" in result.stdout
    # Cache path should contain docling models path
    assert "docling" in result.stdout.lower()

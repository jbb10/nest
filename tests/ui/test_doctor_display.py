"""Tests for doctor display helpers."""

from pathlib import Path
from unittest.mock import MagicMock

from rich.console import Console

from nest.services.doctor_service import (
    EnvironmentReport,
    EnvironmentStatus,
    ModelReport,
    ModelStatus,
)
from nest.ui.doctor_display import (
    display_doctor_report,
    format_size,
)


class TestFormatSize:
    """Tests for human-readable size formatting."""

    def test_format_bytes(self) -> None:
        """Test formatting bytes."""
        assert format_size(100) == "100 B"
        assert format_size(1023) == "1023 B"

    def test_format_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        assert format_size(1024) == "1 KB"
        assert format_size(1024 * 500) == "500 KB"

    def test_format_megabytes(self) -> None:
        """Test formatting megabytes."""
        assert format_size(1024 * 1024) == "1.0 MB"
        assert format_size(1024 * 1024 * 892) == "892.0 MB"

    def test_format_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        assert format_size(1_800_000_000) == "1.7 GB"
        assert format_size(1024 * 1024 * 1024 * 2) == "2.0 GB"


class TestDisplayModelReport:
    """Tests for model report display functionality."""

    def test_display_doctor_report_with_cached_models(self) -> None:
        """Test display with model report showing cached models."""
        console = Console(file=MagicMock(), force_terminal=True, width=120)

        env_report = EnvironmentReport(
            python=EnvironmentStatus("Python", "pass", "3.11.4"),
            uv=EnvironmentStatus("uv", "pass", "0.4.12"),
            nest=EnvironmentStatus("Nest", "pass", "1.0.0"),
        )

        model_report = ModelReport(
            models=ModelStatus(
                cached=True,
                size_bytes=1_800_000_000,
                cache_path=Path.home() / ".cache" / "docling" / "models",
                cache_status="exists",
            )
        )

        # Should not raise any exceptions
        display_doctor_report(env_report, console, model_report)

    def test_display_doctor_report_with_missing_models(self) -> None:
        """Test display with model report showing models not cached."""
        console = Console(file=MagicMock(), force_terminal=True, width=120)

        env_report = EnvironmentReport(
            python=EnvironmentStatus("Python", "pass", "3.11.4"),
            uv=EnvironmentStatus("uv", "pass", "0.4.12"),
            nest=EnvironmentStatus("Nest", "pass", "1.0.0"),
        )

        model_report = ModelReport(
            models=ModelStatus(
                cached=False,
                size_bytes=None,
                cache_path=Path.home() / ".cache" / "docling" / "models",
                cache_status="not_created",
                suggestion="Run `nest init` to download models",
            )
        )

        # Should not raise any exceptions
        display_doctor_report(env_report, console, model_report)

    def test_display_doctor_report_with_empty_cache(self) -> None:
        """Test display with model report showing empty cache directory."""
        console = Console(file=MagicMock(), force_terminal=True, width=120)

        env_report = EnvironmentReport(
            python=EnvironmentStatus("Python", "pass", "3.11.4"),
            uv=EnvironmentStatus("uv", "pass", "0.4.12"),
            nest=EnvironmentStatus("Nest", "pass", "1.0.0"),
        )

        model_report = ModelReport(
            models=ModelStatus(
                cached=False,
                size_bytes=None,
                cache_path=Path.home() / ".cache" / "docling" / "models",
                cache_status="empty",
                suggestion="Run `nest init` to download models",
            )
        )

        # Should not raise any exceptions
        display_doctor_report(env_report, console, model_report)


class TestDisplayDoctorReport:
    """Tests for complete doctor report display."""

    def test_display_doctor_report_with_model_report(self) -> None:
        """Test display with both environment and model reports."""
        console = Console(file=MagicMock(), force_terminal=True, width=120)

        env_report = EnvironmentReport(
            python=EnvironmentStatus("Python", "pass", "3.11.4"),
            uv=EnvironmentStatus("uv", "pass", "0.4.12"),
            nest=EnvironmentStatus("Nest", "pass", "1.0.0"),
        )

        model_report = ModelReport(
            models=ModelStatus(
                cached=True,
                size_bytes=1_800_000_000,
                cache_path=Path.home() / ".cache" / "docling" / "models",
                cache_status="exists",
            )
        )

        # Should not raise any exceptions
        display_doctor_report(env_report, console, model_report)

    def test_display_doctor_report_without_model_report(self) -> None:
        """Test display with only environment report (no model checker)."""
        console = Console(file=MagicMock(), force_terminal=True, width=120)

        env_report = EnvironmentReport(
            python=EnvironmentStatus("Python", "pass", "3.11.4"),
            uv=EnvironmentStatus("uv", "pass", "0.4.12"),
            nest=EnvironmentStatus("Nest", "pass", "1.0.0"),
        )

        # Should not raise any exceptions
        display_doctor_report(env_report, console, None)

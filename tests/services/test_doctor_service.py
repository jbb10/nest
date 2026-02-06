"""Unit tests for DoctorService."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from nest.services.doctor_service import (
    DoctorService,
    EnvironmentReport,
    EnvironmentStatus,
    ModelReport,
    ModelStatus,
)


class TestPythonVersionCheck:
    """Tests for Python version validation."""

    def test_supported_python_version_passes(self) -> None:
        """Python 3.10+ should pass validation."""
        service = DoctorService()

        with patch("sys.version_info", (3, 11, 4)):
            status = service._check_python_version()

        assert status.name == "Python"
        assert status.status == "pass"
        assert status.current_value == "3.11.4"
        assert status.message is None
        assert status.suggestion is None

    def test_minimum_python_version_passes(self) -> None:
        """Python 3.10.0 exactly should pass."""
        service = DoctorService()

        with patch("sys.version_info", (3, 10, 0)):
            status = service._check_python_version()

        assert status.status == "pass"
        assert status.current_value == "3.10.0"

    def test_unsupported_python_version_fails(self) -> None:
        """Python <3.10 should fail validation."""
        service = DoctorService()

        with patch("sys.version_info", (3, 9, 1)):
            status = service._check_python_version()

        assert status.name == "Python"
        assert status.status == "fail"
        assert status.current_value == "3.9.1"
        assert "3.10" in status.message
        assert status.suggestion is not None


class TestUvInstallationCheck:
    """Tests for uv installation validation."""

    def test_uv_installed_and_version_detected(self) -> None:
        """uv installed with version should pass."""
        service = DoctorService()

        with patch("shutil.which", return_value="/usr/local/bin/uv"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="uv 0.4.12 (abc123)\n"
                )

                status = service._check_uv_installation()

        assert status.name == "uv"
        assert status.status == "pass"
        assert status.current_value == "0.4.12"
        assert status.message is None

    def test_uv_installed_with_unexpected_output_warns(self) -> None:
        """uv version output without version should warn."""
        service = DoctorService()

        with patch("shutil.which", return_value="/usr/local/bin/uv"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="uv\n")

                status = service._check_uv_installation()

        assert status.name == "uv"
        assert status.status == "warning"
        assert status.current_value == "found"
        assert "determine" in status.message.lower()

    def test_uv_not_in_path(self) -> None:
        """uv not found should fail with helpful suggestion."""
        service = DoctorService()

        with patch("shutil.which", return_value=None):
            status = service._check_uv_installation()

        assert status.name == "uv"
        assert status.status == "fail"
        assert status.current_value == "not found"
        assert "astral.sh" in status.suggestion

    def test_uv_found_but_version_fails(self) -> None:
        """uv found but version check fails should warn."""
        service = DoctorService()

        with patch("shutil.which", return_value="/usr/local/bin/uv"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="")

                status = service._check_uv_installation()

        assert status.name == "uv"
        assert status.status == "warning"
        assert status.current_value == "found"
        assert "version" in status.message.lower()

    def test_uv_version_command_timeout(self) -> None:
        """Timeout during version check should warn but not fail."""
        service = DoctorService()

        with patch("shutil.which", return_value="/usr/local/bin/uv"):
            with patch("subprocess.run", side_effect=TimeoutError):
                status = service._check_uv_installation()

        assert status.status == "warning"
        assert "version check failed" in status.message


class TestNestVersionCheck:
    """Tests for Nest version validation."""

    def test_nest_version_reported(self) -> None:
        """Nest version should be reported from __version__."""
        service = DoctorService()

        with patch("nest.__version__", "1.0.0"):
            with patch.object(service, "_fetch_latest_version", return_value=None):
                status = service._check_nest_version()

        assert status.name == "Nest"
        assert status.status == "pass"
        assert status.current_value == "1.0.0"

    def test_nest_version_update_available_warns(self) -> None:
        """Newer Nest version should be reported as available."""
        service = DoctorService()

        with patch("nest.__version__", "1.0.0"):
            with patch.object(service, "_fetch_latest_version", return_value="1.2.0"):
                status = service._check_nest_version()

        assert status.name == "Nest"
        assert status.status == "warning"
        assert status.current_value == "1.0.0"
        assert "available" in (status.message or "")
        assert status.suggestion is not None


class TestCheckEnvironment:
    """Tests for complete environment validation."""

    def test_check_environment_returns_complete_report(self) -> None:
        """check_environment() should return report with all checks."""
        service = DoctorService()

        with patch("sys.version_info", (3, 11, 4)):
            with patch("shutil.which", return_value="/usr/local/bin/uv"):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=0, stdout="uv 0.4.12\n"
                    )
                    with patch("nest.__version__", "1.0.0"):
                        report = service.check_environment()

        assert isinstance(report, EnvironmentReport)
        assert report.python.status == "pass"
        assert report.uv.status == "pass"
        assert report.nest.status == "pass"

    def test_all_pass_property_true_when_no_failures(self) -> None:
        """all_pass should be True when no failures."""
        report = EnvironmentReport(
            python=EnvironmentStatus("Python", "pass", "3.11.4"),
            uv=EnvironmentStatus("uv", "pass", "0.4.12"),
            nest=EnvironmentStatus("Nest", "warning", "1.0.0", message="update available"),
        )

        assert report.all_pass is True

    def test_all_pass_property_false_when_failure(self) -> None:
        """all_pass should be False when any check fails."""
        report = EnvironmentReport(
            python=EnvironmentStatus("Python", "fail", "3.9.1"),
            uv=EnvironmentStatus("uv", "pass", "0.4.12"),
            nest=EnvironmentStatus("Nest", "pass", "1.0.0"),
        )

        assert report.all_pass is False


class MockModelChecker:
    """Mock implementation of ModelCheckerProtocol for testing."""

    def __init__(
        self,
        cached: bool = True,
        size: int = 1_800_000_000,
        cache_status: str = "exists",
    ):
        self._cached = cached
        self._size = size
        self._cache_status = cache_status

    def are_models_cached(self) -> bool:
        return self._cached

    def get_cache_path(self) -> Path:
        return Path.home() / ".cache" / "docling" / "models"

    def get_cache_size(self) -> int:
        return self._size

    def get_cache_status(self) -> str:
        return self._cache_status


class TestModelValidation:
    """Tests for ML model validation functionality."""

    def test_check_ml_models_when_models_cached(self) -> None:
        """check_ml_models() should report success when models are cached."""
        mock_checker = MockModelChecker(
            cached=True, size=1_800_000_000, cache_status="exists"
        )
        service = DoctorService(model_checker=mock_checker)

        report = service.check_ml_models()

        assert report is not None
        assert isinstance(report, ModelReport)
        assert report.models.cached is True
        assert report.models.size_bytes == 1_800_000_000
        assert report.models.cache_status == "exists"
        assert report.models.suggestion is None

    def test_check_ml_models_when_models_not_cached(self) -> None:
        """check_ml_models() should report failure with suggestion when models not cached."""
        mock_checker = MockModelChecker(
            cached=False, size=0, cache_status="not_created"
        )
        service = DoctorService(model_checker=mock_checker)

        report = service.check_ml_models()

        assert report is not None
        assert report.models.cached is False
        assert report.models.size_bytes is None
        assert report.models.cache_status == "not_created"
        assert report.models.suggestion == "Run `nest init` to download models"

    def test_check_ml_models_when_cache_empty(self) -> None:
        """check_ml_models() should handle empty cache directory."""
        mock_checker = MockModelChecker(cached=False, size=0, cache_status="empty")
        service = DoctorService(model_checker=mock_checker)

        report = service.check_ml_models()

        assert report is not None
        assert report.models.cached is False
        assert report.models.cache_status == "empty"

    def test_check_ml_models_returns_none_when_no_checker(self) -> None:
        """check_ml_models() should return None when no model checker configured."""
        service = DoctorService(model_checker=None)

        report = service.check_ml_models()

        assert report is None

    def test_model_report_all_pass_true_when_cached(self) -> None:
        """ModelReport.all_pass should be True when models are cached."""
        report = ModelReport(
            models=ModelStatus(
                cached=True,
                size_bytes=1_800_000_000,
                cache_path=Path.home() / ".cache" / "docling" / "models",
                cache_status="exists",
            )
        )

        assert report.all_pass is True

    def test_model_report_all_pass_false_when_not_cached(self) -> None:
        """ModelReport.all_pass should be False when models not cached."""
        report = ModelReport(
            models=ModelStatus(
                cached=False,
                size_bytes=None,
                cache_path=Path.home() / ".cache" / "docling" / "models",
                cache_status="not_created",
            )
        )

        assert report.all_pass is False

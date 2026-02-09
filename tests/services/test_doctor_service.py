"""Unit tests for DoctorService."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from nest.services.doctor_service import (
    DoctorService,
    EnvironmentReport,
    EnvironmentStatus,
    ModelReport,
    ModelStatus,
    ProjectReport,
    ProjectStatus,
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
                mock_run.return_value = MagicMock(returncode=0, stdout="uv 0.4.12 (abc123)\n")

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
                    mock_run.return_value = MagicMock(returncode=0, stdout="uv 0.4.12\n")
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
        mock_checker = MockModelChecker(cached=True, size=1_800_000_000, cache_status="exists")
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
        mock_checker = MockModelChecker(cached=False, size=0, cache_status="not_created")
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


class TestProjectStatusDataclass:
    """Tests for ProjectStatus dataclass."""

    def test_project_status_valid_project(self) -> None:
        """ProjectStatus should hold all validation states."""
        status = ProjectStatus(
            manifest_status="valid",
            manifest_version="1.0.0",
            current_version="1.0.0",
            agent_file_present=True,
            folders_status="intact",
            suggestions=[],
        )

        assert status.manifest_status == "valid"
        assert status.manifest_version == "1.0.0"
        assert status.current_version == "1.0.0"
        assert status.agent_file_present is True
        assert status.folders_status == "intact"
        assert status.suggestions == []

    def test_project_status_with_issues(self) -> None:
        """ProjectStatus should track multiple issues."""
        status = ProjectStatus(
            manifest_status="missing",
            manifest_version=None,
            current_version="1.0.0",
            agent_file_present=False,
            folders_status="sources_missing",
            suggestions=["Run `nest init` to create project"],
        )

        assert status.manifest_status == "missing"
        assert status.manifest_version is None
        assert not status.agent_file_present
        assert status.folders_status == "sources_missing"
        assert len(status.suggestions) == 1


class TestProjectReportDataclass:
    """Tests for ProjectReport dataclass."""

    def test_project_report_all_pass_true_when_valid(self) -> None:
        """ProjectReport.all_pass should be True for valid project."""
        status = ProjectStatus(
            manifest_status="valid",
            manifest_version="1.0.0",
            current_version="1.0.0",
            agent_file_present=True,
            folders_status="intact",
            suggestions=[],
        )
        report = ProjectReport(status=status)

        assert report.all_pass is True

    def test_project_report_all_pass_false_when_manifest_missing(self) -> None:
        """ProjectReport.all_pass should be False when manifest missing."""
        status = ProjectStatus(
            manifest_status="missing",
            manifest_version=None,
            current_version="1.0.0",
            agent_file_present=True,
            folders_status="intact",
            suggestions=[],
        )
        report = ProjectReport(status=status)

        assert report.all_pass is False

    def test_project_report_all_pass_false_when_agent_missing(self) -> None:
        """ProjectReport.all_pass should be False when agent file missing."""
        status = ProjectStatus(
            manifest_status="valid",
            manifest_version="1.0.0",
            current_version="1.0.0",
            agent_file_present=False,
            folders_status="intact",
            suggestions=[],
        )
        report = ProjectReport(status=status)

        assert report.all_pass is False

    def test_project_report_all_pass_false_when_folders_missing(self) -> None:
        """ProjectReport.all_pass should be False when folders missing."""
        status = ProjectStatus(
            manifest_status="valid",
            manifest_version="1.0.0",
            current_version="1.0.0",
            agent_file_present=True,
            folders_status="sources_missing",
            suggestions=[],
        )
        report = ProjectReport(status=status)

        assert report.all_pass is False

    def test_project_report_has_warnings_true_for_agent_missing(self) -> None:
        """ProjectReport.has_warnings should be True for agent file warning."""
        status = ProjectStatus(
            manifest_status="valid",
            manifest_version="1.0.0",
            current_version="1.0.0",
            agent_file_present=False,
            folders_status="intact",
            suggestions=[],
        )
        report = ProjectReport(status=status)

        assert report.has_warnings is True

    def test_project_report_has_warnings_true_for_version_mismatch(self) -> None:
        """ProjectReport.has_warnings should be True for version mismatch."""
        status = ProjectStatus(
            manifest_status="version_mismatch",
            manifest_version="0.9.0",
            current_version="1.0.0",
            agent_file_present=True,
            folders_status="intact",
            suggestions=[],
        )
        report = ProjectReport(status=status)

        assert report.has_warnings is True

    def test_project_report_has_warnings_false_for_manifest_errors(self) -> None:
        """ProjectReport.has_warnings should be False for manifest errors."""
        status = ProjectStatus(
            manifest_status="invalid_json",
            manifest_version=None,
            current_version="1.0.0",
            agent_file_present=True,
            folders_status="intact",
            suggestions=[],
        )
        report = ProjectReport(status=status)

        assert report.has_warnings is False


class MockProjectChecker:
    """Mock implementation of ProjectCheckerProtocol for testing."""

    def __init__(
        self,
        manifest_exists: bool = True,
        manifest_error_message: str | None = None,
        manifest_version: str = "1.0.0",
        agent_exists: bool = True,
        sources_exist: bool = True,
        context_exist: bool = True,
    ) -> None:
        """Initialize mock with desired states."""
        self._manifest_exists = manifest_exists
        self._manifest_error_message = manifest_error_message
        self._manifest_version = manifest_version
        self._agent_exists = agent_exists
        self._sources_exist = sources_exist
        self._context_exist = context_exist

    def manifest_exists(self, project_dir: Path) -> bool:
        """Check if manifest exists."""
        return self._manifest_exists

    def load_manifest(self, project_dir: Path) -> MagicMock:
        """Load manifest (may raise ManifestError)."""
        if self._manifest_error_message is not None:
            from nest.core.exceptions import ManifestError

            raise ManifestError(self._manifest_error_message)

        manifest = MagicMock()
        manifest.nest_version = self._manifest_version
        return manifest

    def agent_file_exists(self, project_dir: Path) -> bool:
        """Check if agent file exists."""
        return self._agent_exists

    def source_folder_exists(self, project_dir: Path) -> bool:
        """Check if source folder exists."""
        return self._sources_exist

    def context_folder_exists(self, project_dir: Path) -> bool:
        """Check if context folder exists."""
        return self._context_exist


class TestCheckProject:
    """Tests for DoctorService.check_project()."""

    def test_check_project_returns_none_when_no_checker(self, tmp_path: Path) -> None:
        """check_project() should return None when no project checker configured."""
        service = DoctorService(project_checker=None)

        report = service.check_project(tmp_path)

        assert report is None

    def test_check_project_valid_project(self, tmp_path: Path) -> None:
        """check_project() should return report for valid project."""
        mock_checker = MockProjectChecker()
        service = DoctorService(project_checker=mock_checker)

        with patch("nest.__version__", "1.0.0"):
            report = service.check_project(tmp_path)

        assert report is not None
        assert report.status.manifest_status == "valid"
        assert report.status.agent_file_present is True
        assert report.status.folders_status == "intact"
        assert report.all_pass is True
        assert report.status.suggestions == []

    def test_check_project_missing_manifest(self, tmp_path: Path) -> None:
        """check_project() should detect missing manifest."""
        mock_checker = MockProjectChecker(manifest_exists=False)
        service = DoctorService(project_checker=mock_checker)

        with patch("nest.__version__", "1.0.0"):
            report = service.check_project(tmp_path)

        assert report is not None
        assert report.status.manifest_status == "missing"
        assert report.status.manifest_version is None
        assert report.all_pass is False
        assert "nest init" in " ".join(report.status.suggestions)

    def test_check_project_invalid_json_manifest(self, tmp_path: Path) -> None:
        """check_project() should detect invalid JSON in manifest."""
        mock_checker = MockProjectChecker(manifest_error_message="Invalid JSON")
        service = DoctorService(project_checker=mock_checker)

        with patch("nest.__version__", "1.0.0"):
            report = service.check_project(tmp_path)

        assert report is not None
        assert report.status.manifest_status == "invalid_json"
        assert report.status.manifest_version is None
        assert report.all_pass is False
        assert "nest doctor --fix" in " ".join(report.status.suggestions)

    def test_check_project_invalid_structure_manifest(self, tmp_path: Path) -> None:
        """check_project() should detect invalid structure in manifest."""
        mock_checker = MockProjectChecker(manifest_error_message="Invalid structure for manifest")
        service = DoctorService(project_checker=mock_checker)

        with patch("nest.__version__", "1.0.0"):
            report = service.check_project(tmp_path)

        assert report is not None
        assert report.status.manifest_status == "invalid_structure"
        assert report.status.manifest_version is None
        assert report.all_pass is False
        assert "nest doctor --fix" in " ".join(report.status.suggestions)

    def test_check_project_version_mismatch(self, tmp_path: Path) -> None:
        """check_project() should detect manifest version mismatch."""
        mock_checker = MockProjectChecker(manifest_version="0.9.0")
        service = DoctorService(project_checker=mock_checker)

        with patch("nest.__version__", "1.0.0"):
            report = service.check_project(tmp_path)

        assert report is not None
        assert report.status.manifest_status == "version_mismatch"
        assert report.status.manifest_version == "0.9.0"
        assert report.status.current_version == "1.0.0"
        assert report.has_warnings is True
        assert "nest update" in " ".join(report.status.suggestions)

    def test_check_project_missing_agent_file(self, tmp_path: Path) -> None:
        """check_project() should detect missing agent file."""
        mock_checker = MockProjectChecker(agent_exists=False)
        service = DoctorService(project_checker=mock_checker)

        with patch("nest.__version__", "1.0.0"):
            report = service.check_project(tmp_path)

        assert report is not None
        assert report.status.agent_file_present is False
        assert report.all_pass is False
        assert "regenerate agent" in " ".join(report.status.suggestions).lower()

    def test_check_project_missing_sources_folder(self, tmp_path: Path) -> None:
        """check_project() should detect missing sources folder."""
        mock_checker = MockProjectChecker(sources_exist=False)
        service = DoctorService(project_checker=mock_checker)

        with patch("nest.__version__", "1.0.0"):
            report = service.check_project(tmp_path)

        assert report is not None
        assert report.status.folders_status == "sources_missing"
        assert report.all_pass is False
        assert "_nest_sources" in " ".join(report.status.suggestions)

    def test_check_project_missing_context_folder(self, tmp_path: Path) -> None:
        """check_project() should detect missing context folder."""
        mock_checker = MockProjectChecker(context_exist=False)
        service = DoctorService(project_checker=mock_checker)

        with patch("nest.__version__", "1.0.0"):
            report = service.check_project(tmp_path)

        assert report is not None
        assert report.status.folders_status == "context_missing"
        assert report.all_pass is False
        assert "_nest_context" in " ".join(report.status.suggestions)

    def test_check_project_both_folders_missing(self, tmp_path: Path) -> None:
        """check_project() should detect both folders missing."""
        mock_checker = MockProjectChecker(sources_exist=False, context_exist=False)
        service = DoctorService(project_checker=mock_checker)

        with patch("nest.__version__", "1.0.0"):
            report = service.check_project(tmp_path)

        assert report is not None
        assert report.status.folders_status == "both_missing"
        assert report.all_pass is False


class TestRemediationResult:
    """Tests for RemediationResult dataclass."""

    def test_remediation_result_success(self) -> None:
        """RemediationResult should store successful remediation."""
        from nest.services.doctor_service import RemediationResult

        result = RemediationResult(
            issue="missing_manifest",
            attempted=True,
            success=True,
            message="Manifest rebuilt successfully",
        )

        assert result.issue == "missing_manifest"
        assert result.attempted is True
        assert result.success is True
        assert result.message == "Manifest rebuilt successfully"

    def test_remediation_result_failure(self) -> None:
        """RemediationResult should store failed remediation."""
        from nest.services.doctor_service import RemediationResult

        result = RemediationResult(
            issue="model_download",
            attempted=True,
            success=False,
            message="Network error: connection timeout",
        )

        assert result.issue == "model_download"
        assert result.attempted is True
        assert result.success is False
        assert "timeout" in result.message

    def test_remediation_result_not_attempted(self) -> None:
        """RemediationResult should handle not attempted."""
        from nest.services.doctor_service import RemediationResult

        result = RemediationResult(
            issue="agent_file",
            attempted=False,
            success=False,
            message="User declined",
        )

        assert result.attempted is False
        assert result.success is False


class TestRemediationReport:
    """Tests for RemediationReport dataclass."""

    def test_remediation_report_all_succeeded(self) -> None:
        """RemediationReport should detect all successes."""
        from nest.services.doctor_service import RemediationReport, RemediationResult

        results = [
            RemediationResult("manifest", True, True, "Manifest rebuilt"),
            RemediationResult("folders", True, True, "Folders created"),
        ]
        report = RemediationReport(results=results)

        assert report.all_succeeded is True
        assert report.any_attempted is True
        assert len(report.results) == 2

    def test_remediation_report_partial_failure(self) -> None:
        """RemediationReport should detect partial failures."""
        from nest.services.doctor_service import RemediationReport, RemediationResult

        results = [
            RemediationResult("manifest", True, True, "Success"),
            RemediationResult("models", True, False, "Failed"),
        ]
        report = RemediationReport(results=results)

        assert report.all_succeeded is False
        assert report.any_attempted is True

    def test_remediation_report_none_attempted(self) -> None:
        """RemediationReport should detect when nothing attempted."""
        from nest.services.doctor_service import RemediationReport, RemediationResult

        results = [
            RemediationResult("manifest", False, False, "User declined"),
            RemediationResult("folders", False, False, "User declined"),
        ]
        report = RemediationReport(results=results)

        assert report.all_succeeded is True  # None failed because none attempted
        assert report.any_attempted is False

    def test_remediation_report_empty(self) -> None:
        """RemediationReport should handle empty results."""
        from nest.services.doctor_service import RemediationReport

        report = RemediationReport(results=[])

        assert report.all_succeeded is True  # Vacuous truth
        assert report.any_attempted is False


class TestRemediationMethods:
    """Tests for DoctorService remediation methods."""

    def test_recreate_folders_both_exist(self, tmp_path: Path) -> None:
        """recreate_folders() should report no action when both exist."""
        from nest.services.doctor_service import DoctorService, RemediationResult

        # Create mock filesystem with both folders existing
        mock_fs = MagicMock()
        mock_fs.exists.side_effect = lambda p: True  # Both exist

        service = DoctorService()
        result = service.recreate_folders(tmp_path, mock_fs)

        assert isinstance(result, RemediationResult)
        assert result.issue == "missing_folders"
        assert result.attempted is False
        assert result.success is True
        assert "already exist" in result.message.lower()

    def test_recreate_folders_creates_missing(self, tmp_path: Path) -> None:
        """recreate_folders() should create missing folders."""
        from nest.services.doctor_service import DoctorService

        # Mock filesystem where neither folder exists
        mock_fs = MagicMock()
        mock_fs.exists.return_value = False

        service = DoctorService()
        result = service.recreate_folders(tmp_path, mock_fs)

        assert result.attempted is True
        assert result.success is True
        # Should have called create_directory for both folders
        assert mock_fs.create_directory.call_count == 2

    def test_regenerate_agent_file_success(self, tmp_path: Path) -> None:
        """regenerate_agent_file() should use AgentWriterProtocol."""
        from nest.services.doctor_service import DoctorService, RemediationResult

        mock_writer = MagicMock()
        service = DoctorService()

        result = service.regenerate_agent_file(tmp_path, "TestProject", mock_writer)

        assert isinstance(result, RemediationResult)
        assert result.attempted is True
        assert result.success is True
        assert mock_writer.generate.called

    def test_regenerate_agent_file_handles_error(self, tmp_path: Path) -> None:
        """regenerate_agent_file() should handle generation errors."""
        from nest.services.doctor_service import DoctorService

        mock_writer = MagicMock()
        mock_writer.generate.side_effect = OSError("Write failed")

        service = DoctorService()
        result = service.regenerate_agent_file(tmp_path, "TestProject", mock_writer)

        assert result.attempted is True
        assert result.success is False
        assert "failed" in result.message.lower()

    def test_download_models_when_checker_none(self, tmp_path: Path) -> None:
        """download_models() should fail gracefully when no model checker."""
        from nest.services.doctor_service import DoctorService, RemediationResult

        service = DoctorService(model_checker=None)
        result = service.download_models()

        assert isinstance(result, RemediationResult)
        assert result.attempted is False
        assert result.success is False
        assert "not available" in result.message.lower() or "no checker" in result.message.lower()

    def test_download_models_success(self) -> None:
        """download_models() should trigger model download."""
        from nest.services.doctor_service import DoctorService

        mock_checker = MagicMock()
        mock_checker.download_if_needed.return_value = True

        service = DoctorService(model_checker=mock_checker)
        result = service.download_models()

        assert result.attempted is True
        assert result.success is True
        assert mock_checker.download_if_needed.called


class TestRebuildManifest:
    """Tests for DoctorService.rebuild_manifest()."""

    def test_rebuild_manifest_no_manifest_adapter(self, tmp_path: Path) -> None:
        """rebuild_manifest() should fail when no manifest adapter."""
        from nest.services.doctor_service import DoctorService

        service = DoctorService(manifest_adapter=None)
        result = service.rebuild_manifest(tmp_path, "TestProject")

        assert result.attempted is False
        assert result.success is False
        assert "not available" in result.message.lower()

    def test_rebuild_manifest_no_filesystem_adapter(self, tmp_path: Path) -> None:
        """rebuild_manifest() should fail when no filesystem adapter."""
        from nest.services.doctor_service import DoctorService

        mock_manifest = MagicMock()
        service = DoctorService(manifest_adapter=mock_manifest, filesystem=None)
        result = service.rebuild_manifest(tmp_path, "TestProject")

        assert result.attempted is False
        assert result.success is False
        assert "not available" in result.message.lower()

    def test_rebuild_manifest_empty_sources(self, tmp_path: Path) -> None:
        """rebuild_manifest() should create empty manifest when no sources."""
        from nest.services.doctor_service import DoctorService

        mock_manifest = MagicMock()
        mock_fs = MagicMock()

        service = DoctorService(manifest_adapter=mock_manifest, filesystem=mock_fs)

        # Sources directory doesn't exist - simulating no sources
        # (tmp_path / "_nest_sources" not created)

        result = service.rebuild_manifest(tmp_path, "TestProject", mock_fs)

        assert result.attempted is True
        assert result.success is True
        assert "empty" in result.message.lower() or "no sources" in result.message.lower()

    def test_rebuild_manifest_with_processed_files(self, tmp_path: Path) -> None:
        """rebuild_manifest() should restore entries from processed files."""
        from nest.services.doctor_service import DoctorService

        # Create real directories and files
        sources_dir = tmp_path / "_nest_sources"
        context_dir = tmp_path / "_nest_context"
        sources_dir.mkdir()
        context_dir.mkdir()

        # Create source file
        source_file = sources_dir / "doc.pdf"
        source_file.write_text("dummy content")

        # Create matching processed output
        output_file = context_dir / "doc.md"
        output_file.write_text("# Processed content")

        mock_manifest = MagicMock()
        mock_fs = MagicMock()
        mock_fs.list_files.return_value = [source_file]

        service = DoctorService(manifest_adapter=mock_manifest, filesystem=mock_fs)
        result = service.rebuild_manifest(tmp_path, "TestProject", mock_fs)

        assert result.attempted is True
        assert result.success is True
        assert "1 files restored" in result.message
        assert mock_manifest.save.called


class TestGetProjectName:
    """Tests for DoctorService._get_project_name()."""

    def test_get_project_name_from_manifest(self, tmp_path: Path) -> None:
        """_get_project_name() should return name from manifest if available."""
        from nest.services.doctor_service import DoctorService

        mock_manifest = MagicMock()
        mock_manifest.exists.return_value = True
        mock_manifest.load.return_value = MagicMock(project_name="MyProject")

        service = DoctorService(manifest_adapter=mock_manifest)
        name = service._get_project_name(tmp_path)

        assert name == "MyProject"

    def test_get_project_name_default_when_no_manifest(self, tmp_path: Path) -> None:
        """_get_project_name() should return default when no manifest."""
        from nest.services.doctor_service import DoctorService

        service = DoctorService(manifest_adapter=None)
        name = service._get_project_name(tmp_path)

        assert name == "Nest Project"

    def test_get_project_name_default_when_manifest_error(self, tmp_path: Path) -> None:
        """_get_project_name() should return default when manifest load fails."""
        from nest.services.doctor_service import DoctorService

        mock_manifest = MagicMock()
        mock_manifest.exists.return_value = True
        mock_manifest.load.side_effect = Exception("Load failed")

        service = DoctorService(manifest_adapter=mock_manifest)
        name = service._get_project_name(tmp_path)

        assert name == "Nest Project"

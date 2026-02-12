"""Tests for SubprocessRunnerAdapter.

Covers AC6: SubprocessRunnerProtocol satisfaction, arg passthrough,
error propagation, and default timeout.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from nest.adapters.protocols import SubprocessRunnerProtocol
from nest.adapters.subprocess_runner import UV_DEFAULT_TIMEOUT, SubprocessRunnerAdapter


class TestProtocolSatisfaction:
    """AC6: SubprocessRunnerAdapter satisfies SubprocessRunnerProtocol."""

    def test_isinstance_check(self) -> None:
        adapter = SubprocessRunnerAdapter()
        assert isinstance(adapter, SubprocessRunnerProtocol)


class TestRun:
    """AC6: run() passes args through to subprocess.run."""

    @patch("nest.adapters.subprocess_runner.subprocess.run")
    def test_passes_args_to_subprocess(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["uv", "tool", "install", "--force", "pkg@v1.0.0"],
            returncode=0,
            stdout="ok",
            stderr="",
        )
        adapter = SubprocessRunnerAdapter()
        result = adapter.run(["uv", "tool", "install", "--force", "pkg@v1.0.0"])

        mock_run.assert_called_once_with(
            ["uv", "tool", "install", "--force", "pkg@v1.0.0"],
            capture_output=True,
            text=True,
            timeout=UV_DEFAULT_TIMEOUT,
            check=True,
        )
        assert result.returncode == 0

    @patch("nest.adapters.subprocess_runner.subprocess.run")
    def test_uses_custom_timeout(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["cmd"], returncode=0, stdout="", stderr=""
        )
        adapter = SubprocessRunnerAdapter()
        adapter.run(["cmd"], timeout=60)

        mock_run.assert_called_once_with(
            ["cmd"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )

    @patch("nest.adapters.subprocess_runner.subprocess.run")
    def test_uses_constructor_default_timeout(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["cmd"], returncode=0, stdout="", stderr=""
        )
        adapter = SubprocessRunnerAdapter(default_timeout=30)
        adapter.run(["cmd"])

        mock_run.assert_called_once_with(
            ["cmd"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

    def test_default_timeout_is_120(self) -> None:
        assert UV_DEFAULT_TIMEOUT == 120  # noqa: PLR2004


class TestErrorPropagation:
    """AC6: run() propagates subprocess errors."""

    @patch("nest.adapters.subprocess_runner.subprocess.run")
    def test_propagates_called_process_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["uv", "tool", "install"], stderr="failed"
        )
        adapter = SubprocessRunnerAdapter()

        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            adapter.run(["uv", "tool", "install"])

        assert exc_info.value.returncode == 1

    @patch("nest.adapters.subprocess_runner.subprocess.run")
    def test_propagates_timeout_expired(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["uv", "tool", "install"], timeout=120
        )
        adapter = SubprocessRunnerAdapter()

        with pytest.raises(subprocess.TimeoutExpired):
            adapter.run(["uv", "tool", "install"])

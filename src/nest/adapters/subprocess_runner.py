"""Subprocess runner adapter for testable command execution.

Wraps ``subprocess.run`` behind ``SubprocessRunnerProtocol`` so that
services (e.g., ``UpdateService``) can execute shell commands without
directly depending on ``subprocess``.
"""

import subprocess

UV_DEFAULT_TIMEOUT = 120  # seconds — uv install can be slow on first run


class SubprocessRunnerAdapter:
    """Adapter wrapping subprocess.run for testable command execution.

    Used by ``UpdateService`` to execute ``uv tool install`` commands.
    Injectable via ``SubprocessRunnerProtocol`` for testing.
    """

    def __init__(self, *, default_timeout: int = UV_DEFAULT_TIMEOUT) -> None:
        """Initialize the adapter.

        Args:
            default_timeout: Default timeout in seconds for commands.
        """
        self._default_timeout = default_timeout

    def run(
        self,
        args: list[str],
        *,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a command via subprocess.

        Args:
            args: Command and arguments list.
            timeout: Timeout in seconds. Uses default if None.

        Returns:
            CompletedProcess result with captured stdout/stderr.

        Raises:
            subprocess.CalledProcessError: If command returns non-zero exit code.
            subprocess.TimeoutExpired: If command exceeds timeout.
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        return subprocess.run(  # noqa: S603
            args,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            check=True,
        )

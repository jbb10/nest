"""Git client adapter for querying remote tags.

Wraps ``subprocess`` calls to ``git ls-remote --tags`` to discover
available version tags from a remote repository.
"""

import subprocess

from nest.core.exceptions import ConfigError

GIT_TIMEOUT_SECONDS = 10


def _clean_url(remote_url: str) -> str:
    """Strip ``git+`` prefix if present for git CLI compatibility."""
    return remote_url.removeprefix("git+")


class GitClientAdapter:
    """Adapter for querying git remote tags.

    Wraps subprocess calls to ``git ls-remote --tags`` to discover
    available version tags from a remote repository.
    """

    def __init__(self, *, timeout: int = GIT_TIMEOUT_SECONDS) -> None:
        """Initialize the adapter.

        Args:
            timeout: Timeout in seconds for git network operations.
        """
        self._timeout = timeout

    def list_tags(self, remote_url: str) -> list[str]:
        """Query remote repository for version tags.

        Executes ``git ls-remote --tags <url>`` and parses output to
        extract tag names.

        Args:
            remote_url: Git remote URL. Handles ``git+https://...`` prefix
                        by stripping the ``git+`` part.

        Returns:
            List of tag name strings (e.g., ``["v1.0.0", "v1.2.1"]``).

        Raises:
            ConfigError: If git command fails or network is unavailable.
        """
        url = _clean_url(remote_url)
        try:
            result = subprocess.run(  # noqa: S603, S607
                ["git", "ls-remote", "--tags", url],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as err:
            raise ConfigError(
                "Cannot reach update server. Check your internet connection."
            ) from err

        return self._parse_tags(result.stdout)

    @staticmethod
    def _parse_tags(stdout: str) -> list[str]:
        """Parse ``git ls-remote --tags`` output into tag names.

        Args:
            stdout: Raw stdout from the git command.

        Returns:
            List of tag name strings with ``refs/tags/`` prefix stripped.
            Entries ending with ``^{}`` (dereferenced annotated tags) are excluded.
        """
        tags: list[str] = []
        for line in stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 2:  # noqa: PLR2004
                continue
            ref = parts[1]
            if ref.endswith("^{}"):
                continue
            tag_name = ref.removeprefix("refs/tags/")
            if tag_name:
                tags.append(tag_name)
        return tags

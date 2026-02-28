"""Tests for adapters/git_client.py — GitClientAdapter.

Covers AC #1 (Git Remote Tag Query), AC #6 (Network Error Handling),
AC #7 (No Tags Found), AC #8 (GitClientProtocol satisfaction).
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from nest.adapters.git_client import GitClientAdapter, _clean_url
from nest.adapters.protocols import GitClientProtocol
from nest.core.exceptions import ConfigError

SAMPLE_LS_REMOTE = (
    "abc123def456\trefs/tags/v0.1.0\n"
    "abc123def456\trefs/tags/v0.1.0^{}\n"
    "def789ghi012\trefs/tags/v0.1.1\n"
    "def789ghi012\trefs/tags/v0.1.1^{}\n"
    "ghi345jkl678\trefs/tags/v0.1.2\n"
    "ghi345jkl678\trefs/tags/v0.1.2^{}\n"
    "mno901pqr234\trefs/tags/latest\n"
)


# ---------------------------------------------------------------------------
# AC #8: Protocol Satisfaction
# ---------------------------------------------------------------------------


class TestProtocol:
    """Tests for GitClientProtocol compliance."""

    def test_satisfies_protocol(self) -> None:
        """AC #8: GitClientAdapter satisfies GitClientProtocol."""
        assert isinstance(GitClientAdapter(), GitClientProtocol)


# ---------------------------------------------------------------------------
# AC #1: Git Remote Tag Query
# ---------------------------------------------------------------------------


class TestListTags:
    """Tests for GitClientAdapter.list_tags()."""

    @patch("nest.adapters.git_client.subprocess.run")
    def test_parses_valid_output(self, mock_run: MagicMock) -> None:
        """AC #1: Parses git ls-remote output into tag list."""
        mock_run.return_value = MagicMock(stdout=SAMPLE_LS_REMOTE, returncode=0)
        adapter = GitClientAdapter()

        tags = adapter.list_tags("git+https://github.com/jbb10/nest")

        assert "v0.1.0" in tags
        assert "v0.1.1" in tags
        assert "v0.1.2" in tags
        assert "latest" in tags  # Filtering is done in core/version.py

    @patch("nest.adapters.git_client.subprocess.run")
    def test_ignores_deref_entries(self, mock_run: MagicMock) -> None:
        """AC #1: Entries ending with ^{} are excluded."""
        mock_run.return_value = MagicMock(stdout=SAMPLE_LS_REMOTE, returncode=0)
        adapter = GitClientAdapter()

        tags = adapter.list_tags("https://github.com/jbb10/nest")

        assert not any(t.endswith("^{}") for t in tags)

    @patch("nest.adapters.git_client.subprocess.run")
    def test_strips_git_plus_prefix(self, mock_run: MagicMock) -> None:
        """AC #1: Strips git+ prefix from URL before calling git."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        adapter = GitClientAdapter()

        adapter.list_tags("git+https://github.com/jbb10/nest")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1].get("args", [])
        assert "https://github.com/jbb10/nest" in cmd
        assert "git+https://github.com/jbb10/nest" not in cmd

    @patch("nest.adapters.git_client.subprocess.run")
    def test_passes_url_without_git_prefix_unchanged(self, mock_run: MagicMock) -> None:
        """AC #1: URLs without git+ prefix passed as-is."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        adapter = GitClientAdapter()

        adapter.list_tags("https://github.com/jbb10/nest")

        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1].get("args", [])
        assert "https://github.com/jbb10/nest" in cmd


# ---------------------------------------------------------------------------
# AC #7: No Tags Found
# ---------------------------------------------------------------------------


class TestNoTags:
    """Tests for empty tag scenarios."""

    @patch("nest.adapters.git_client.subprocess.run")
    def test_empty_output_returns_empty_list(self, mock_run: MagicMock) -> None:
        """AC #7: Empty stdout returns empty list."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        adapter = GitClientAdapter()

        tags = adapter.list_tags("https://github.com/jbb10/nest")

        assert tags == []

    @patch("nest.adapters.git_client.subprocess.run")
    def test_whitespace_only_output_returns_empty_list(self, mock_run: MagicMock) -> None:
        """AC #7: Whitespace-only stdout returns empty list."""
        mock_run.return_value = MagicMock(stdout="  \n  \n", returncode=0)
        adapter = GitClientAdapter()

        tags = adapter.list_tags("https://github.com/jbb10/nest")

        assert tags == []


# ---------------------------------------------------------------------------
# AC #6: Network Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error scenarios."""

    @patch("nest.adapters.git_client.subprocess.run")
    def test_raises_config_error_on_subprocess_failure(self, mock_run: MagicMock) -> None:
        """AC #6: CalledProcessError raises ConfigError."""
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        adapter = GitClientAdapter()

        with pytest.raises(ConfigError, match="Cannot reach update server"):
            adapter.list_tags("https://github.com/jbb10/nest")

    @patch("nest.adapters.git_client.subprocess.run")
    def test_raises_config_error_on_timeout(self, mock_run: MagicMock) -> None:
        """AC #6: TimeoutExpired raises ConfigError."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)
        adapter = GitClientAdapter()

        with pytest.raises(ConfigError, match="Cannot reach update server"):
            adapter.list_tags("https://github.com/jbb10/nest")

    @patch("nest.adapters.git_client.subprocess.run")
    def test_raises_config_error_on_os_error(self, mock_run: MagicMock) -> None:
        """AC #6: OSError (git not found) raises ConfigError."""
        mock_run.side_effect = OSError("git not found")
        adapter = GitClientAdapter()

        with pytest.raises(ConfigError, match="Cannot reach update server"):
            adapter.list_tags("https://github.com/jbb10/nest")

    def test_custom_timeout_parameter(self) -> None:
        """Constructor accepts custom timeout."""
        adapter = GitClientAdapter(timeout=30)
        assert adapter._timeout == 30  # noqa: SLF001


# ---------------------------------------------------------------------------
# _clean_url helper
# ---------------------------------------------------------------------------


class TestCleanUrl:
    """Tests for _clean_url()."""

    def test_strips_git_plus(self) -> None:
        """Strips git+ prefix."""
        assert _clean_url("git+https://github.com/jbb10/nest") == ("https://github.com/jbb10/nest")

    def test_no_prefix_unchanged(self) -> None:
        """URLs without git+ prefix are unchanged."""
        assert _clean_url("https://github.com/jbb10/nest") == ("https://github.com/jbb10/nest")


# ---------------------------------------------------------------------------
# _parse_tags edge cases
# ---------------------------------------------------------------------------


class TestParseTags:
    """Tests for _parse_tags malformed input handling."""

    @patch("nest.adapters.git_client.subprocess.run")
    def test_skips_empty_tag_names(self, mock_run: MagicMock) -> None:
        """Malformed lines with empty ref path produce no tags."""
        malformed = "abc123\trefs/tags/\ndef456\trefs/tags/v1.0.0\n"
        mock_run.return_value = MagicMock(stdout=malformed, returncode=0)
        adapter = GitClientAdapter()

        tags = adapter.list_tags("https://example.com/repo")

        assert tags == ["v1.0.0"]

    @patch("nest.adapters.git_client.subprocess.run")
    def test_skips_lines_without_tab(self, mock_run: MagicMock) -> None:
        """Lines missing tab delimiter are skipped."""
        malformed = "no-tab-line\nabc123\trefs/tags/v1.0.0\n"
        mock_run.return_value = MagicMock(stdout=malformed, returncode=0)
        adapter = GitClientAdapter()

        tags = adapter.list_tags("https://example.com/repo")

        assert tags == ["v1.0.0"]

"""Tests for core/version.py — Semver parsing, sorting, comparison.

Covers AC #2 (Semver Parsing), AC #3 (Version Sorting),
AC #4 (Non-Semver Tags Filtered), AC #5 (Version Comparison Annotations).
"""

import pytest

from nest.core.version import Version, compare_versions, is_newer, parse_version, sort_versions

# ---------------------------------------------------------------------------
# AC #2: Semver Parsing
# ---------------------------------------------------------------------------


class TestParseVersion:
    """Tests for parse_version()."""

    def test_parse_with_v_prefix(self) -> None:
        """AC #2: Parses 'v1.2.3' correctly."""
        result = parse_version("v1.2.3")
        assert result == Version(1, 2, 3)

    def test_parse_without_v_prefix(self) -> None:
        """AC #2: Parses '1.2.3' correctly."""
        result = parse_version("1.2.3")
        assert result == Version(1, 2, 3)

    def test_parse_zero_versions(self) -> None:
        """AC #2: Parses '0.0.0' correctly."""
        result = parse_version("v0.0.0")
        assert result == Version(0, 0, 0)

    def test_parse_large_numbers(self) -> None:
        """AC #2: Parses large version numbers."""
        result = parse_version("v10.20.300")
        assert result == Version(10, 20, 300)

    def test_parse_strips_whitespace(self) -> None:
        """AC #2: Strips leading/trailing whitespace."""
        result = parse_version("  v1.0.0  ")
        assert result == Version(1, 0, 0)

    def test_returns_none_for_non_semver_latest(self) -> None:
        """AC #4: Returns None for 'latest'."""
        assert parse_version("latest") is None

    def test_returns_none_for_non_semver_beta(self) -> None:
        """AC #4: Returns None for 'beta'."""
        assert parse_version("beta") is None

    def test_returns_none_for_non_semver_docs_update(self) -> None:
        """AC #4: Returns None for 'docs-update'."""
        assert parse_version("docs-update") is None

    def test_returns_none_for_missing_patch(self) -> None:
        """AC #4: Returns None for 'v1.2' (missing patch)."""
        assert parse_version("v1.2") is None

    def test_returns_none_for_extra_segments(self) -> None:
        """AC #4: Returns None for 'v1.2.3.4' (extra segment)."""
        assert parse_version("v1.2.3.4") is None

    def test_returns_none_for_prerelease(self) -> None:
        """AC #4: Returns None for 'v1.2.3-beta' (prerelease)."""
        assert parse_version("v1.2.3-beta") is None

    def test_returns_none_for_empty_string(self) -> None:
        """AC #4: Returns None for empty string."""
        assert parse_version("") is None


# ---------------------------------------------------------------------------
# AC #3: Version Sorting (Newest First)
# ---------------------------------------------------------------------------


class TestSortVersions:
    """Tests for sort_versions()."""

    def test_sorts_newest_first(self) -> None:
        """AC #3: Versions returned sorted newest-first."""
        tags = ["v1.0.0", "v1.3.1", "v1.2.0", "v1.4.0", "v1.1.0"]
        result = sort_versions(tags)
        assert result == ["1.4.0", "1.3.1", "1.2.0", "1.1.0", "1.0.0"]

    def test_strips_v_prefix_in_output(self) -> None:
        """AC #3: Output versions have v prefix stripped."""
        result = sort_versions(["v2.0.0", "v1.0.0"])
        assert result == ["2.0.0", "1.0.0"]

    def test_handles_mixed_prefix(self) -> None:
        """AC #3: Handles mix of v-prefixed and non-prefixed."""
        result = sort_versions(["v1.0.0", "2.0.0", "v1.5.0"])
        assert result == ["2.0.0", "1.5.0", "1.0.0"]

    def test_filters_non_semver(self) -> None:
        """AC #4: Non-semver tags are filtered out."""
        tags = ["v1.0.0", "latest", "beta", "v2.0.0", "docs-update"]
        result = sort_versions(tags)
        assert result == ["2.0.0", "1.0.0"]

    def test_empty_list(self) -> None:
        """AC #7: Returns empty list when given empty input."""
        assert sort_versions([]) == []

    def test_all_non_semver(self) -> None:
        """AC #4: Returns empty when all tags are non-semver."""
        assert sort_versions(["latest", "beta", "nightly"]) == []

    def test_patch_ordering(self) -> None:
        """AC #3: Patch versions sorted correctly."""
        tags = ["v1.0.2", "v1.0.0", "v1.0.1"]
        result = sort_versions(tags)
        assert result == ["1.0.2", "1.0.1", "1.0.0"]

    def test_deduplicates_normalized_versions(self) -> None:
        """Duplicate tags with different prefixes are deduplicated."""
        tags = ["v1.0.0", "1.0.0", "v2.0.0"]
        result = sort_versions(tags)
        assert result == ["2.0.0", "1.0.0"]


# ---------------------------------------------------------------------------
# AC #5: Version Comparison Annotations
# ---------------------------------------------------------------------------


class TestCompareVersions:
    """Tests for compare_versions()."""

    def test_annotates_latest_and_installed(self) -> None:
        """AC #5: Annotates latest and installed versions correctly."""
        result = compare_versions("0.1.2", ["0.1.3", "0.1.2", "0.1.1", "0.1.0"])
        assert result == [
            ("0.1.3", "(latest)"),
            ("0.1.2", "(installed)"),
            ("0.1.1", ""),
            ("0.1.0", ""),
        ]

    def test_current_is_latest(self) -> None:
        """AC #5: When current is latest, annotated with both."""
        result = compare_versions("0.1.3", ["0.1.3", "0.1.2", "0.1.1"])
        assert result == [
            ("0.1.3", "(installed) (latest)"),
            ("0.1.2", ""),
            ("0.1.1", ""),
        ]

    def test_current_not_in_list(self) -> None:
        """AC #5: When current version not in available list."""
        result = compare_versions("0.0.9", ["0.1.3", "0.1.2", "0.1.1"])
        assert result == [
            ("0.1.3", "(latest)"),
            ("0.1.2", ""),
            ("0.1.1", ""),
        ]

    def test_single_version_is_installed_and_latest(self) -> None:
        """AC #5: Single version that matches current."""
        result = compare_versions("1.0.0", ["1.0.0"])
        assert result == [("1.0.0", "(installed) (latest)")]

    def test_single_version_not_installed(self) -> None:
        """AC #5: Single version that doesn't match current."""
        result = compare_versions("0.9.0", ["1.0.0"])
        assert result == [("1.0.0", "(latest)")]

    def test_empty_available(self) -> None:
        """AC #7: Empty available list returns empty result."""
        assert compare_versions("1.0.0", []) == []

    def test_handles_v_prefix_in_current(self) -> None:
        """AC #5: Handles v prefix in current version string."""
        result = compare_versions("v0.1.2", ["0.1.3", "0.1.2"])
        assert result == [
            ("0.1.3", "(latest)"),
            ("0.1.2", "(installed)"),
        ]


# ---------------------------------------------------------------------------
# is_newer helper
# ---------------------------------------------------------------------------


class TestIsNewer:
    """Tests for is_newer()."""

    def test_newer_patch(self) -> None:
        """Detects newer patch version."""
        assert is_newer("1.0.1", "1.0.0") is True

    def test_newer_minor(self) -> None:
        """Detects newer minor version."""
        assert is_newer("1.1.0", "1.0.9") is True

    def test_newer_major(self) -> None:
        """Detects newer major version."""
        assert is_newer("2.0.0", "1.9.9") is True

    def test_not_newer_equal(self) -> None:
        """Equal versions: not newer."""
        assert is_newer("1.0.0", "1.0.0") is False

    def test_not_newer_older(self) -> None:
        """Older version: not newer."""
        assert is_newer("1.0.0", "1.0.1") is False

    def test_handles_v_prefix(self) -> None:
        """Handles v prefix on both args."""
        assert is_newer("v2.0.0", "v1.0.0") is True

    def test_raises_on_invalid_a(self) -> None:
        """Raises ValueError for non-semver version_a."""
        with pytest.raises(ValueError, match="Invalid semver"):
            is_newer("latest", "1.0.0")

    def test_raises_on_invalid_b(self) -> None:
        """Raises ValueError for non-semver version_b."""
        with pytest.raises(ValueError, match="Invalid semver"):
            is_newer("1.0.0", "beta")

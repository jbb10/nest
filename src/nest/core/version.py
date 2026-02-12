"""Semantic version parsing, sorting, and comparison.

Pure business logic for working with semver version strings.
No I/O operations — this module depends only on the standard library.
"""

import re
from typing import NamedTuple

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class Version(NamedTuple):
    """Parsed semantic version components.

    Attributes:
        major: Major version number.
        minor: Minor version number.
        patch: Patch version number.
    """

    major: int
    minor: int
    patch: int


def parse_version(tag: str) -> Version | None:
    """Parse a version string into components.

    Handles both ``"v1.2.3"`` and ``"1.2.3"`` formats.  Returns *None* for
    non-semver strings (e.g., ``"latest"``, ``"beta"``, ``"docs-update"``).

    Args:
        tag: Version tag string to parse.

    Returns:
        Version tuple if valid semver, None otherwise.
    """
    match = _SEMVER_RE.match(tag.strip())
    if match is None:
        return None
    return Version(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _strip_v(tag: str) -> str:
    """Remove optional ``v`` prefix from a version string."""
    return tag[1:] if tag.startswith("v") else tag


def sort_versions(tags: list[str]) -> list[str]:
    """Sort version tags newest-first, filtering non-semver.

    Args:
        tags: Raw tag strings from git remote.

    Returns:
        Sorted version strings (without ``v`` prefix), newest first.
        Non-semver tags are excluded.
    """
    seen: set[str] = set()
    parsed: list[tuple[Version, str]] = []
    for tag in tags:
        v = parse_version(tag)
        if v is not None:
            stripped = _strip_v(tag)
            if stripped not in seen:
                seen.add(stripped)
                parsed.append((v, stripped))
    parsed.sort(key=lambda pair: pair[0], reverse=True)
    return [ver_str for _, ver_str in parsed]


def compare_versions(
    current: str,
    available: list[str],
) -> list[tuple[str, str]]:
    """Annotate available versions relative to current.

    Args:
        current: Currently installed version string (without ``v`` prefix).
        available: Sorted list of available version strings (without ``v`` prefix).

    Returns:
        List of ``(version, annotation)`` tuples.
        Annotations: ``"(latest)"`` for newest, ``"(installed)"`` for current,
        ``""`` otherwise.
    """
    current_clean = _strip_v(current)
    result: list[tuple[str, str]] = []
    for i, ver in enumerate(available):
        ver_clean = _strip_v(ver)
        if i == 0:
            if ver_clean == current_clean:
                result.append((ver, "(installed) (latest)"))
            else:
                result.append((ver, "(latest)"))
        elif ver_clean == current_clean:
            result.append((ver, "(installed)"))
        else:
            result.append((ver, ""))
    return result


def is_newer(version_a: str, version_b: str) -> bool:
    """Check if *version_a* is newer than *version_b*.

    Args:
        version_a: First version string.
        version_b: Second version string.

    Returns:
        True if version_a > version_b.

    Raises:
        ValueError: If either string is not valid semver.
    """
    va = parse_version(version_a)
    vb = parse_version(version_b)
    if va is None or vb is None:
        msg = f"Invalid semver: {version_a!r}, {version_b!r}"
        raise ValueError(msg)
    return va > vb

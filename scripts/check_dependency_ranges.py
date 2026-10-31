"""Assert that direct dependency ranges and uv.lock agree.

Users install nest with ``uv tool install``, which ignores uv.lock and
resolves the newest versions the pyproject.toml ranges permit. Every
direct runtime dependency therefore declares a three-component
compatible-release range (``~=X.Y.Z``): patch releases flow to users,
while minor and major upstream releases reach users only through a
reviewed pull request that raises the range (issue #52).

This script fails when a direct dependency uses any other specifier, or
when the committed uv.lock resolves a dependency outside its declared
range, so the ranges CI tests cannot drift from the ranges users
install. Run it from the repository root (``make check-deps``).
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path
from typing import Any, NamedTuple, cast

_REPO_ROOT = Path(__file__).resolve().parent.parent

# PEP 440 compatible release: ~=X.Y.Z means >=X.Y.Z, <X.Y+1.0, so a
# three-component anchor keeps every minor release out of a fresh resolve.
_COMPATIBLE_RELEASE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)~=(?P<version>\d+\.\d+\.\d+)$"
)
_LOCKED_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


class VersionAnchor(NamedTuple):
    """The ``X.Y.Z`` anchor of a compatible-release range."""

    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def _canonical(name: str) -> str:
    """Normalize a distribution name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def satisfies_anchor(version: str, anchor: VersionAnchor) -> bool:
    """Check whether a locked ``X.Y.Z`` version lies inside the ``~=anchor`` range."""
    if _LOCKED_VERSION.match(version) is None:
        return False
    major, minor, patch = (int(part) for part in version.split("."))
    return (major, minor) == (anchor.major, anchor.minor) and patch >= anchor.patch


def direct_dependency_ranges(
    pyproject_path: Path,
) -> tuple[dict[str, VersionAnchor], list[str]]:
    """Read ``[project].dependencies``, returning anchors and policy violations.

    Args:
        pyproject_path: Path to the pyproject.toml to inspect.

    Returns:
        A ``(anchors, problems)`` pair. ``anchors`` maps every dependency
        that follows the policy to its range anchor; ``problems`` describes
        every dependency that does not.
    """
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = cast(dict[str, Any], data.get("project", {}))
    dependencies = cast(list[Any], project.get("dependencies", []))
    anchors: dict[str, VersionAnchor] = {}
    problems: list[str] = []
    for requirement in dependencies:
        if not isinstance(requirement, str):
            problems.append(f"{requirement!r}: not a dependency string")
            continue
        match = _COMPATIBLE_RELEASE.match(requirement.replace(" ", ""))
        if match is None:
            problems.append(
                f"{requirement}: direct dependencies must use a three-component "
                "compatible-release specifier (~=X.Y.Z)"
            )
            continue
        major, minor, patch = (int(part) for part in match["version"].split("."))
        anchors[_canonical(match["name"])] = VersionAnchor(major, minor, patch)
    return anchors, problems


def locked_versions(lock_path: Path) -> dict[str, str]:
    """Map every locked package to its locked version.

    Packages without a version (nest itself, whose version is dynamic) are
    skipped.
    """
    data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    packages = cast(list[dict[str, Any]], data.get("package", []))
    versions: dict[str, str] = {}
    for package in packages:
        name = package.get("name")
        version = package.get("version")
        if isinstance(name, str) and isinstance(version, str):
            versions[_canonical(name)] = version
    return versions


def check_ranges(pyproject_path: Path, lock_path: Path) -> list[str]:
    """Return a description of every range-policy violation (empty when compliant)."""
    anchors, problems = direct_dependency_ranges(pyproject_path)
    locked = locked_versions(lock_path)
    for name, anchor in sorted(anchors.items()):
        version = locked.get(name)
        if version is None:
            problems.append(f"{name}: not recorded in {lock_path.name}")
        elif not satisfies_anchor(version, anchor):
            problems.append(
                f"{name}~={anchor}: {lock_path.name} resolves {version}, outside the range"
            )
    return problems


def main() -> int:
    """Run the check against the repository's pyproject.toml and uv.lock."""
    problems = check_ranges(_REPO_ROOT / "pyproject.toml", _REPO_ROOT / "uv.lock")
    if problems:
        print("dependency range policy violations:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("dependency ranges OK: every direct dependency is ~=X.Y.Z and locked in range")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

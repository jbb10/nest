"""Tests for scripts/check_dependency_ranges.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from check_dependency_ranges import (
    VersionAnchor,
    check_ranges,
    direct_dependency_ranges,
    locked_versions,
    main,
    satisfies_anchor,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _write_pyproject(path: Path, dependencies: list[str]) -> None:
    lines = ["[project]", 'name = "example"', 'version = "1.0.0"', "dependencies = ["]
    lines += [f'    "{dependency}",' for dependency in dependencies]
    lines += ["]"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_lock(path: Path, packages: list[tuple[str, str | None]]) -> None:
    lines = ["version = 1"]
    for name, version in packages:
        lines += ["", "[[package]]", f'name = "{name}"']
        if version is not None:
            lines += [f'version = "{version}"']
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestSatisfiesAnchor:
    @pytest.mark.parametrize(
        ("version", "anchor", "expected"),
        [
            ("2.140.0", VersionAnchor(2, 140, 0), True),
            ("2.140.5", VersionAnchor(2, 140, 0), True),
            ("2.141.0", VersionAnchor(2, 140, 0), False),
            ("3.0.0", VersionAnchor(2, 140, 0), False),
            ("2.139.9", VersionAnchor(2, 140, 0), False),
            ("2.140", VersionAnchor(2, 140, 0), False),
            ("2.140.0rc1", VersionAnchor(2, 140, 0), False),
        ],
    )
    def test_membership(self, version: str, anchor: VersionAnchor, expected: bool) -> None:
        assert satisfies_anchor(version, anchor) is expected


class TestDirectDependencyRanges:
    def test_compatible_release_ranges_are_collected(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        _write_pyproject(pyproject, ["typer~=0.26.8", "rich~=15.0.0"])

        anchors, problems = direct_dependency_ranges(pyproject)

        assert problems == []
        assert anchors == {"typer": VersionAnchor(0, 26, 8), "rich": VersionAnchor(15, 0, 0)}

    def test_names_are_canonicalized(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        _write_pyproject(pyproject, ["PyYAML~=6.0.3"])

        anchors, problems = direct_dependency_ranges(pyproject)

        assert problems == []
        assert anchors == {"pyyaml": VersionAnchor(6, 0, 3)}

    @pytest.mark.parametrize(
        "requirement",
        ["typer>=0.26.8", "typer~=0.26", "typer==0.26.8", "typer", "typer~=0.26.8rc1"],
    )
    def test_non_policy_specifiers_are_rejected(self, tmp_path: Path, requirement: str) -> None:
        pyproject = tmp_path / "pyproject.toml"
        _write_pyproject(pyproject, [requirement])

        _, problems = direct_dependency_ranges(pyproject)

        assert problems == [
            requirement + ": direct dependencies must use a three-component compatible-release "
            "specifier (~=X.Y.Z)"
        ]


class TestLockedVersions:
    def test_packages_without_a_version_are_skipped(self, tmp_path: Path) -> None:
        lock = tmp_path / "uv.lock"
        _write_lock(lock, [("nest", None), ("typer", "0.26.8")])

        assert locked_versions(lock) == {"typer": "0.26.8"}


class TestCheckRanges:
    def test_compliant_files_produce_no_problems(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        lock = tmp_path / "uv.lock"
        _write_pyproject(pyproject, ["typer~=0.26.8"])
        _write_lock(lock, [("typer", "0.26.8")])

        assert check_ranges(pyproject, lock) == []

    def test_newer_patch_inside_the_range_is_compliant(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        lock = tmp_path / "uv.lock"
        _write_pyproject(pyproject, ["typer~=0.26.8"])
        _write_lock(lock, [("typer", "0.26.9")])

        assert check_ranges(pyproject, lock) == []

    def test_locked_version_outside_the_range_fails(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        lock = tmp_path / "uv.lock"
        _write_pyproject(pyproject, ["typer~=0.26.8"])
        _write_lock(lock, [("typer", "0.27.0")])

        problems = check_ranges(pyproject, lock)

        assert problems == ["typer~=0.26.8: uv.lock resolves 0.27.0, outside the range"]

    def test_dependency_missing_from_the_lock_fails(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        lock = tmp_path / "uv.lock"
        _write_pyproject(pyproject, ["typer~=0.26.8"])
        _write_lock(lock, [("rich", "15.0.0")])

        problems = check_ranges(pyproject, lock)

        assert problems == ["typer: not recorded in uv.lock"]

    def test_bad_specifier_and_bad_lock_version_are_both_reported(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        lock = tmp_path / "uv.lock"
        _write_pyproject(pyproject, ["typer>=0.26.8", "rich~=15.0.0"])
        _write_lock(lock, [("rich", "16.0.0")])

        problems = check_ranges(pyproject, lock)

        assert problems == [
            "typer>=0.26.8: direct dependencies must use a three-component "
            "compatible-release specifier (~=X.Y.Z)",
            "rich~=15.0.0: uv.lock resolves 16.0.0, outside the range",
        ]


class TestRepositoryCompliance:
    def test_repository_ranges_and_lock_are_compliant(self) -> None:
        assert check_ranges(REPO_ROOT / "pyproject.toml", REPO_ROOT / "uv.lock") == []

    def test_main_succeeds_on_the_repository(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main() == 0
        assert "dependency ranges OK" in capsys.readouterr().out

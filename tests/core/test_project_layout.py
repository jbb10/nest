"""Tests for project layout detection."""

from pathlib import Path

from nest.core.paths import AGENT_DIR, AGENT_FILES
from nest.core.project_layout import detect_project


def test_empty_directory_is_not_a_project(tmp_path: Path) -> None:
    layout = detect_project(tmp_path)
    assert not layout.is_nest_project
    assert not layout.initialized
    assert layout.missing_agent_files == tuple(AGENT_FILES)


def test_manifest_marks_project_initialized(tmp_path: Path) -> None:
    (tmp_path / ".nest").mkdir()
    (tmp_path / ".nest" / "manifest.json").write_text("{}")
    layout = detect_project(tmp_path)
    assert layout.initialized
    assert layout.is_nest_project
    assert layout.meta_dir


def test_legacy_project_is_a_project_but_not_initialized(tmp_path: Path) -> None:
    (tmp_path / ".nest_manifest.json").write_text("{}")
    layout = detect_project(tmp_path)
    assert layout.legacy_manifest
    assert layout.is_nest_project
    assert not layout.initialized


def test_partial_project_with_only_sources_is_a_project(tmp_path: Path) -> None:
    (tmp_path / "_nest_sources").mkdir()
    layout = detect_project(tmp_path)
    assert layout.sources_dir
    assert not layout.context_dir
    assert layout.is_nest_project


def test_reports_individual_missing_agent_files(tmp_path: Path) -> None:
    agent_dir = tmp_path / AGENT_DIR
    agent_dir.mkdir(parents=True)
    for name in AGENT_FILES[1:]:
        (agent_dir / name).write_text("x")
    layout = detect_project(tmp_path)
    assert layout.missing_agent_files == (AGENT_FILES[0],)
    assert not layout.agent_files_present

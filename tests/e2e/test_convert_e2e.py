"""E2E tests for the convert command.

Tests run the actual CLI via subprocess with real file I/O and real Docling
processing, in isolated temporary workspaces outside any Nest project.
"""

import shutil
from pathlib import Path

import pytest

from .conftest import run_cli, skip_without_docling
from .test_image_description_e2e import CANNED_DESCRIPTION, MockVisionServer

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _copy_fixture(name: str, dest: Path) -> Path:
    """Copy a fixture file to dest (creating parents) and return the target path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(_FIXTURES_DIR / name, dest)
    return dest


@pytest.mark.e2e
class TestConvertErrorPathsE2E:
    """E2E tests for convert error paths that need no Docling models."""

    def test_convert_missing_path_fails_clearly(self, fresh_temp_dir: Path) -> None:
        """A path that does not exist exits 1 with a clear reason."""
        result = run_cli(["convert", "missing.pdf"], cwd=fresh_temp_dir)

        assert result.exit_code == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        output = result.stdout + result.stderr
        assert "Convert failed" in output
        assert "Path not found" in output

    def test_convert_unsupported_single_file_fails_clearly(self, fresh_temp_dir: Path) -> None:
        """A single unsupported file exits 1 naming the unsupported type."""
        archive = fresh_temp_dir / "archive.zip"
        archive.write_bytes(b"PK\x03\x04" + b"\x00" * 32)

        result = run_cli(["convert", str(archive)], cwd=fresh_temp_dir)

        assert result.exit_code == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        output = result.stdout + result.stderr
        assert "Convert failed" in output
        assert "Unsupported file type" in output
        assert ".zip" in output


@pytest.mark.e2e
@skip_without_docling
class TestConvertE2E:
    """E2E tests for nest convert outside any project.

    These tests require Docling models to be downloaded.
    """

    def test_convert_single_file_writes_markdown_next_to_original(
        self, fresh_temp_dir: Path
    ) -> None:
        """Converting one PDF writes q1.md next to it and creates nothing else."""
        _copy_fixture("quarterly.pdf", fresh_temp_dir / "reports" / "q1.pdf")

        result = run_cli(["convert", "reports/q1.pdf"], cwd=fresh_temp_dir)

        assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        output_md = fresh_temp_dir / "reports" / "q1.md"
        assert output_md.exists(), "Expected reports/q1.md next to the original"
        assert output_md.stat().st_size > 0
        # No project artifacts anywhere
        assert not (fresh_temp_dir / ".nest").exists()
        assert not (fresh_temp_dir / "_nest_context").exists()
        assert list(fresh_temp_dir.rglob("manifest.json")) == []
        assert "Converted: 1" in result.stdout

    def test_convert_directory_recursively_with_passthrough_untouched(
        self, fresh_temp_dir: Path
    ) -> None:
        """A directory converts recursively; text files stay untouched; hidden dirs skipped."""
        docs = fresh_temp_dir / "docs"
        _copy_fixture("quarterly.pdf", docs / "reports" / "q1.pdf")
        _copy_fixture("summary.docx", docs / "reports" / "summary.docx")
        notes = docs / "notes.txt"
        notes.write_text("original notes\n", encoding="utf-8", newline="\n")
        _copy_fixture("quarterly.pdf", docs / ".hidden" / "secret.pdf")

        result = run_cli(["convert", "docs"], cwd=fresh_temp_dir)

        assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert (docs / "reports" / "q1.md").exists()
        assert (docs / "reports" / "summary.md").exists()
        # Passthrough text file left in place, content untouched
        assert notes.read_text() == "original notes\n"
        assert "left in place" in result.stdout
        # Hidden directory not converted
        assert not (docs / ".hidden" / "secret.md").exists()
        # No project artifacts
        assert not (fresh_temp_dir / ".nest").exists()

    def test_convert_output_mirrors_tree_with_passthrough_copies(
        self, fresh_temp_dir: Path
    ) -> None:
        """--output mirrors the tree and copies passthrough files; originals untouched."""
        docs = fresh_temp_dir / "docs"
        out = fresh_temp_dir / "out"
        _copy_fixture("quarterly.pdf", docs / "reports" / "q1.pdf")
        (docs / "notes.txt").write_text("original notes\n", encoding="utf-8", newline="\n")

        result = run_cli(["convert", "docs", "--output", "out"], cwd=fresh_temp_dir)

        assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert (out / "reports" / "q1.md").exists()
        assert (out / "notes.txt").read_text() == "original notes\n"
        # Originals untouched: no markdown written next to the source
        assert not (docs / "reports" / "q1.md").exists()
        assert "Converted: 2" in result.stdout

    def test_convert_rerun_skips_existing_then_force_regenerates(
        self, fresh_temp_dir: Path
    ) -> None:
        """A rerun skips existing outputs (exit 0); --force re-converts."""
        _copy_fixture("quarterly.pdf", fresh_temp_dir / "q1.pdf")

        first = run_cli(["convert", "q1.pdf"], cwd=fresh_temp_dir)
        assert first.exit_code == 0, f"stdout: {first.stdout}\nstderr: {first.stderr}"
        assert "Converted: 1" in first.stdout

        second = run_cli(["convert", "q1.pdf"], cwd=fresh_temp_dir)
        assert second.exit_code == 0, f"stdout: {second.stdout}\nstderr: {second.stderr}"
        assert "Converted: 0" in second.stdout
        assert "Skipped:   1" in second.stdout
        assert "Outputs already present: 1" in second.stdout

        forced = run_cli(["convert", "q1.pdf", "--force"], cwd=fresh_temp_dir)
        assert forced.exit_code == 0, f"stdout: {forced.stdout}\nstderr: {forced.stderr}"
        assert "Converted: 1" in forced.stdout

    def test_convert_corrupt_file_fails_others_continue(self, fresh_temp_dir: Path) -> None:
        """A corrupt file fails with a reason and non-zero exit; others still convert."""
        docs = fresh_temp_dir / "docs"
        _copy_fixture("corrupt.pdf", docs / "corrupt.pdf")
        _copy_fixture("summary.docx", docs / "valid.docx")

        result = run_cli(["convert", "docs"], cwd=fresh_temp_dir)

        assert result.exit_code != 0, (
            f"Expected non-zero exit with a failure, got 0: {result.stdout}"
        )
        assert (docs / "valid.md").exists(), "Valid file should still convert"
        assert not (docs / "corrupt.md").exists()
        assert "Failed:    1" in result.stdout
        assert "corrupt.pdf" in result.stdout
        assert "Converted: 1" in result.stdout

    def test_convert_inside_project_leaves_project_state_untouched(
        self, initialized_project: Path
    ) -> None:
        """Convert behaves identically inside a project and touches no project state."""
        project_dir = initialized_project
        _copy_fixture("quarterly.pdf", project_dir / "notes" / "q1.pdf")

        manifest_path = project_dir / ".nest" / "manifest.json"
        manifest_before = manifest_path.read_text()
        context_before = sorted(
            str(p.relative_to(project_dir)) for p in (project_dir / "_nest_context").rglob("*")
        )

        result = run_cli(["convert", "notes"], cwd=project_dir)

        assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert (project_dir / "notes" / "q1.md").exists()
        # Project state untouched
        assert manifest_path.read_text() == manifest_before
        context_after = sorted(
            str(p.relative_to(project_dir)) for p in (project_dir / "_nest_context").rglob("*")
        )
        assert context_after == context_before

    def test_convert_describes_images_with_mock_vision(self, fresh_temp_dir: Path) -> None:
        """Image descriptions land in the output markdown next to the original."""
        _copy_fixture("image_doc.pdf", fresh_temp_dir / "image_doc.pdf")

        with MockVisionServer(response=CANNED_DESCRIPTION) as server:
            result = run_cli(
                ["convert", "image_doc.pdf"],
                cwd=fresh_temp_dir,
                timeout=300,
                env=server.env_vars(),
            )

        assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert server.call_count > 0, "Expected the vision model to be called"
        content = (fresh_temp_dir / "image_doc.md").read_text()
        assert CANNED_DESCRIPTION in content, (
            f"Expected canned description in output markdown.\nstdout: {result.stdout}"
        )
        assert "Images described:" in result.stdout

    def test_convert_vision_reports_activity_and_completes_batches(
        self, fresh_temp_dir: Path
    ) -> None:
        """Real PDF conversion reports work and finishes a batch before reading more PDFs."""
        for number in range(5):
            fixture = "image_doc.pdf" if number == 0 else "quarterly.pdf"
            _copy_fixture(fixture, fresh_temp_dir / f"report-{number}.pdf")

        with MockVisionServer(response=CANNED_DESCRIPTION) as server:
            result = run_cli(
                ["convert", "."],
                cwd=fresh_temp_dir,
                timeout=300,
                env=server.env_vars(),
            )

        assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert server.call_count > 0
        assert "Preparing conversion models" in result.stdout
        assert "Converting document 1 of 5" in result.stdout
        assert result.stdout.index("Describing images: 4 documents") < result.stdout.index(
            "Converting document 5 of 5"
        )
        assert "Describing images: 1 document" in result.stdout
        assert "Converted: 5" in result.stdout
        for number in range(5):
            assert (fresh_temp_dir / f"report-{number}.md").stat().st_size > 0
        assert CANNED_DESCRIPTION in (fresh_temp_dir / "report-0.md").read_text()

    @pytest.mark.parametrize("verbose", [False, True])
    def test_convert_no_llm_skips_image_descriptions(
        self, fresh_temp_dir: Path, verbose: bool
    ) -> None:
        """--no-llm converts without any LLM call or description."""
        _copy_fixture("image_doc.pdf", fresh_temp_dir / "image_doc.pdf")

        args = ["convert", "image_doc.pdf", "--no-llm"]
        if verbose:
            args.append("--verbose")
        with MockVisionServer(response=CANNED_DESCRIPTION) as server:
            result = run_cli(
                args,
                cwd=fresh_temp_dir,
                timeout=300,
                env=server.env_vars(),
            )

        assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert server.call_count == 0, "Expected no LLM calls with --no-llm"
        output = result.stdout + result.stderr
        assert ("INFO [RapidOCR]" in output) is verbose, output
        if not verbose:
            for diagnostic in (
                "[RapidOCR]",
                "UserWarning:",
                "Loading weights:",
                "slow image processor",
            ):
                assert diagnostic not in output, output
        content = (fresh_temp_dir / "image_doc.md").read_text()
        assert CANNED_DESCRIPTION not in content
        assert "disabled (--no-llm)" in result.stdout


@pytest.mark.e2e
class TestConvertLLMOnlyE2E:
    """E2E tests for nest convert --llm-only with a mocked vision model."""

    def test_llm_only_writes_the_model_transcription_without_docling(
        self, fresh_temp_dir: Path
    ) -> None:
        """An image file is prepared from the model's Markdown, without loading Docling models."""
        _copy_fixture("notes.png", fresh_temp_dir / "notes.png")
        transcript = "# Notes\n\n| Metric | Value |\n| --- | --- |\n| Growth | 69% |"

        with MockVisionServer(response=transcript) as server:
            result = run_cli(
                ["convert", "notes.png", "--llm-only"],
                cwd=fresh_temp_dir,
                env=server.env_vars(),
            )

        assert result.exit_code == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert server.call_count == 1
        assert (fresh_temp_dir / "notes.md").read_text() == transcript + "\n"
        assert "Preparing conversion models" not in result.stdout
        assert "Pages transcribed by the LLM: 1" in result.stdout

    def test_llm_only_unreadable_page_fails_the_document(self, fresh_temp_dir: Path) -> None:
        """A page the model reports as unreadable fails the document and writes nothing."""
        _copy_fixture("notes.png", fresh_temp_dir / "notes.png")

        with MockVisionServer(response="NEST_UNREADABLE_PAGE") as server:
            result = run_cli(
                ["convert", "notes.png", "--llm-only"],
                cwd=fresh_temp_dir,
                env=server.env_vars(),
            )

        assert result.exit_code == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert server.call_count == 1
        assert not (fresh_temp_dir / "notes.md").exists()
        assert "could not read the page" in result.stdout + result.stderr

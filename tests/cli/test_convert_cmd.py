"""Tests for the convert command CLI."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from rich.console import Console
from typer.testing import CliRunner

from nest.cli.main import app
from nest.core.exceptions import NestError
from nest.core.models import (
    Activity,
    ConvertFailure,
    ConvertResult,
    ConvertSkip,
    DiscoveredFile,
)
from nest.ui.conversion import display_convert_summary as _display_convert_summary

runner = CliRunner()


def _make_plan(root: Path, pending: int = 0, skipped: int = 0) -> MagicMock:
    """Build a mock ConvertPlan with real DiscoveredFile lists."""
    plan = MagicMock()
    plan.root = root
    plan.pending = [
        DiscoveredFile(path=root / f"file{i}.pdf", status="new", checksum=f"sum{i}")
        for i in range(pending)
    ]
    plan.skipped = [
        DiscoveredFile(
            path=root / f"skip{i}.txt",
            status="new",
            checksum=f"skipsum{i}",
            collision_reason="Text file; left in place",
        )
        for i in range(skipped)
    ]
    return plan


def _make_result(**overrides: object) -> ConvertResult:
    """Build a ConvertResult with defaults for the summary display."""
    defaults: dict[str, object] = {
        "root": Path("/tmp/docs"),
        "processed_count": 2,
        "skipped_count": 1,
        "failed_count": 0,
        "skips": [ConvertSkip(path=Path("/tmp/docs/notes.txt"), reason="Text file; left in place")],
        "failures": [],
    }
    defaults.update(overrides)
    return ConvertResult.model_validate(defaults)


class TestConvertCommandHelp:
    """Tests for convert command help text."""

    def test_convert_registered_in_main_app(self) -> None:
        """The convert command is registered next to sync."""
        result = runner.invoke(app, ["convert", "--help"])

        assert result.exit_code == 0
        assert "Convert" in result.output

    def test_convert_help_displays_all_flags(self) -> None:
        """Help should show --output, --force and --no-llm."""
        result = runner.invoke(app, ["convert", "--help"])

        assert result.exit_code == 0
        output = result.output
        assert "--output" in output
        assert "--force" in output
        assert "--no-llm" in output
        assert "--llm-only" in output


class TestConvertCommandErrors:
    """Tests for convert command error paths."""

    @patch("nest.cli.convert_cmd.create_convert_service")
    def test_convert_missing_path_fails_with_reason(
        self, mock_create_service: MagicMock, tmp_path: Path
    ) -> None:
        """A missing path exits non-zero with a clear reason."""
        mock_service = MagicMock()
        mock_service.plan.side_effect = NestError(f"Path not found: {tmp_path / 'nope.pdf'}")
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["convert", str(tmp_path / "nope.pdf")])

        assert result.exit_code == 1
        assert "Convert failed" in result.output
        assert "Path not found" in result.output

    @patch("nest.cli.convert_cmd.create_convert_service")
    def test_convert_unsupported_single_file_fails_with_reason(
        self, mock_create_service: MagicMock, tmp_path: Path
    ) -> None:
        """An unsupported single file exits non-zero with a clear reason."""
        mock_service = MagicMock()
        mock_service.plan.side_effect = NestError("Unsupported file type: .zip")
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["convert", str(tmp_path / "archive.zip")])

        assert result.exit_code == 1
        assert "Convert failed" in result.output
        assert "Unsupported file type" in result.output


class TestConvertCommandRun:
    """Tests for the convert command happy path and exit codes."""

    @patch("nest.cli.convert_cmd.create_convert_service")
    def test_convert_attributes_quality_warnings_to_each_document(
        self, mock_create_service: MagicMock, tmp_path: Path
    ) -> None:
        service = mock_create_service.return_value
        service.plan.return_value = _make_plan(tmp_path, pending=2)

        def execute(plan, progress_callback, activity_callback):
            for index, source in enumerate(plan.pending, start=1):
                activity_callback(
                    Activity(stage="converting", files=[source.path], current=index, total=2)
                )
                logging.getLogger("MatchingPostProcessor").warning(
                    "1 of 514 pdf cells matched neither a row nor a column band and were dropped"
                )
                progress_callback(source.path.name)
            return _make_result(root=tmp_path, processed_count=2, skipped_count=0, skips=[])

        service.execute.side_effect = execute
        result = runner.invoke(app, ["convert", str(tmp_path), "--no-llm"])

        assert result.exit_code == 0, result.output
        summary = result.output.split("Review recommended:")[1]
        assert "file0.pdf" in summary
        assert "file1.pdf" in summary
        assert summary.count("Table extraction dropped some content") == 2
        assert "MatchingPostProcessor" not in result.output

    @patch("nest.cli.convert_cmd.create_convert_service")
    def test_convert_success_shows_summary(
        self, mock_create_service: MagicMock, tmp_path: Path
    ) -> None:
        """A successful run shows the summary with counts and exits zero."""
        mock_service = MagicMock()
        mock_service.plan.return_value = _make_plan(tmp_path, pending=2)
        mock_service.execute.return_value = _make_result()
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["convert", str(tmp_path)])

        assert result.exit_code == 0
        assert "Convert complete" in result.output
        assert "Converted: 2" in result.output
        assert "Skipped:   1" in result.output
        assert "Failed:    0" in result.output

    @patch("nest.cli.convert_cmd.create_convert_service")
    def test_convert_exit_nonzero_when_any_file_failed(
        self, mock_create_service: MagicMock, tmp_path: Path
    ) -> None:
        """The exit code is non-zero if any file failed."""
        mock_service = MagicMock()
        mock_service.plan.return_value = _make_plan(tmp_path, pending=1)
        mock_service.execute.return_value = _make_result(
            failed_count=1,
            failures=[
                ConvertFailure(path=Path("/tmp/docs/bad.pdf"), reason="Docling convert failed: x")
            ],
        )
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["convert", str(tmp_path)])

        assert result.exit_code == 1
        assert "Failed:    1" in result.output

    @patch("nest.cli.convert_cmd.create_convert_service")
    def test_convert_exit_zero_with_skips_only(
        self, mock_create_service: MagicMock, tmp_path: Path
    ) -> None:
        """Skipped files alone do not make the exit code non-zero."""
        mock_service = MagicMock()
        mock_service.plan.return_value = _make_plan(tmp_path, skipped=1)
        mock_service.execute.return_value = _make_result(processed_count=0, skipped_count=1)
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["convert", str(tmp_path)])

        assert result.exit_code == 0

    @patch("nest.cli.convert_cmd.create_convert_service")
    def test_convert_passes_flags_to_plan(
        self, mock_create_service: MagicMock, tmp_path: Path
    ) -> None:
        """--output and --force are forwarded to plan()."""
        mock_service = MagicMock()
        mock_service.plan.return_value = _make_plan(tmp_path)
        mock_service.execute.return_value = _make_result()
        mock_create_service.return_value = mock_service
        out = tmp_path / "out"

        result = runner.invoke(app, ["convert", str(tmp_path), "--output", str(out), "--force"])

        assert result.exit_code == 0
        mock_service.plan.assert_called_once_with(
            tmp_path.resolve(), output_dir=out.resolve(), force=True
        )

    @patch("nest.cli.convert_cmd.create_convert_service")
    def test_convert_no_llm_disables_llm(
        self, mock_create_service: MagicMock, tmp_path: Path
    ) -> None:
        """--no-llm is forwarded to the composition root."""
        mock_service = MagicMock()
        mock_service.plan.return_value = _make_plan(tmp_path)
        mock_service.execute.return_value = _make_result()
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["convert", str(tmp_path), "--no-llm"])

        assert result.exit_code == 0
        mock_create_service.assert_called_once_with(no_llm=True, llm_config=None, llm_only=False)

    @patch("nest.cli.convert_cmd.resolve_llm_config")
    @patch("nest.cli.convert_cmd.create_convert_service")
    def test_convert_llm_only_is_forwarded(
        self, mock_create_service: MagicMock, mock_resolve: MagicMock, tmp_path: Path
    ) -> None:
        mock_service = MagicMock()
        mock_service.plan.return_value = _make_plan(tmp_path)
        mock_service.execute.return_value = _make_result()
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["convert", str(tmp_path), "--llm-only"])

        assert result.exit_code == 0
        mock_create_service.assert_called_once_with(
            no_llm=False, llm_config=mock_resolve.return_value, llm_only=True
        )

    @patch("nest.cli.convert_cmd.create_convert_service")
    def test_convert_llm_only_conflicts_with_no_llm(
        self, mock_create_service: MagicMock, tmp_path: Path
    ) -> None:
        result = runner.invoke(app, ["convert", str(tmp_path), "--llm-only", "--no-llm"])

        assert result.exit_code == 1
        assert "Convert failed" in result.output
        assert "--llm-only cannot be combined with --no-llm" in result.output
        mock_create_service.assert_not_called()

    @patch("nest.cli.convert_cmd.resolve_llm_config", return_value=None)
    def test_convert_llm_only_requires_llm(self, mock_resolve: MagicMock, tmp_path: Path) -> None:
        result = runner.invoke(app, ["convert", str(tmp_path), "--llm-only"])

        assert result.exit_code == 1
        mock_resolve.assert_called()
        assert "Convert failed" in result.output
        assert "--llm-only requires an LLM vision model" in result.output
        assert "nest config llm" in result.output


class TestDisplayConvertSummary:
    """Tests for the convert summary display."""

    def test_summary_groups_routine_skips_without_listing_paths(self) -> None:
        console, lines = self._make_console()
        result = _make_result(
            skipped_count=2,
            skips=[
                ConvertSkip(path=Path("/tmp/docs/report.pdf"), reason="Output already exists"),
                ConvertSkip(path=Path("/tmp/docs/notes.txt"), reason="Text file; left in place"),
            ],
        )

        _display_convert_summary(result, console)

        output = "\n".join(lines)
        assert "Outputs already present: 1" in output
        assert "Text files left in place: 1" in output
        assert "report.pdf" not in output
        assert "notes.txt" not in output

    def _make_console(self) -> tuple[Mock, list[str]]:
        output_lines: list[str] = []
        console = Mock(spec=Console)
        console.print.side_effect = lambda *args, **kwargs: output_lines.append(
            " ".join(str(a) for a in args)
        )
        return console, output_lines

    def test_summary_lists_failure_reasons(self) -> None:
        """Each failure is listed with its reason."""
        console, lines = self._make_console()
        result = _make_result(
            failed_count=1,
            failures=[
                ConvertFailure(path=Path("/tmp/docs/corrupt.pdf"), reason="Docling convert failed")
            ],
        )

        _display_convert_summary(result, console)

        full_output = "\n".join(lines)
        assert "Failed files:" in full_output
        assert "corrupt.pdf" in full_output
        assert "Docling convert failed" in full_output

    def test_summary_calls_out_images_that_need_llm(self) -> None:
        console, lines = self._make_console()
        result = _make_result(
            failed_count=1,
            failures=[
                ConvertFailure(
                    path=Path("/tmp/docs/flow.png"),
                    reason="requires LLM image description",
                    kind="needs_llm",
                )
            ],
        )

        _display_convert_summary(
            result,
            console,
            "not configured (run 'nest config llm' or set NEST_LLM_API_KEY)",
        )

        output = "\n".join(lines)
        assert "1 image file needs an LLM image description and was not processed" in output
        assert "flow.png" in output
        assert "Run 'nest config llm' or set NEST_LLM_API_KEY" in output
        assert "then run 'nest convert' again" in output

    def test_summary_tells_user_to_drop_no_llm_flag(self) -> None:
        console, lines = self._make_console()
        result = _make_result(
            failed_count=1,
            failures=[
                ConvertFailure(
                    path=Path("/tmp/docs/flow.png"),
                    reason="requires LLM image description",
                    kind="needs_llm",
                )
            ],
        )

        _display_convert_summary(result, console, "disabled (--no-llm)")

        assert "Run 'nest convert' again without --no-llm" in "\n".join(lines)

    def test_summary_lists_skip_reasons(self) -> None:
        """Each skipped file is listed with its reason."""
        console, lines = self._make_console()
        result = _make_result()

        _display_convert_summary(result, console, verbose=True)

        full_output = "\n".join(lines)
        assert "Skipped files:" in full_output
        assert "notes.txt" in full_output
        assert "left in place" in full_output

    def test_summary_hides_skip_list_when_empty(self) -> None:
        """No skip section when nothing was skipped."""
        console, lines = self._make_console()
        result = _make_result(skipped_count=0, skips=[])

        _display_convert_summary(result, console)

        full_output = "\n".join(lines)
        assert "Skipped files:" not in full_output

    def test_summary_shows_llm_disabled_note(self) -> None:
        """The LLM status note is shown when given."""
        console, lines = self._make_console()
        result = _make_result()

        _display_convert_summary(result, console, llm_status_note="disabled (--no-llm)")

        full_output = "\n".join(lines)
        assert "LLM:" in full_output
        assert "disabled (--no-llm)" in full_output

    def test_summary_shows_image_description_counts(self) -> None:
        """Image description counts and tokens are shown when non-zero."""
        console, lines = self._make_console()
        result = _make_result(
            images_described=2,
            images_skipped=1,
            vision_prompt_tokens=100,
            vision_completion_tokens=50,
        )

        _display_convert_summary(result, console)

        full_output = "\n".join(lines)
        assert "Images described: 2" in full_output
        assert "Images skipped:  1" in full_output
        assert "150" in full_output

    def test_summary_shows_transcribed_page_count(self) -> None:
        console, lines = self._make_console()
        result = _make_result(pages_transcribed=3)

        _display_convert_summary(result, console)

        assert "Pages transcribed by the LLM: 3" in "\n".join(lines)

    def test_summary_shows_paths_relative_to_root(self) -> None:
        """Skipped files are shown relative to the conversion root."""
        console, lines = self._make_console()
        result = _make_result(
            skips=[
                ConvertSkip(path=Path("/tmp/docs/sub/notes.txt"), reason="Text file; left in place")
            ]
        )

        _display_convert_summary(result, console, verbose=True)

        full_output = "\n".join(lines)
        assert "sub/notes.txt" in full_output

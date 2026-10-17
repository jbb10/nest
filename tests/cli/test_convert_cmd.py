"""Tests for the convert command CLI."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from rich.console import Console
from typer.testing import CliRunner

from nest.cli.convert_cmd import _display_convert_summary
from nest.cli.main import app
from nest.core.exceptions import NestError
from nest.core.models import ConvertFailure, ConvertResult, ConvertSkip, DiscoveredFile

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
        """Help should show --output, --force and --no-ai."""
        result = runner.invoke(app, ["convert", "--help"])

        assert result.exit_code == 0
        output = result.output
        assert "--output" in output
        assert "--force" in output
        assert "--no-ai" in output


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
    def test_convert_no_ai_disables_ai(
        self, mock_create_service: MagicMock, tmp_path: Path
    ) -> None:
        """--no-ai is forwarded to the composition root."""
        mock_service = MagicMock()
        mock_service.plan.return_value = _make_plan(tmp_path)
        mock_service.execute.return_value = _make_result()
        mock_create_service.return_value = mock_service

        result = runner.invoke(app, ["convert", str(tmp_path), "--no-ai"])

        assert result.exit_code == 0
        mock_create_service.assert_called_once_with(no_ai=True, ai_config=None)


class TestDisplayConvertSummary:
    """Tests for the convert summary display."""

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

    def test_summary_lists_skip_reasons(self) -> None:
        """Each skipped file is listed with its reason."""
        console, lines = self._make_console()
        result = _make_result()

        _display_convert_summary(result, console)

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

    def test_summary_shows_ai_disabled_note(self) -> None:
        """The AI status note is shown when given."""
        console, lines = self._make_console()
        result = _make_result()

        _display_convert_summary(result, console, ai_status_note="disabled (--no-ai)")

        full_output = "\n".join(lines)
        assert "AI:" in full_output
        assert "disabled (--no-ai)" in full_output

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

    def test_summary_shows_paths_relative_to_root(self) -> None:
        """Skipped files are shown relative to the conversion root."""
        console, lines = self._make_console()
        result = _make_result(
            skips=[
                ConvertSkip(path=Path("/tmp/docs/sub/notes.txt"), reason="Text file; left in place")
            ]
        )

        _display_convert_summary(result, console)

        full_output = "\n".join(lines)
        assert "sub/notes.txt" in full_output

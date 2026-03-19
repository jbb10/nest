"""Tests for sync command CLI."""

from pathlib import Path
from unittest.mock import Mock

import typer
from typer.testing import CliRunner

from nest.cli.main import app
from nest.cli.sync_cmd import _display_sync_summary, _validate_on_error
from nest.core.models import SyncResult
from nest.core.paths import AI_SEEN_MARKER, NEST_META_DIR

runner = CliRunner()


class TestValidateOnError:
    """Tests for --on-error validation."""

    def test_valid_skip_value(self) -> None:
        """'skip' should be accepted."""
        result = _validate_on_error("skip")
        assert result == "skip"

    def test_valid_fail_value(self) -> None:
        """'fail' should be accepted."""
        result = _validate_on_error("fail")
        assert result == "fail"

    def test_invalid_value_raises_bad_parameter(self) -> None:
        """Invalid values should raise BadParameter."""
        import pytest

        with pytest.raises(typer.BadParameter, match="Must be 'skip' or 'fail'"):
            _validate_on_error("invalid")


class TestSyncCommandHelp:
    """Tests for sync command help text."""

    def test_sync_help_displays_all_flags(self) -> None:
        """Help should show all flags."""
        result = runner.invoke(app, ["sync", "--help"])

        assert result.exit_code == 0
        assert "--on-error" in result.output
        assert "--dry-run" in result.output
        assert "--force" in result.output
        assert "--no-clean" in result.output
        assert "--no-ai" in result.output
        assert "--dir" in result.output


class TestSyncCommandFlags:
    """Tests for sync command flag parsing."""

    def test_default_on_error_is_skip(self) -> None:
        """Default --on-error should be 'skip'."""
        # This is tested implicitly - the CLI accepts no --on-error
        result = runner.invoke(app, ["sync", "--help"])
        assert "default: skip" in result.output

    def test_dry_run_flag_accepted(self) -> None:
        """--dry-run flag should be parsed."""
        # Note: Will fail because no project exists, but flag should be parsed
        result = runner.invoke(app, ["sync", "--dry-run"])
        # Check that it didn't fail due to flag parsing
        assert "--dry-run" not in result.output or "error" not in result.output.lower()

    def test_force_flag_accepted(self) -> None:
        """--force flag should be parsed."""
        result = runner.invoke(app, ["sync", "--force"])
        # Check that it didn't fail due to flag parsing
        assert "--force" not in result.output or "error" not in result.output.lower()


class TestSyncProjectValidation:
    """Tests for project validation (AC: #3)."""

    def test_sync_fails_when_no_manifest(self, tmp_path: Path) -> None:
        """Sync should fail with error when .nest/manifest.json doesn't exist."""
        # Create empty directory (no manifest)
        result = runner.invoke(app, ["sync", "--dir", str(tmp_path)])

        assert result.exit_code == 1
        assert "No Nest project found" in result.output

    def test_sync_error_message_shows_reason(self, tmp_path: Path) -> None:
        """Error should explain why (manifest not found)."""
        result = runner.invoke(app, ["sync", "--dir", str(tmp_path)])

        assert ".nest/manifest.json not found" in result.output

    def test_sync_error_message_shows_action(self, tmp_path: Path) -> None:
        """Error should suggest running nest init."""
        result = runner.invoke(app, ["sync", "--dir", str(tmp_path)])

        assert "nest init" in result.output


class TestDisplaySyncSummaryAggregatedTokens:
    """Tests for aggregated AI token display (Story 6.4)."""

    def _make_console(self) -> tuple["Mock", list[str]]:
        from rich.console import Console

        output_lines: list[str] = []
        console = Mock(spec=Console)
        console.print.side_effect = lambda *args, **kwargs: output_lines.append(
            " ".join(str(a) for a in args)
        )
        return console, output_lines

    def test_display_sync_summary_shows_aggregated_tokens(self) -> None:
        """Combined prompt+completion from both services shown in single line."""
        console, lines = self._make_console()
        result = SyncResult(
            ai_prompt_tokens=500,
            ai_completion_tokens=100,
            ai_glossary_prompt_tokens=300,
            ai_glossary_completion_tokens=50,
            ai_files_enriched=2,
            ai_glossary_terms_added=3,
        )

        _display_sync_summary(result, console, Path("/tmp/errors.log"))

        token_lines = [line for line in lines if "AI tokens:" in line]
        assert len(token_lines) == 1
        assert "950" in token_lines[0]
        assert "prompt: 800" in token_lines[0]
        assert "completion: 150" in token_lines[0]

    def test_display_sync_summary_hides_tokens_when_zero(self) -> None:
        """All tokens zero → no AI tokens line."""
        console, lines = self._make_console()
        result = SyncResult()

        _display_sync_summary(result, console, Path("/tmp/errors.log"))

        token_lines = [line for line in lines if "AI tokens:" in line]
        assert len(token_lines) == 0

    def test_display_sync_summary_shows_enrichment_count(self) -> None:
        """'AI enriched: X descriptions' shown when > 0."""
        console, lines = self._make_console()
        result = SyncResult(
            ai_files_enriched=4,
            ai_prompt_tokens=100,
            ai_completion_tokens=20,
        )

        _display_sync_summary(result, console, Path("/tmp/errors.log"))

        enriched_lines = [line for line in lines if "AI enriched:" in line]
        assert len(enriched_lines) == 1
        assert "4 descriptions" in enriched_lines[0]

    def test_display_sync_summary_shows_glossary_count(self) -> None:
        """'AI glossary: X terms defined' shown when > 0."""
        console, lines = self._make_console()
        result = SyncResult(
            ai_glossary_terms_added=5,
            ai_glossary_prompt_tokens=200,
            ai_glossary_completion_tokens=30,
        )

        _display_sync_summary(result, console, Path("/tmp/errors.log"))

        glossary_lines = [line for line in lines if "AI glossary:" in line]
        assert len(glossary_lines) == 1
        assert "5 terms defined" in glossary_lines[0]

    def test_display_sync_summary_shows_ai_not_configured_note(self) -> None:
        """Users should see why AI enrichment did not run."""
        console, lines = self._make_console()
        result = SyncResult()

        _display_sync_summary(
            result,
            console,
            Path("/tmp/errors.log"),
            ai_status_note="not configured (run 'nest config ai' or set NEST_AI_API_KEY / OPENAI_API_KEY)",
        )

        status_lines = [line for line in lines if "AI:" in line]
        assert len(status_lines) == 1
        assert "not configured" in status_lines[0]

    def test_display_sync_summary_shows_ai_disabled_note(self) -> None:
        """Users should see when AI was explicitly disabled."""
        console, lines = self._make_console()
        result = SyncResult()

        _display_sync_summary(
            result,
            console,
            Path("/tmp/errors.log"),
            ai_status_note="disabled (--no-ai)",
        )

        status_lines = [line for line in lines if "AI:" in line]
        assert len(status_lines) == 1
        assert "disabled (--no-ai)" in status_lines[0]


class TestDisplaySyncSummaryFirstRun:
    """Tests for first-run AI discovery message (Story 6.4)."""

    def _make_console(self) -> tuple["Mock", list[str]]:
        from rich.console import Console

        output_lines: list[str] = []
        console = Mock(spec=Console)
        console.print.side_effect = lambda *args, **kwargs: output_lines.append(
            " ".join(str(a) for a in args)
        )
        return console, output_lines

    def test_display_sync_summary_shows_first_run_message(self, tmp_path: Path) -> None:
        """No .ai_seen marker → discovery message shown."""
        meta_dir = tmp_path / NEST_META_DIR
        meta_dir.mkdir()

        console, lines = self._make_console()
        result = SyncResult(
            ai_files_enriched=2,
            ai_prompt_tokens=100,
            ai_completion_tokens=20,
        )

        _display_sync_summary(
            result,
            console,
            Path("/tmp/errors.log"),
            ai_detected_key="OPENAI_API_KEY",
            project_root=tmp_path,
        )

        full_output = "\n".join(lines)
        assert "AI enrichment enabled" in full_output
        assert "OPENAI_API_KEY" in full_output

    def test_display_sync_summary_creates_marker_file(self, tmp_path: Path) -> None:
        """.ai_seen file created after first AI use."""
        meta_dir = tmp_path / NEST_META_DIR
        meta_dir.mkdir()

        console, _ = self._make_console()
        result = SyncResult(
            ai_files_enriched=1,
            ai_prompt_tokens=50,
            ai_completion_tokens=10,
        )

        _display_sync_summary(
            result,
            console,
            Path("/tmp/errors.log"),
            ai_detected_key="OPENAI_API_KEY",
            project_root=tmp_path,
        )

        marker = meta_dir / AI_SEEN_MARKER
        assert marker.exists()

    def test_display_sync_summary_suppresses_message_on_subsequent_runs(
        self, tmp_path: Path
    ) -> None:
        """.ai_seen exists → no discovery message."""
        meta_dir = tmp_path / NEST_META_DIR
        meta_dir.mkdir()
        (meta_dir / AI_SEEN_MARKER).touch()

        console, lines = self._make_console()
        result = SyncResult(
            ai_files_enriched=2,
            ai_prompt_tokens=100,
            ai_completion_tokens=20,
        )

        _display_sync_summary(
            result,
            console,
            Path("/tmp/errors.log"),
            ai_detected_key="OPENAI_API_KEY",
            project_root=tmp_path,
        )

        full_output = "\n".join(lines)
        assert "AI enrichment enabled" not in full_output

    def test_display_sync_summary_no_message_when_no_ai_used(self, tmp_path: Path) -> None:
        """AI not active → no discovery message even without marker."""
        meta_dir = tmp_path / NEST_META_DIR
        meta_dir.mkdir()

        console, lines = self._make_console()
        result = SyncResult()  # Zero AI activity

        _display_sync_summary(
            result,
            console,
            Path("/tmp/errors.log"),
            ai_detected_key="OPENAI_API_KEY",
            project_root=tmp_path,
        )

        full_output = "\n".join(lines)
        assert "AI enrichment enabled" not in full_output
        # Marker should NOT be created
        assert not (meta_dir / AI_SEEN_MARKER).exists()


class TestDisplaySyncSummaryVisionStats:
    """Tests for vision image description display in _display_sync_summary() (Story 7.4)."""

    def _make_console(self) -> tuple["Mock", list[str]]:
        from rich.console import Console

        output_lines: list[str] = []
        console = Mock(spec=Console)
        console.print.side_effect = lambda *args, **kwargs: output_lines.append(
            " ".join(str(a) for a in args)
        )
        return console, output_lines

    def test_images_described_with_mermaid(self) -> None:
        """images_described=3, images_mermaid=1 → 'Images described: 3 (1 as Mermaid diagrams)'."""
        console, lines = self._make_console()
        result = SyncResult(images_described=3, images_mermaid=1, vision_prompt_tokens=100)

        _display_sync_summary(result, console, Path("/tmp/errors.log"))

        image_lines = [line for line in lines if "Images described:" in line]
        assert len(image_lines) == 1
        assert "3" in image_lines[0]
        assert "1 as Mermaid diagrams" in image_lines[0]

    def test_images_described_no_mermaid(self) -> None:
        """images_described=2, images_mermaid=0 → 'Images described: 2' (no Mermaid note)."""
        console, lines = self._make_console()
        result = SyncResult(images_described=2, images_mermaid=0, vision_prompt_tokens=80)

        _display_sync_summary(result, console, Path("/tmp/errors.log"))

        image_lines = [line for line in lines if "Images described:" in line]
        assert len(image_lines) == 1
        assert "2" in image_lines[0]
        assert "Mermaid" not in image_lines[0]

    def test_no_images_no_image_line(self) -> None:
        """images_described=0 → no 'Images described' line."""
        console, lines = self._make_console()
        result = SyncResult(images_described=0, images_skipped=0)

        _display_sync_summary(result, console, Path("/tmp/errors.log"))

        image_lines = [line for line in lines if "Images described:" in line]
        assert len(image_lines) == 0

    def test_images_skipped_shown(self) -> None:
        """images_skipped=4 → 'Images skipped:  4 (logos/signatures)'."""
        console, lines = self._make_console()
        result = SyncResult(images_skipped=4)

        _display_sync_summary(result, console, Path("/tmp/errors.log"))

        skipped_lines = [line for line in lines if "Images skipped:" in line]
        assert len(skipped_lines) == 1
        assert "4" in skipped_lines[0]
        assert "logos/signatures" in skipped_lines[0]

    def test_images_skipped_zero_not_shown(self) -> None:
        """images_skipped=0 → no skipped line."""
        console, lines = self._make_console()
        result = SyncResult(images_skipped=0)

        _display_sync_summary(result, console, Path("/tmp/errors.log"))

        skipped_lines = [line for line in lines if "Images skipped:" in line]
        assert len(skipped_lines) == 0

    def test_vision_tokens_included_in_total(self) -> None:
        """Vision tokens aggregated into the 'AI tokens:' line with text enrichment tokens."""
        console, lines = self._make_console()
        result = SyncResult(
            ai_prompt_tokens=200,
            ai_completion_tokens=50,
            ai_glossary_prompt_tokens=100,
            ai_glossary_completion_tokens=25,
            vision_prompt_tokens=100,
            vision_completion_tokens=50,
        )

        _display_sync_summary(result, console, Path("/tmp/errors.log"))

        token_lines = [line for line in lines if "AI tokens:" in line]
        assert len(token_lines) == 1
        # Total = (200+100+100) prompt + (50+25+50) completion = 400 + 125 = 525
        assert "525" in token_lines[0]
        assert "prompt: 400" in token_lines[0]
        assert "completion: 125" in token_lines[0]

    def test_vision_tokens_only_no_text_enrichment(self) -> None:
        """Vision-only tokens still show the 'AI tokens:' line."""
        console, lines = self._make_console()
        result = SyncResult(
            vision_prompt_tokens=100,
            vision_completion_tokens=50,
            images_described=5,
        )

        _display_sync_summary(result, console, Path("/tmp/errors.log"))

        token_lines = [line for line in lines if "AI tokens:" in line]
        assert len(token_lines) == 1
        assert "150" in token_lines[0]

    def test_vision_triggers_ai_was_used_for_first_run_message(self, tmp_path: Path) -> None:
        """images_described > 0 triggers first-run AI discovery message."""
        meta_dir = tmp_path / NEST_META_DIR
        meta_dir.mkdir()

        console, lines = self._make_console()
        result = SyncResult(images_described=3, vision_prompt_tokens=100)

        _display_sync_summary(
            result,
            console,
            Path("/tmp/errors.log"),
            ai_detected_key="OPENAI_API_KEY",
            project_root=tmp_path,
        )

        full_output = "\n".join(lines)
        assert "AI enrichment enabled" in full_output

    def test_create_sync_service_no_ai_disables_vision(self, tmp_path: Path) -> None:
        """create_sync_service with no_ai=True creates no vision provider or PDS."""
        from nest.cli.sync_cmd import create_sync_service

        project_root = tmp_path
        (project_root / ".nest").mkdir()

        service = create_sync_service(project_root, no_ai=True)

        assert service._picture_description_service is None
        assert service._vision_docling_processor is None

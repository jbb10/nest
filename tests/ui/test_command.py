"""Whole-app output policy tested through command registration and the public session interface."""

import logging
import subprocess
import sys
import threading
from io import StringIO
from pathlib import Path

import click
import pytest
from rich.console import Console
from typer.main import get_command
from typer.testing import CliRunner

from nest.cli.main import app
from nest.ui.command import CommandUI, NestCommand, current_output


def test_lightweight_command_does_not_import_ml_libraries(tmp_path: Path) -> None:
    script = (
        "import sys\n"
        "from nest.cli.main import app\n"
        "from typer.testing import CliRunner\n"
        "result = CliRunner().invoke(app, ['status', '--dir', sys.argv[1]])\n"
        "assert result.exit_code == 1, result.output\n"
        "assert 'torch' not in sys.modules\n"
        "assert 'transformers' not in sys.modules\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_registered_command_owns_an_output_session() -> None:
    def check(command: click.Command) -> None:
        if isinstance(command, click.Group):
            for child in command.commands.values():
                check(child)
        else:
            assert isinstance(command, NestCommand), command.name
            assert any(parameter.name == "verbose" for parameter in command.params)

    check(get_command(app))


@pytest.mark.parametrize(
    "arguments",
    [
        ["init"],
        ["sync"],
        ["convert"],
        ["status"],
        ["doctor"],
        ["update"],
        ["config", "ai"],
    ],
)
def test_verbose_is_available_on_every_command(arguments: list[str]) -> None:
    result = CliRunner().invoke(app, [*arguments, "--help"])
    assert result.exit_code == 0, result.output
    assert "--verbose" in result.output


def test_completed_documents_do_not_mean_the_whole_command_is_complete() -> None:
    stream = StringIO()
    with CommandUI("sync", Console(file=stream, width=120)) as output:
        output.start(1)
        output.advance("document.pdf")
        output.stage("Generating document descriptions and glossary")
        output.finish()
    assert "100%" not in stream.getvalue()
    assert "Generating document descriptions and glossary" in stream.getvalue()
    assert "\x1b" not in stream.getvalue()


def test_session_restores_after_abort() -> None:
    with pytest.raises(KeyboardInterrupt):
        with CommandUI("sync", Console(file=StringIO())):
            raise KeyboardInterrupt
    with pytest.raises(RuntimeError, match="No active"):
        current_output()


def test_warning_is_summarized_once_without_raw_duplicate(tmp_path: Path) -> None:
    stream = StringIO()
    with CommandUI("sync", Console(file=stream, width=160)) as output:
        output.root = tmp_path
        for _ in range(3):
            logging.getLogger("nest.services.picture_description_service").warning(
                "Image description failed",
                extra={"source_path": str(tmp_path / "deck.pptx")},
            )
    rendered = stream.getvalue()
    assert rendered.count("Image description failed") == 1
    assert "WARNING:" not in rendered
    assert "deck.pptx" in rendered


def test_spinner_animates_while_the_command_waits() -> None:
    class FrameStream(StringIO):
        def __init__(self) -> None:
            super().__init__()
            self.frames: set[str] = set()
            self.animated = threading.Event()

        def write(self, text: str) -> int:
            self.frames.update(
                character for character in text if 0x2800 <= ord(character) <= 0x28FF
            )
            if len(self.frames) > 1:
                self.animated.set()
            return super().write(text)

    stream = FrameStream()
    with CommandUI("sync", Console(file=stream, force_terminal=True, width=80)) as output:
        output.stage("Waiting for image descriptions")
        assert stream.animated.wait(timeout=3), (
            "The live spinner did not advance during blocking work"
        )

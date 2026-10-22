"""Tests for AITranscriptionService: AI transcription of image files and PDF pages."""

from __future__ import annotations

import base64
import io
import threading
from pathlib import Path

import pytest
from PIL import Image

from nest.core.exceptions import ProcessingError
from nest.core.models import LLMCompletionResult
from nest.services.ai_transcription_service import (
    TRANSCRIPTION_PROMPT,
    UNREADABLE_PAGE,
    AITranscriptionService,
)


class PageEchoProvider:
    """Vision provider that answers with the width of each image it receives.

    Pages are drawn with distinct widths, so the answer identifies the page.
    """

    def __init__(self, fail_widths: set[int] | None = None, wrap: str | None = None) -> None:
        self.fail_widths = fail_widths or set()
        self.wrap = wrap
        self.calls: list[tuple[str, bytes, str]] = []
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return "mock-vision-model"

    def complete_with_image(
        self,
        prompt: str,
        image_base64: str,
        mime_type: str = "image/png",
    ) -> LLMCompletionResult | None:
        data = base64.b64decode(image_base64)
        with self._lock:
            self.calls.append((prompt, data, mime_type))
        width = Image.open(io.BytesIO(data)).width
        if width in self.fail_widths:
            return None
        text = f"page width {width}"
        if self.wrap is not None:
            text = self.wrap.format(text)
        return LLMCompletionResult(text=text, prompt_tokens=100, completion_tokens=10)


def save_image(path: Path, width: int, fmt: str) -> Path:
    Image.new("RGB", (width, 50), "white").save(path, fmt)
    return path


def save_pdf(path: Path, widths: list[int]) -> Path:
    pages = [Image.new("RGB", (width, 50), "white") for width in widths]
    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=72)
    return path


class TestHandles:
    @pytest.mark.parametrize("name", ["scan.png", "photo.JPG", "fax.tiff", "report.pdf"])
    def test_images_and_pdfs_are_transcribed(self, name: str) -> None:
        assert AITranscriptionService(PageEchoProvider()).handles(Path(name))

    @pytest.mark.parametrize("name", ["deck.pptx", "memo.docx", "sheet.xlsx", "notes.md"])
    def test_other_formats_are_not_transcribed(self, name: str) -> None:
        assert not AITranscriptionService(PageEchoProvider()).handles(Path(name))


class TestTranscribeImages:
    def test_native_image_is_sent_unchanged_with_the_transcription_prompt(
        self, tmp_path: Path
    ) -> None:
        provider = PageEchoProvider()
        source = save_image(tmp_path / "scan.jpg", 300, "JPEG")

        result = AITranscriptionService(provider).transcribe(source)

        assert provider.calls == [(TRANSCRIPTION_PROMPT, source.read_bytes(), "image/jpeg")]
        assert result.markdown == "page width 300\n"
        assert (result.pages, result.prompt_tokens, result.completion_tokens) == (1, 100, 10)

    def test_image_formats_the_model_cannot_read_are_sent_as_png(self, tmp_path: Path) -> None:
        provider = PageEchoProvider()
        source = save_image(tmp_path / "scan.bmp", 320, "BMP")

        result = AITranscriptionService(provider).transcribe(source)

        [(_, data, mime_type)] = provider.calls
        assert mime_type == "image/png"
        assert Image.open(io.BytesIO(data)).format == "PNG"
        assert result.markdown == "page width 320\n"

    def test_every_frame_of_a_multipage_tiff_is_a_page(self, tmp_path: Path) -> None:
        provider = PageEchoProvider()
        frames = [Image.new("RGB", (width, 50), "white") for width in (200, 210)]
        source = tmp_path / "fax.tiff"
        frames[0].save(source, "TIFF", save_all=True, append_images=frames[1:])

        result = AITranscriptionService(provider).transcribe(source)

        assert result.markdown == "page width 200\n\npage width 210\n"
        assert result.pages == 2

    def test_code_fence_around_the_whole_answer_is_removed(self, tmp_path: Path) -> None:
        provider = PageEchoProvider(wrap="```markdown\n{}\n```")
        source = save_image(tmp_path / "scan.png", 300, "PNG")

        result = AITranscriptionService(provider).transcribe(source)

        assert result.markdown == "page width 300\n"


class TestTranscribePdfs:
    def test_pages_are_transcribed_and_joined_in_page_order(self, tmp_path: Path) -> None:
        provider = PageEchoProvider()
        source = save_pdf(tmp_path / "report.pdf", [100, 150, 200])

        result = AITranscriptionService(provider).transcribe(source)

        widths = [int(line.split()[-1]) for line in result.markdown.split("\n\n")]
        assert widths == sorted(widths)
        assert len(widths) == 3
        assert {mime for _, _, mime in provider.calls} == {"image/png"}
        assert (result.pages, result.prompt_tokens, result.completion_tokens) == (3, 300, 30)

    def test_pages_are_rendered_above_screen_resolution(self, tmp_path: Path) -> None:
        provider = PageEchoProvider()
        source = save_pdf(tmp_path / "report.pdf", [100])

        AITranscriptionService(provider).transcribe(source)

        [(_, data, _)] = provider.calls
        assert Image.open(io.BytesIO(data)).width >= 200

    def test_a_failed_page_fails_the_document(self, tmp_path: Path) -> None:
        source = save_pdf(tmp_path / "report.pdf", [100, 150])
        probe = PageEchoProvider()
        AITranscriptionService(probe).transcribe(source)
        second_page_width = max(Image.open(io.BytesIO(data)).width for _, data, _ in probe.calls)
        provider = PageEchoProvider(fail_widths={second_page_width})

        with pytest.raises(ProcessingError, match="AI transcription failed for 1 of 2 pages"):
            AITranscriptionService(provider).transcribe(source)

    def test_a_page_the_model_cannot_read_fails_the_document(self, tmp_path: Path) -> None:
        provider = PageEchoProvider(wrap=f"  {UNREADABLE_PAGE}\n")
        source = save_image(tmp_path / "scan.png", 300, "PNG")

        with pytest.raises(ProcessingError, match="AI vision model could not read the page"):
            AITranscriptionService(provider).transcribe(source)

    def test_prompt_asks_for_the_unreadable_marker_instead_of_a_refusal(self) -> None:
        assert UNREADABLE_PAGE in TRANSCRIPTION_PROMPT

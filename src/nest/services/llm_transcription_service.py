"""LLM transcription of image files and PDFs.

Sends each page of a source document to the vision model as an image and
takes the model's Markdown as the prepared document. Docling layout analysis,
OCR, and table structure recognition are not involved. See ADR 0004.
"""

from __future__ import annotations

import base64
import io
import logging
import re
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from nest.core.exceptions import ProcessingError
from nest.core.models import LLMCompletionResult, TranscriptionResult
from nest.core.paths import is_image_extension

if TYPE_CHECKING:
    from PIL.Image import Image

    from nest.adapters.protocols import VisionLLMProviderProtocol

logger = logging.getLogger(__name__)

TRANSCRIPTION_PROMPT = (
    (Path(__file__).parent / "prompts" / "transcription_prompt.md")
    .read_text(encoding="utf-8")
    .rstrip("\n")
)
# The prompt asks for this marker instead of a refusal when a page is unreadable.
UNREADABLE_PAGE = "NEST_UNREADABLE_PAGE"

# Formats vision models accept as-is; other image formats are re-encoded as PNG.
_NATIVE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_PDF_RENDER_SCALE = 2.0
MAX_CONCURRENT_PAGES = 8

_WHOLE_ANSWER_FENCE = re.compile(r"\A```(?:markdown|md)?\n(.*)\n```\Z", re.DOTALL)


class _PageImage(NamedTuple):
    data: bytes
    mime_type: str


class LLMTranscriptionService:
    """Transcribes images and PDFs to Markdown with a vision model, page by page."""

    def __init__(self, vision_provider: VisionLLMProviderProtocol) -> None:
        self._vision_provider = vision_provider

    def handles(self, source: Path) -> bool:
        """Whether ``source`` is an image file or a PDF."""
        return source.suffix.lower() == ".pdf" or is_image_extension(source.suffix)

    def transcribe(self, source: Path) -> TranscriptionResult:
        """Transcribe every page of ``source``.

        Raises:
            ProcessingError: If the vision model fails on any page.
        """
        pages = list(_pages(source))
        if not pages:
            raise ProcessingError("Document has no pages", source_path=source)
        with ThreadPoolExecutor(max_workers=min(len(pages), MAX_CONCURRENT_PAGES)) as executor:
            answers = list(executor.map(self._transcribe_page, pages))

        failed = sum(answer is None for answer in answers)
        if failed:
            scope = f" for {failed} of {len(pages)} pages" if len(pages) > 1 else ""
            raise ProcessingError(f"LLM transcription failed{scope}", source_path=source)
        completed = [answer for answer in answers if answer is not None]
        unreadable = sum(UNREADABLE_PAGE in answer.text for answer in completed)
        if unreadable:
            scope = f"{unreadable} of {len(pages)} pages" if len(pages) > 1 else "the page"
            raise ProcessingError(
                f"LLM vision model could not read {scope}; "
                "a stronger model may help (NEST_LLM_VISION_MODEL)",
                source_path=source,
            )
        texts = [_unwrap(answer.text) for answer in completed]
        return TranscriptionResult(
            markdown="\n\n".join(text for text in texts if text) + "\n",
            pages=len(pages),
            prompt_tokens=sum(answer.prompt_tokens for answer in completed),
            completion_tokens=sum(answer.completion_tokens for answer in completed),
        )

    def _transcribe_page(self, page: _PageImage) -> LLMCompletionResult | None:
        return self._vision_provider.complete_with_image(
            TRANSCRIPTION_PROMPT, base64.b64encode(page.data).decode("ascii"), page.mime_type
        )


def _pages(source: Path) -> Iterator[_PageImage]:
    """Yield each page of ``source`` as an encoded image."""
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        import pypdfium2  # pyright: ignore[reportMissingTypeStubs]

        # pypdfium2 ships without type information.
        pdf: Any = pypdfium2.PdfDocument(source)
        try:
            for page in pdf:
                yield _PageImage(_png(page.render(scale=_PDF_RENDER_SCALE).to_pil()), "image/png")
        finally:
            pdf.close()
        return

    if suffix in _NATIVE_MIME_TYPES:
        yield _PageImage(source.read_bytes(), _NATIVE_MIME_TYPES[suffix])
        return

    from PIL import Image, ImageSequence

    with Image.open(source) as image:
        for frame in ImageSequence.Iterator(image):
            yield _PageImage(_png(frame), "image/png")


def _png(image: Image) -> bytes:
    if image.mode not in ("RGB", "RGBA", "L", "LA"):
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _unwrap(text: str) -> str:
    """Strip whitespace and a code fence wrapped around the whole answer."""
    text = text.strip()
    match = _WHOLE_ANSWER_FENCE.match(text)
    return match.group(1).strip() if match else text

"""Tests for the convert service.

Covers project-free document conversion: planning (validation, discovery,
skip-existing classification) and execution (in-place conversion, output
mirroring, passthrough handling, per-file failure recording).
"""

from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock

import pytest

from nest.adapters.file_discovery import FileDiscoveryAdapter
from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.passthrough_processor import PassthroughProcessor
from nest.core.checksum import compute_sha256
from nest.core.exceptions import NestError, ProcessingError
from nest.core.models import (
    Activity,
    PictureDescriptionResult,
    ProcessingResult,
    TranscriptionResult,
)
from nest.services.convert_service import ConvertService
from nest.services.output_service import OutputMirrorService


class StubProcessor:
    """Document processor that writes a marker line to each output path."""

    def __init__(self, fail_names: set[str] | None = None) -> None:
        self.fail_names = fail_names or set()
        self.processed: list[Path] = []

    def process(self, source: Path, output: Path) -> ProcessingResult:
        if source.name in self.fail_names:
            return ProcessingResult(
                source_path=source,
                status="failed",
                error=f"stub failure for {source.name}",
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"converted: {source.name}\n", encoding="utf-8", newline="\n")
        self.processed.append(source)
        return ProcessingResult(source_path=source, status="success", output_path=output)


class StubDownloader:
    """Model cache that records download calls without downloading."""

    def __init__(self) -> None:
        self.download_calls = 0

    def are_models_cached(self) -> bool:
        return True

    def download_if_needed(self, progress: bool = True) -> bool:
        self.download_calls += 1
        return False

    def get_cache_path(self) -> Path:
        return Path("/tmp/docling-models")

    def get_cache_size(self) -> int:
        return 0

    def get_cache_status(self) -> Literal["exists", "empty", "not_created"]:
        return "exists"


def make_service(
    fail_names: set[str] | None = None,
) -> tuple[ConvertService, StubProcessor, StubDownloader]:
    """Wire a ConvertService with real discovery/passthrough and stub conversion."""
    processor = StubProcessor(fail_names)
    downloader = StubDownloader()
    service = ConvertService(
        output=OutputMirrorService(
            filesystem=FileSystemAdapter(),
            processor=processor,
            passthrough_processor=PassthroughProcessor(),
        ),
        file_discovery=FileDiscoveryAdapter(),
        model_downloader=downloader,
    )
    return service, processor, downloader


def write(path: Path, content: str = "content") -> Path:
    """Create a file (and parents) with the given content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return path


class TestConvertPlanValidation:
    """Tests for target validation in plan()."""

    def test_plan_raises_for_missing_path(self, tmp_path: Path) -> None:
        """A path that does not exist raises NestError naming the path."""
        service, _, _ = make_service()

        with pytest.raises(NestError, match="not found"):
            service.plan(tmp_path / "missing")

    def test_plan_raises_for_unsupported_single_file(self, tmp_path: Path) -> None:
        """A single file of an unsupported type raises NestError naming the type."""
        service, _, _ = make_service()
        write(tmp_path / "archive.zip")

        with pytest.raises(NestError, match="[Uu]nsupported file type"):
            service.plan(tmp_path / "archive.zip")

    def test_plan_accepts_single_supported_file(self, tmp_path: Path) -> None:
        """A single supported file is planned with its parent as root."""
        service, _, _ = make_service()
        pdf = write(tmp_path / "docs" / "q1.pdf")

        plan = service.plan(pdf)

        assert plan.root == pdf.parent
        assert [f.path for f in plan.pending] == [pdf]
        assert plan.skipped == []

    def test_plan_accepts_explicitly_passed_hidden_file(self, tmp_path: Path) -> None:
        """An explicitly passed hidden file converts; hidden rules apply to directories."""
        service, _, _ = make_service()
        pdf = write(tmp_path / ".secret.pdf")

        plan = service.plan(pdf)

        assert [f.path for f in plan.pending] == [pdf]


class TestConvertPlanDiscovery:
    """Tests for directory discovery in plan()."""

    def test_plan_discovers_nested_supported_files(self, tmp_path: Path) -> None:
        """A directory is processed recursively for all supported extensions."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        write(docs / "reports" / "q1.pdf")
        write(docs / "reports" / "summary.docx")
        write(docs / "decks" / "intro.pptx")

        plan = service.plan(docs)

        names = {f.path.name for f in plan.pending}
        assert names == {"q1.pdf", "summary.docx", "intro.pptx"}
        assert all(f.path.is_absolute() for f in plan.pending)

    def test_plan_skips_hidden_directories_like_sync(self, tmp_path: Path) -> None:
        """Hidden directories are skipped with the same rules as sync."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        write(docs / "visible.pdf")
        write(docs / ".hidden" / "secret.pdf")

        plan = service.plan(docs)

        assert [f.path.name for f in plan.pending] == ["visible.pdf"]

    def test_plan_skips_unsupported_files_in_directory(self, tmp_path: Path) -> None:
        """Files with unsupported extensions are ignored during directory discovery."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        write(docs / "good.pdf")
        write(docs / "archive.zip")

        plan = service.plan(docs)

        assert [f.path.name for f in plan.pending] == ["good.pdf"]

    def test_plan_includes_standalone_image_files(self, tmp_path: Path) -> None:
        """Image files are source documents and are planned for conversion."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        write(docs / "diagram.png")

        plan = service.plan(docs)

        assert [f.path.name for f in plan.pending] == ["diagram.png"]

    def test_plan_computes_checksums_for_pending_files(self, tmp_path: Path) -> None:
        """Each planned file carries its SHA-256 checksum."""
        service, _, _ = make_service()
        pdf = write(tmp_path / "q1.pdf", "binary-ish content")

        plan = service.plan(pdf)

        assert plan.pending[0].checksum == compute_sha256(pdf)


class TestConvertPlanSkipClassification:
    """Tests for skip classification in plan()."""

    def test_plan_skips_passthrough_files_without_output(self, tmp_path: Path) -> None:
        """Without --output, passthrough text files are left in place and skipped."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        write(docs / "notes.txt")
        write(docs / "report.pdf")

        plan = service.plan(docs)

        assert [f.path.name for f in plan.pending] == ["report.pdf"]
        assert [f.path.name for f in plan.skipped] == ["notes.txt"]
        assert "left in place" in (plan.skipped[0].collision_reason or "")

    def test_plan_keeps_passthrough_files_with_output(self, tmp_path: Path) -> None:
        """With --output, passthrough text files are pending for copying."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        write(docs / "notes.txt")

        plan = service.plan(docs, output_dir=tmp_path / "out")

        assert [f.path.name for f in plan.pending] == ["notes.txt"]

    def test_plan_skips_existing_output(self, tmp_path: Path) -> None:
        """A file whose target Markdown already exists is skipped with a reason."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        write(docs / "q1.pdf")
        write(docs / "q1.md", "already converted")

        plan = service.plan(docs)

        assert plan.pending == []
        reasons = {f.path.name: f.collision_reason or "" for f in plan.skipped}
        assert "already exists" in reasons["q1.pdf"]
        # q1.md is itself a passthrough source, left in place without --output
        assert "left in place" in reasons["q1.md"]

    def test_plan_force_overrides_existing_output(self, tmp_path: Path) -> None:
        """--force re-plans files whose target Markdown already exists."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        write(docs / "q1.pdf")
        write(docs / "q1.md", "already converted")

        plan = service.plan(docs, force=True)

        assert [f.path.name for f in plan.pending] == ["q1.pdf"]

    def test_plan_checks_existing_output_in_output_dir(self, tmp_path: Path) -> None:
        """With --output, existence is checked in the output tree, not next to the source."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        out = tmp_path / "out"
        write(docs / "q1.pdf")
        write(docs / "q1.md", "in-place markdown must not block --output")
        write(out / "q1.md", "already converted")

        plan = service.plan(docs, output_dir=out)

        assert plan.pending == []
        reasons = {f.path.name: f.collision_reason or "" for f in plan.skipped}
        # Both the passthrough copy and the Docling conversion target out/q1.md
        assert "already exists" in reasons["q1.md"]
        assert "already exists" in reasons["q1.pdf"]


def fake_conversion(markdown: str, *, pictures: list[str | None]) -> MagicMock:
    """Build a conversion result holding pictures with the given top labels."""
    from docling_core.types.doc.items.picture.picture import PictureItem

    items: list[MagicMock] = []
    for label in pictures:
        item = MagicMock()
        item.__class__ = PictureItem
        if label is None:
            item.meta.classification = None
        else:
            prediction = MagicMock()
            prediction.class_name = label
            prediction.confidence = 0.9
            item.meta.classification.predictions = [prediction]
        items.append(item)
    conversion = MagicMock()
    conversion.document.iterate_items.return_value = [(item, 1) for item in items]
    conversion.document.export_to_markdown.return_value = markdown
    return conversion


class TestStandaloneImagesWithoutVision:
    """Image files need AI only when they hold a picture the vision pass would describe."""

    def make_service(self, conversions: dict[str, MagicMock]) -> ConvertService:
        image_processor = MagicMock()
        image_processor.convert.side_effect = lambda source: conversions[source.name]
        return ConvertService(
            output=OutputMirrorService(FileSystemAdapter(), StubProcessor()),
            file_discovery=FileDiscoveryAdapter(),
            image_processor=image_processor,
        )

    def test_image_with_describable_picture_fails_and_writes_nothing(self, tmp_path: Path) -> None:
        source = write(tmp_path / "flow.png")
        service = self.make_service(
            {"flow.png": fake_conversion("<!-- image -->", pictures=["flow_chart"])}
        )

        result = service.execute(service.plan(source))

        assert result.failed_count == 1
        assert result.processed_count == 0
        assert not (tmp_path / "flow.md").exists()
        assert result.failures[0].path == source
        assert result.failures[0].kind == "needs_ai"
        assert result.failures[0].reason == "requires AI image description"

    def test_image_without_describable_picture_is_written(self, tmp_path: Path) -> None:
        write(tmp_path / "notes.png")
        service = self.make_service(
            {"notes.png": fake_conversion("## Meeting notes", pictures=["logo"])}
        )

        result = service.execute(service.plan(tmp_path))

        assert result.failed_count == 0
        assert result.processed_count == 1
        assert (tmp_path / "notes.md").read_text() == "## Meeting notes"

    def test_documents_keep_placeholder_behaviour_without_vision(self, tmp_path: Path) -> None:
        """Embedded images in a PDF do not make the document fail (ADR 0002)."""
        write(tmp_path / "report.pdf")
        service = self.make_service({})

        result = service.execute(service.plan(tmp_path))

        assert result.failed_count == 0
        assert (tmp_path / "report.md").read_text() == "converted: report.pdf\n"


class StubTranscription:
    """Transcription service that handles images and PDFs, failing named files."""

    def __init__(self, fail_names: set[str] | None = None) -> None:
        self.fail_names = fail_names or set()
        self.transcribed: list[Path] = []

    def handles(self, source: Path) -> bool:
        return source.suffix in {".png", ".pdf"}

    def transcribe(self, source: Path) -> TranscriptionResult:
        if source.name in self.fail_names:
            raise ProcessingError("AI transcription failed", source_path=source)
        self.transcribed.append(source)
        return TranscriptionResult(
            markdown=f"transcribed: {source.name}\n",
            pages=2,
            prompt_tokens=100,
            completion_tokens=10,
        )


class TestAIOnlyTranscription:
    """With a transcriber, image files and PDFs skip Docling for AI transcription."""

    def make_service(
        self, transcription: StubTranscription
    ) -> tuple[ConvertService, StubProcessor, StubDownloader, MagicMock]:
        processor = StubProcessor()
        downloader = StubDownloader()
        image_processor = MagicMock()
        service = ConvertService(
            output=OutputMirrorService(FileSystemAdapter(), processor),
            file_discovery=FileDiscoveryAdapter(),
            model_downloader=downloader,
            image_processor=image_processor,
            transcriber=transcription,
        )
        return service, processor, downloader, image_processor

    def test_images_and_pdfs_are_transcribed_and_other_formats_use_docling(
        self, tmp_path: Path
    ) -> None:
        transcription = StubTranscription()
        service, processor, _, image_processor = self.make_service(transcription)
        write(tmp_path / "scan.png")
        write(tmp_path / "report.pdf")
        write(tmp_path / "memo.docx")
        activities: list[Activity] = []

        result = service.execute(service.plan(tmp_path), activity_callback=activities.append)

        assert (tmp_path / "scan.md").read_text() == "transcribed: scan.png\n"
        assert (tmp_path / "report.md").read_text() == "transcribed: report.pdf\n"
        assert (tmp_path / "memo.md").read_text() == "converted: memo.docx\n"
        assert processor.processed == [tmp_path / "memo.docx"]
        image_processor.convert.assert_not_called()
        assert result.processed_count == 3
        assert result.pages_transcribed == 4
        assert (result.vision_prompt_tokens, result.vision_completion_tokens) == (200, 20)
        assert {a.files[0].name for a in activities if a.stage == "transcribing"} == {
            "scan.png",
            "report.pdf",
        }

    def test_failed_transcription_is_a_failed_document_and_writes_nothing(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        service, _, _, _ = self.make_service(StubTranscription(fail_names={"scan.png"}))
        write(tmp_path / "scan.png")
        write(tmp_path / "report.pdf")

        result = service.execute(service.plan(tmp_path))

        assert not (tmp_path / "scan.md").exists()
        assert result.processed_count == 1
        assert [f.path.name for f in result.failures] == ["scan.png"]
        assert result.failures[0].reason == "AI transcription failed"
        assert "Unexpected error" not in caplog.text

    def test_failed_transcription_preserves_existing_output(self, tmp_path: Path) -> None:
        service, _, _, _ = self.make_service(StubTranscription(fail_names={"scan.png"}))
        source = write(tmp_path / "scan.png")
        output = write(tmp_path / "scan.md", "previous successful output")

        result = service.execute(service.plan(source, force=True))

        assert result.failed_count == 1
        assert output.read_text() == "previous successful output"

    def test_no_model_download_when_every_file_is_transcribed(self, tmp_path: Path) -> None:
        service, _, downloader, _ = self.make_service(StubTranscription())
        write(tmp_path / "scan.png")
        write(tmp_path / "report.pdf")

        service.execute(service.plan(tmp_path))

        assert downloader.download_calls == 0

    def test_models_download_when_some_file_needs_docling(self, tmp_path: Path) -> None:
        service, _, downloader, _ = self.make_service(StubTranscription())
        write(tmp_path / "scan.png")
        write(tmp_path / "memo.docx")

        service.execute(service.plan(tmp_path))

        assert downloader.download_calls == 1


class TestConvertExecute:
    """Tests for execute()."""

    def test_failed_image_description_preserves_existing_output(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        source = write(tmp_path / "report.pdf")
        output = write(tmp_path / "report.md", "previous successful output")
        vision = MagicMock()
        description = MagicMock()
        description.describe.return_value = PictureDescriptionResult(images_failed=1)
        service = ConvertService(
            output=OutputMirrorService(FileSystemAdapter(), StubProcessor()),
            file_discovery=FileDiscoveryAdapter(),
            vision_processor=vision,
            picture_description=description,
        )
        result = service.execute(service.plan(source, force=True))
        assert result.failed_count == 1
        assert result.images_failed == 1
        assert result.processed_count == 0
        assert output.read_text() == "previous successful output"
        assert (
            result.failures[0].reason
            == "Vision describe failed: 1 required image description failed"
        )
        assert "Unexpected error" not in caplog.text

    def test_vision_writes_outputs_and_advances_before_converting_entire_folder(
        self, tmp_path: Path
    ) -> None:
        """Vision conversion completes bounded batches before reading more documents."""
        processor = MagicMock()
        description = MagicMock()
        completed: list[str] = []
        completed_before_conversion: list[int] = []
        activities: list[Activity] = []

        def convert(source: Path) -> MagicMock:
            assert activities[-1].files == [source]
            assert activities[-1].stage == "converting"
            completed_before_conversion.append(len(completed))
            conversion = MagicMock()
            conversion.document.export_to_markdown.return_value = f"converted: {source.name}"
            return conversion

        processor.convert.side_effect = convert
        description.describe.return_value = MagicMock(
            images_described=0,
            images_skipped=0,
            images_failed=0,
            prompt_tokens=0,
            completion_tokens=0,
        )
        service = ConvertService(
            output=OutputMirrorService(FileSystemAdapter(), StubProcessor()),
            file_discovery=FileDiscoveryAdapter(),
            vision_processor=processor,
            picture_description=description,
        )
        for number in range(5):
            write(tmp_path / f"report-{number}.pdf")

        def on_completed(name: str) -> None:
            assert (tmp_path / name).with_suffix(".md").read_text() == f"converted: {name}"
            completed.append(name)

        result = service.execute(
            service.plan(tmp_path),
            progress_callback=on_completed,
            activity_callback=activities.append,
        )

        assert result.processed_count == 5
        assert result.failed_count == 0
        assert completed_before_conversion[-1] > 0, (
            "All documents were converted before any Markdown output or progress was produced"
        )
        assert len(completed) == 5
        assert activities[-1].stage == "writing"
        assert len(activities[-1].files) == 1

    def test_execute_writes_markdown_next_to_original(self, tmp_path: Path) -> None:
        """Each output is written next to its original: reports/q1.pdf -> reports/q1.md."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        write(docs / "reports" / "q1.pdf")

        result = service.execute(service.plan(docs))

        assert (docs / "reports" / "q1.md").exists()
        assert result.processed_count == 1
        assert result.failed_count == 0

    def test_execute_leaves_passthrough_untouched_without_output(self, tmp_path: Path) -> None:
        """Without --output, passthrough files keep their content and mtime."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        notes = write(docs / "notes.txt", "original text")
        before = notes.stat().st_mtime_ns
        write(docs / "report.pdf")

        result = service.execute(service.plan(docs))

        assert notes.read_text() == "original text"
        assert notes.stat().st_mtime_ns == before
        assert result.skipped_count == 1
        assert result.processed_count == 1

    def test_execute_copies_passthrough_into_output_tree(self, tmp_path: Path) -> None:
        """With --output, passthrough files are copied mirroring the tree."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        out = tmp_path / "out"
        write(docs / "notes.txt", "original text")
        write(docs / "reports" / "q1.pdf")

        result = service.execute(service.plan(docs, output_dir=out))

        assert (out / "notes.txt").read_text() == "original text"
        assert (out / "reports" / "q1.md").exists()
        assert not (docs / "reports" / "q1.md").exists()
        assert result.processed_count == 2

    def test_execute_records_failure_reason_and_continues(self, tmp_path: Path) -> None:
        """A failed file does not stop the run; the summary carries the reason."""
        service, _, _ = make_service(fail_names={"bad.pdf"})
        docs = tmp_path / "docs"
        write(docs / "good.pdf")
        write(docs / "bad.pdf")

        result = service.execute(service.plan(docs))

        assert (docs / "good.md").exists()
        assert not (docs / "bad.md").exists()
        assert result.processed_count == 1
        assert result.failed_count == 1
        assert [f.path.name for f in result.failures] == ["bad.pdf"]
        assert "stub failure for bad.pdf" in result.failures[0].reason

    def test_execute_skips_docling_file_colliding_with_passthrough(self, tmp_path: Path) -> None:
        """With --output, a passthrough file wins the output path over a Docling file."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        out = tmp_path / "out"
        write(docs / "report.md", "passthrough wins")
        write(docs / "report.pdf")

        result = service.execute(service.plan(docs, output_dir=out))

        assert (out / "report.md").read_text() == "passthrough wins"
        assert not (out / "report.pdf").exists()
        assert result.processed_count == 1
        assert result.skipped_count == 1
        collision = [s for s in result.skips if s.path.name == "report.pdf"]
        assert len(collision) == 1
        assert "conflicts" in collision[0].reason

    def test_execute_creates_no_project_artifacts(self, tmp_path: Path) -> None:
        """No manifest, .nest folder, index, or glossary is created anywhere."""
        service, _, _ = make_service()
        docs = tmp_path / "docs"
        write(docs / "q1.pdf")

        service.execute(service.plan(docs))

        assert not (tmp_path / ".nest").exists()
        assert list(tmp_path.rglob("manifest.json")) == []
        assert list(tmp_path.rglob("00_MASTER_INDEX.md")) == []
        assert list(tmp_path.rglob("glossary.md")) == []
        assert list(tmp_path.rglob("errors.log")) == []

    def test_execute_downloads_models_when_docling_files_pending(self, tmp_path: Path) -> None:
        """The model cache is consulted before converting Docling-convertible files."""
        service, _, downloader = make_service()
        write(tmp_path / "q1.pdf")

        service.execute(service.plan(tmp_path / "q1.pdf"))

        assert downloader.download_calls == 1

    def test_execute_skips_download_for_passthrough_only_run(self, tmp_path: Path) -> None:
        """No model download when only passthrough files are copied."""
        service, _, downloader = make_service()
        write(tmp_path / "notes.txt")

        service.execute(service.plan(tmp_path, output_dir=tmp_path / "out"))

        assert downloader.download_calls == 0

    def test_execute_advances_progress_once_per_attempted_file(self, tmp_path: Path) -> None:
        """Every attempted file (converted, skipped, or failed) advances progress once."""
        service, _, _ = make_service(fail_names={"bad.pdf"})
        docs = tmp_path / "docs"
        write(docs / "good.pdf")
        write(docs / "bad.pdf")
        write(docs / "notes.txt")

        seen: list[str] = []
        result = service.execute(service.plan(docs), progress_callback=seen.append)

        assert sorted(seen) == ["bad.pdf", "good.pdf", "notes.txt"]
        assert result.processed_count + result.skipped_count + result.failed_count == 3

    def test_execute_reports_existing_output_as_skipped(self, tmp_path: Path) -> None:
        """Re-running reports the existing output as skipped with its reason."""
        service, _, _ = make_service()
        pdf = write(tmp_path / "q1.pdf")

        service.execute(service.plan(pdf))
        result = service.execute(service.plan(pdf))

        assert result.processed_count == 0
        assert result.skipped_count == 1
        assert result.failures == []
        assert [s.path.name for s in result.skips] == ["q1.pdf"]
        assert "already exists" in result.skips[0].reason

    def test_execute_force_regenerates_existing_output(self, tmp_path: Path) -> None:
        """--force re-converts files whose output already exists."""
        service, _, _ = make_service()
        pdf = write(tmp_path / "q1.pdf")

        service.execute(service.plan(pdf))
        result = service.execute(service.plan(pdf, force=True))

        assert result.processed_count == 1
        assert (tmp_path / "q1.md").exists()

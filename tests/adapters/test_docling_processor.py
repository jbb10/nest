"""Tests for DoclingProcessor adapter."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from nest.adapters.protocols import DocumentProcessorProtocol
from nest.core.models import ProcessingResult

if TYPE_CHECKING:
    from nest.adapters.docling_processor import DoclingProcessor


class TestDocumentProcessorProtocolExists:
    """Tests that DocumentProcessorProtocol is properly defined."""

    def test_protocol_is_importable(self) -> None:
        """Test that DocumentProcessorProtocol can be imported."""
        # This will fail at import time if not defined
        assert DocumentProcessorProtocol is not None

    def test_protocol_has_process_method(self) -> None:
        """Test that protocol defines process method signature."""
        # Check that the protocol has the expected method
        assert hasattr(DocumentProcessorProtocol, "process")

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that protocol is runtime checkable for isinstance checks."""
        # Protocol should be decorated with @runtime_checkable
        # Check for _is_runtime_protocol attribute set by the decorator
        assert getattr(DocumentProcessorProtocol, "_is_runtime_protocol", False)


class TestProcessingResult:
    """Tests for ProcessingResult model."""

    def test_success_result(self, tmp_path: Path) -> None:
        """Test creating a successful processing result."""
        source = tmp_path / "doc.pdf"
        output = tmp_path / "doc.md"

        result = ProcessingResult(
            source_path=source,
            status="success",
            output_path=output,
        )

        assert result.source_path == source
        assert result.status == "success"
        assert result.output_path == output
        assert result.error is None

    def test_failed_result(self, tmp_path: Path) -> None:
        """Test creating a failed processing result with error."""
        source = tmp_path / "corrupt.pdf"

        result = ProcessingResult(
            source_path=source,
            status="failed",
            error="File is password protected",
        )

        assert result.source_path == source
        assert result.status == "failed"
        assert result.output_path is None
        assert result.error == "File is password protected"

    def test_skipped_result(self, tmp_path: Path) -> None:
        """Test creating a skipped processing result."""
        source = tmp_path / "unchanged.pdf"

        result = ProcessingResult(
            source_path=source,
            status="skipped",
        )

        assert result.source_path == source
        assert result.status == "skipped"
        assert result.output_path is None
        assert result.error is None

    def test_path_type_support(self, tmp_path: Path) -> None:
        """Test that Path objects are properly supported."""
        source = Path("/some/path/to/doc.pdf")
        output = Path("/output/doc.md")

        result = ProcessingResult(
            source_path=source,
            status="success",
            output_path=output,
        )

        assert isinstance(result.source_path, Path)
        assert isinstance(result.output_path, Path)


class TestDoclingProcessorImplementsProtocol:
    """Tests that DoclingProcessor implements DocumentProcessorProtocol."""

    def test_processor_is_importable(self) -> None:
        """Test that DoclingProcessor can be imported."""
        from nest.adapters.docling_processor import DoclingProcessor

        assert DoclingProcessor is not None

    def test_processor_implements_protocol(self) -> None:
        """Test that DoclingProcessor satisfies DocumentProcessorProtocol."""
        from nest.adapters.docling_processor import DoclingProcessor

        processor = DoclingProcessor()
        assert isinstance(processor, DocumentProcessorProtocol)

    def test_processor_has_process_method(self) -> None:
        """Test that DoclingProcessor has process method with correct signature."""
        from nest.adapters.docling_processor import DoclingProcessor

        processor = DoclingProcessor()
        assert hasattr(processor, "process")
        assert callable(processor.process)


class TestDoclingProcessorProcessing:
    """Tests for DoclingProcessor document processing functionality."""

    @pytest.fixture
    def processor(self) -> DoclingProcessor:
        """Create a DoclingProcessor instance."""
        from nest.adapters.docling_processor import DoclingProcessor

        return DoclingProcessor()

    def test_process_creates_output_directory(
        self, processor: DoclingProcessor, tmp_path: Path
    ) -> None:
        """Test that process creates parent directories for output."""
        # Create a simple HTML file (minimal test case)
        source = tmp_path / "source" / "test.html"
        source.parent.mkdir(parents=True)
        source.write_text("<html><body><p>Test content</p></body></html>")

        output = tmp_path / "nested" / "deep" / "output.md"

        result = processor.process(source, output)

        assert result.status == "success"
        assert output.parent.exists()
        assert output.exists()

    def test_process_html_to_markdown(self, processor: DoclingProcessor, tmp_path: Path) -> None:
        """Test HTML file processing produces Markdown output."""
        source = tmp_path / "test.html"
        source.write_text(
            """<!DOCTYPE html>
<html>
<head><title>Test Document</title></head>
<body>
<h1>Heading One</h1>
<p>This is a paragraph with <strong>bold</strong> text.</p>
<ul>
<li>Item 1</li>
<li>Item 2</li>
</ul>
</body>
</html>"""
        )
        output = tmp_path / "output.md"

        result = processor.process(source, output)

        assert result.status == "success"
        assert result.output_path == output
        assert result.error is None
        assert output.exists()

        content = output.read_text()
        # Verify some content was extracted
        assert len(content) > 0

    def test_process_nonexistent_file_returns_failed(
        self, processor: DoclingProcessor, tmp_path: Path
    ) -> None:
        """Test that processing a nonexistent file returns failed result."""
        source = tmp_path / "does_not_exist.pdf"
        output = tmp_path / "output.md"

        result = processor.process(source, output)

        assert result.status == "failed"
        assert result.source_path == source
        assert result.error is not None
        assert result.output_path is None

    def test_process_invalid_format_returns_failed(
        self, processor: DoclingProcessor, tmp_path: Path
    ) -> None:
        """Test that processing an unsupported format returns failed result."""
        source = tmp_path / "test.xyz"
        source.write_text("Some random content")
        output = tmp_path / "output.md"

        result = processor.process(source, output)

        assert result.status == "failed"
        assert result.error is not None

    def test_process_result_contains_source_path(
        self, processor: DoclingProcessor, tmp_path: Path
    ) -> None:
        """Test that ProcessingResult always includes source_path."""
        source = tmp_path / "test.html"
        source.write_text("<html><body>Content</body></html>")
        output = tmp_path / "output.md"

        result = processor.process(source, output)

        assert result.source_path == source


class TestDoclingProcessorBase64Exclusion:
    """Tests for base64 image exclusion (AC8)."""

    @pytest.fixture
    def processor(self) -> DoclingProcessor:
        """Create a DoclingProcessor instance."""
        from nest.adapters.docling_processor import DoclingProcessor

        return DoclingProcessor()

    def test_html_with_embedded_image_excludes_base64(
        self, processor: DoclingProcessor, tmp_path: Path
    ) -> None:
        """Test that HTML with embedded images produces clean Markdown without base64."""
        # Create HTML with a base64 embedded image
        source = tmp_path / "with_image.html"
        # Small 1x1 red pixel PNG encoded as base64
        base64_img = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAA"
            "DUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        source.write_text(
            f"""<!DOCTYPE html>
<html>
<body>
<h1>Document with Image</h1>
<p>Some text before image.</p>
<img src="data:image/png;base64,{base64_img}" alt="Test image">
<p>Some text after image.</p>
</body>
</html>"""
        )
        output = tmp_path / "output.md"

        result = processor.process(source, output)

        assert result.status == "success"
        content = output.read_text()

        # Verify base64 data is NOT in output
        assert "data:image/" not in content
        assert base64_img not in content

    def test_output_does_not_contain_base64_patterns(
        self, processor: DoclingProcessor, tmp_path: Path
    ) -> None:
        """Test that output Markdown never contains base64 data patterns."""
        import re

        source = tmp_path / "test.html"
        source.write_text("<html><body><p>Simple content</p></body></html>")
        output = tmp_path / "output.md"

        result = processor.process(source, output)

        assert result.status == "success"
        content = output.read_text()

        # Check for common base64 image patterns
        base64_pattern = re.compile(r"data:image/[a-z]+;base64,")
        assert not base64_pattern.search(content)


class TestDoclingProcessorErrorHandling:
    """Tests for error handling without logging (AC2 — adapters return results, never log)."""

    def test_failed_processing_returns_failed_result(self, tmp_path: Path) -> None:
        """Test that failed processing returns ProcessingResult with status='failed'."""
        from nest.adapters.docling_processor import DoclingProcessor

        processor = DoclingProcessor()

        # Process a nonexistent file to trigger an error
        source = tmp_path / "does_not_exist.pdf"
        output = tmp_path / "output.md"

        result = processor.process(source, output)

        assert result.status == "failed"
        assert result.error is not None
        assert "does_not_exist" in result.error

    def test_failed_processing_does_not_import_logging(self) -> None:
        """Test that DoclingProcessor does not import any logging module."""
        import importlib
        import inspect

        from nest.adapters import docling_processor

        importlib.reload(docling_processor)
        source = inspect.getsource(docling_processor)
        assert "from nest.core.logging" not in source
        assert "log_processing_error" not in source
        assert "import logging" not in source
        assert "logger.debug" not in source


# ---------------------------------------------------------------------------
# Story 7.2: Two-Pass Image Pipeline — DoclingProcessor classification tests
# AC: 1, 2, 3, 4, 5
# ---------------------------------------------------------------------------


class TestDoclingProcessorClassificationInit:
    """Tests for enable_classification constructor parameter (AC1, AC2)."""

    def test_default_constructor_sets_classification_false(self) -> None:
        """4.1 — Default constructor stores _enable_classification=False."""
        from nest.adapters.docling_processor import DoclingProcessor

        processor = DoclingProcessor()
        assert processor._enable_classification is False

    def test_classification_constructor_sets_flag_true(self) -> None:
        """4.2 — Classification constructor stores _enable_classification=True."""
        from nest.adapters.docling_processor import DoclingProcessor

        processor = DoclingProcessor(enable_classification=True)
        assert processor._enable_classification is True


class TestDoclingProcessorPipelineOptions:
    """Tests for PdfPipelineOptions construction (AC1, AC2)."""

    def test_pipeline_options_without_classification(self) -> None:
        """4.3 — Standard pipeline omits classification / image options."""
        from unittest.mock import patch

        with (
            patch("nest.adapters.docling_processor.PdfPipelineOptions") as mock_opts,
            patch("nest.adapters.docling_processor.PdfFormatOption"),
            patch("nest.adapters.docling_processor.TableStructureOptions"),
            patch("nest.adapters.docling_processor.DocumentConverter"),
        ):
            from nest.adapters.docling_processor import DoclingProcessor

            DoclingProcessor(enable_classification=False)

            assert mock_opts.call_count == 1
            _, kwargs = mock_opts.call_args
            assert "do_picture_classification" not in kwargs
            assert "generate_picture_images" not in kwargs
            assert "images_scale" not in kwargs
            assert "do_picture_description" not in kwargs

    def test_pipeline_options_with_classification(self) -> None:
        """4.4 — Classification pipeline includes correct image options."""
        from unittest.mock import patch

        with (
            patch("nest.adapters.docling_processor.PdfPipelineOptions") as mock_opts,
            patch("nest.adapters.docling_processor.PdfFormatOption"),
            patch("nest.adapters.docling_processor.TableStructureOptions"),
            patch("nest.adapters.docling_processor.DocumentConverter"),
        ):
            from nest.adapters.docling_processor import DoclingProcessor

            DoclingProcessor(enable_classification=True)

            assert mock_opts.call_count == 1
            _, kwargs = mock_opts.call_args
            assert kwargs.get("do_picture_classification") is True
            assert kwargs.get("do_picture_description") is False
            assert kwargs.get("generate_picture_images") is True
            assert kwargs.get("images_scale") == 2.0
            assert kwargs.get("do_table_structure") is True


class TestDoclingProcessorConvertMethod:
    """Tests for the new convert() method (AC3)."""

    def test_convert_delegates_to_internal_converter(self, tmp_path: Path) -> None:
        """4.5 — convert() calls _converter.convert() and returns its result."""
        from unittest.mock import MagicMock, patch

        with patch("nest.adapters.docling_processor.DocumentConverter") as mock_cls:
            from nest.adapters.docling_processor import DoclingProcessor

            mock_converter = mock_cls.return_value
            mock_result = MagicMock()
            mock_converter.convert.return_value = mock_result

            processor = DoclingProcessor(enable_classification=True)
            source = tmp_path / "doc.pdf"

            returned = processor.convert(source)

            mock_converter.convert.assert_called_once_with(source)
            assert returned is mock_result


class TestDoclingProcessorProcessWithMocks:
    """Unit tests for process() using mocked Docling (AC4, AC5)."""

    def test_process_without_classification_calls_converter_directly(self, tmp_path: Path) -> None:
        """4.6 — process() without classification calls _converter.convert() directly."""
        from unittest.mock import MagicMock, patch

        with patch("nest.adapters.docling_processor.DocumentConverter") as mock_cls:
            from nest.adapters.docling_processor import DoclingProcessor

            mock_converter = mock_cls.return_value
            mock_result = MagicMock()
            mock_result.document.export_to_markdown.return_value = "# Hello"
            mock_converter.convert.return_value = mock_result

            processor = DoclingProcessor(enable_classification=False)
            source = tmp_path / "doc.pdf"
            output = tmp_path / "doc.md"

            result = processor.process(source, output)

            mock_converter.convert.assert_called_once_with(source)
            assert result.status == "success"

    def test_process_with_classification_calls_self_convert(self, tmp_path: Path) -> None:
        """4.7 — process() with classification delegates via self.convert()."""
        from unittest.mock import MagicMock, patch

        with patch("nest.adapters.docling_processor.DocumentConverter") as mock_cls:
            from nest.adapters.docling_processor import DoclingProcessor

            mock_converter = mock_cls.return_value
            mock_docling_result = MagicMock()
            mock_docling_result.document.export_to_markdown.return_value = "# Hello"
            mock_converter.convert.return_value = mock_docling_result

            processor = DoclingProcessor(enable_classification=True)
            source = tmp_path / "doc.pdf"
            output = tmp_path / "doc.md"

            with patch.object(processor, "convert", wraps=processor.convert) as spy_convert:
                result = processor.process(source, output)

            spy_convert.assert_called_once_with(source)
            assert result.status == "success"

    def test_process_failure_path_returns_failed_result(self, tmp_path: Path) -> None:
        """4.10 — process() catches exceptions and returns ProcessingResult(status='failed')."""
        from unittest.mock import patch

        with patch("nest.adapters.docling_processor.DocumentConverter") as mock_cls:
            from nest.adapters.docling_processor import DoclingProcessor

            mock_converter = mock_cls.return_value
            mock_converter.convert.side_effect = Exception("bad file")

            processor = DoclingProcessor(enable_classification=False)
            source = tmp_path / "doc.pdf"
            output = tmp_path / "doc.md"

            result = processor.process(source, output)

            assert result.status == "failed"
            assert result.error == "bad file"
            assert result.source_path == source
            assert result.output_path is None

    def test_process_failure_path_with_classification_returns_failed_result(
        self, tmp_path: Path
    ) -> None:
        """4.10b — process() with enable_classification=True also catches exceptions."""
        from unittest.mock import patch

        with patch("nest.adapters.docling_processor.DocumentConverter") as mock_cls:
            from nest.adapters.docling_processor import DoclingProcessor

            mock_converter = mock_cls.return_value
            mock_converter.convert.side_effect = Exception("classify fail")

            processor = DoclingProcessor(enable_classification=True)
            source = tmp_path / "doc.pdf"
            output = tmp_path / "doc.md"

            result = processor.process(source, output)

            assert result.status == "failed"
            assert result.error == "classify fail"
            assert result.source_path == source
            assert result.output_path is None


class TestDoclingProcessorProtocolComplianceWithClassification:
    """Tests for DocumentProcessorProtocol compliance (AC4)."""

    def test_default_processor_satisfies_protocol(self) -> None:
        """4.8 — DoclingProcessor() is instance of DocumentProcessorProtocol."""
        from nest.adapters.docling_processor import DoclingProcessor

        assert isinstance(DoclingProcessor(), DocumentProcessorProtocol)

    def test_classification_processor_satisfies_protocol(self) -> None:
        """4.9 — DoclingProcessor(enable_classification=True) satisfies protocol."""
        from nest.adapters.docling_processor import DoclingProcessor

        assert isinstance(DoclingProcessor(enable_classification=True), DocumentProcessorProtocol)

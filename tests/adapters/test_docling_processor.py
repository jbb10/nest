"""Tests for DoclingProcessor adapter."""

from pathlib import Path

import pytest

from nest.adapters.protocols import DocumentProcessorProtocol
from nest.core.models import ProcessingResult


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
    def processor(self) -> "DoclingProcessor":
        """Create a DoclingProcessor instance."""
        from nest.adapters.docling_processor import DoclingProcessor

        return DoclingProcessor()

    def test_process_creates_output_directory(
        self, processor: "DoclingProcessor", tmp_path: Path
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

    def test_process_html_to_markdown(self, processor: "DoclingProcessor", tmp_path: Path) -> None:
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
        self, processor: "DoclingProcessor", tmp_path: Path
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
        self, processor: "DoclingProcessor", tmp_path: Path
    ) -> None:
        """Test that processing an unsupported format returns failed result."""
        source = tmp_path / "test.xyz"
        source.write_text("Some random content")
        output = tmp_path / "output.md"

        result = processor.process(source, output)

        assert result.status == "failed"
        assert result.error is not None

    def test_process_result_contains_source_path(
        self, processor: "DoclingProcessor", tmp_path: Path
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
    def processor(self) -> "DoclingProcessor":
        """Create a DoclingProcessor instance."""
        from nest.adapters.docling_processor import DoclingProcessor

        return DoclingProcessor()

    def test_html_with_embedded_image_excludes_base64(
        self, processor: "DoclingProcessor", tmp_path: Path
    ) -> None:
        """Test that HTML with embedded images produces clean Markdown without base64."""
        # Create HTML with a base64 embedded image
        source = tmp_path / "with_image.html"
        # Small 1x1 red pixel PNG encoded as base64
        base64_img = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
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
        self, processor: "DoclingProcessor", tmp_path: Path
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


class TestDoclingProcessorErrorLogging:
    """Tests for error logging integration (AC6, AC7)."""

    def test_failed_processing_logs_to_error_file(self, tmp_path: Path) -> None:
        """Test that failed processing writes to .nest_errors.log."""
        import logging

        from nest.adapters.docling_processor import DoclingProcessor

        # Clear any existing handlers
        logger = logging.getLogger("nest.errors")
        logger.handlers.clear()

        error_log = tmp_path / ".nest_errors.log"
        processor = DoclingProcessor(error_log=error_log)

        # Process a nonexistent file to trigger an error
        source = tmp_path / "does_not_exist.pdf"
        output = tmp_path / "output.md"

        result = processor.process(source, output)

        # Flush handlers to ensure log is written
        for handler in logger.handlers:
            handler.flush()

        assert result.status == "failed"
        assert error_log.exists()
        content = error_log.read_text()
        assert "does_not_exist.pdf" in content
        assert "[sync]" in content

    def test_error_log_uses_custom_path(self, tmp_path: Path) -> None:
        """Test that processor uses provided error_log path."""
        import logging

        from nest.adapters.docling_processor import DoclingProcessor

        # Clear any existing handlers
        logger = logging.getLogger("nest.errors")
        logger.handlers.clear()

        custom_log = tmp_path / "custom" / "errors.log"
        processor = DoclingProcessor(error_log=custom_log)

        source = tmp_path / "bad_file.xyz"
        source.write_text("not a valid document")
        output = tmp_path / "output.md"

        processor.process(source, output)

        # Flush handlers
        for handler in logger.handlers:
            handler.flush()

        assert custom_log.exists()

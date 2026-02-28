"""Tests for passthrough file processor.

Tests the PassthroughProcessor which copies text files without conversion.
"""

from pathlib import Path

from nest.adapters.passthrough_processor import PassthroughProcessor


class TestPassthroughProcessor:
    """Tests for PassthroughProcessor class."""

    def test_copies_file_content_accurately(self, tmp_path: Path) -> None:
        """AC2: File content is copied exactly."""
        source = tmp_path / "source" / "notes.txt"
        source.parent.mkdir(parents=True)
        source.write_text("Meeting notes from 2026-02-26")

        output = tmp_path / "output" / "notes.txt"

        processor = PassthroughProcessor()
        result = processor.process(source, output)

        assert result.status == "success"
        assert output.exists()
        assert output.read_text() == "Meeting notes from 2026-02-26"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """AC3: Parent directories are created as needed."""
        source = tmp_path / "source" / "team" / "notes.txt"
        source.parent.mkdir(parents=True)
        source.write_text("content")

        output = tmp_path / "output" / "team" / "notes.txt"

        processor = PassthroughProcessor()
        result = processor.process(source, output)

        assert result.status == "success"
        assert output.exists()
        assert output.parent.exists()

    def test_preserves_original_extension(self, tmp_path: Path) -> None:
        """AC2: Original extension is preserved (not changed to .md)."""
        source = tmp_path / "source" / "config.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("key: value")

        output = tmp_path / "output" / "config.yaml"

        processor = PassthroughProcessor()
        result = processor.process(source, output)

        assert result.status == "success"
        assert result.output_path == output
        assert result.output_path.suffix == ".yaml"

    def test_returns_correct_source_path(self, tmp_path: Path) -> None:
        """ProcessingResult contains correct source_path."""
        source = tmp_path / "source" / "notes.txt"
        source.parent.mkdir(parents=True)
        source.write_text("content")

        output = tmp_path / "output" / "notes.txt"

        processor = PassthroughProcessor()
        result = processor.process(source, output)

        assert result.source_path == source

    def test_returns_correct_output_path(self, tmp_path: Path) -> None:
        """ProcessingResult contains correct output_path."""
        source = tmp_path / "source" / "notes.txt"
        source.parent.mkdir(parents=True)
        source.write_text("content")

        output = tmp_path / "output" / "notes.txt"

        processor = PassthroughProcessor()
        result = processor.process(source, output)

        assert result.output_path == output

    def test_handles_missing_source_gracefully(self, tmp_path: Path) -> None:
        """Missing source file returns failure result."""
        source = tmp_path / "nonexistent.txt"
        output = tmp_path / "output" / "nonexistent.txt"

        processor = PassthroughProcessor()
        result = processor.process(source, output)

        assert result.status == "failed"
        assert result.error is not None

    def test_overwrites_existing_output(self, tmp_path: Path) -> None:
        """Existing output file is overwritten."""
        source = tmp_path / "source" / "notes.txt"
        source.parent.mkdir(parents=True)
        source.write_text("updated content")

        output = tmp_path / "output" / "notes.txt"
        output.parent.mkdir(parents=True)
        output.write_text("old content")

        processor = PassthroughProcessor()
        result = processor.process(source, output)

        assert result.status == "success"
        assert output.read_text() == "updated content"

    def test_handles_binary_content(self, tmp_path: Path) -> None:
        """Binary content is copied accurately."""
        source = tmp_path / "source" / "data.bin"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"\x00\x01\x02\x03\xff")

        output = tmp_path / "output" / "data.bin"

        processor = PassthroughProcessor()
        result = processor.process(source, output)

        assert result.status == "success"
        assert output.read_bytes() == b"\x00\x01\x02\x03\xff"

    def test_deeply_nested_directories(self, tmp_path: Path) -> None:
        """Deeply nested directory structures are created correctly."""
        source = tmp_path / "source" / "a" / "b" / "c" / "d" / "notes.txt"
        source.parent.mkdir(parents=True)
        source.write_text("deep content")

        output = tmp_path / "output" / "a" / "b" / "c" / "d" / "notes.txt"

        processor = PassthroughProcessor()
        result = processor.process(source, output)

        assert result.status == "success"
        assert output.exists()
        assert output.read_text() == "deep content"

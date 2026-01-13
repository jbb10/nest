"""Tests for checksum computation module."""

import hashlib
from pathlib import Path

import pytest

from nest.core.checksum import compute_sha256


class TestComputeSha256:
    """Tests for compute_sha256 function."""

    def test_computes_correct_sha256_for_small_file(self, tmp_path: Path) -> None:
        """Verify SHA-256 computation produces correct hash for known content."""
        # Arrange
        test_content = b"Hello, World!"
        expected_hash = hashlib.sha256(test_content).hexdigest()
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(test_content)

        # Act
        result = compute_sha256(test_file)

        # Assert
        assert result == expected_hash
        assert len(result) == 64  # SHA-256 hex string length
        assert result.islower()  # Lowercase hex encoding

    def test_computes_correct_sha256_for_large_file(self, tmp_path: Path) -> None:
        """Verify chunked reading handles large files correctly."""
        # Arrange - Create file larger than default chunk size (64KB)
        test_content = b"x" * (100 * 1024)  # 100KB
        expected_hash = hashlib.sha256(test_content).hexdigest()
        test_file = tmp_path / "large_file.bin"
        test_file.write_bytes(test_content)

        # Act
        result = compute_sha256(test_file)

        # Assert
        assert result == expected_hash

    def test_computes_same_hash_for_identical_content(self, tmp_path: Path) -> None:
        """Verify identical files produce identical hashes."""
        # Arrange
        content = b"identical content"
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_bytes(content)
        file2.write_bytes(content)

        # Act
        hash1 = compute_sha256(file1)
        hash2 = compute_sha256(file2)

        # Assert
        assert hash1 == hash2

    def test_computes_different_hash_for_different_content(
        self, tmp_path: Path
    ) -> None:
        """Verify different files produce different hashes."""
        # Arrange
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_bytes(b"content A")
        file2.write_bytes(b"content B")

        # Act
        hash1 = compute_sha256(file1)
        hash2 = compute_sha256(file2)

        # Assert
        assert hash1 != hash2

    def test_raises_file_not_found_for_missing_file(self, tmp_path: Path) -> None:
        """Verify FileNotFoundError raised for non-existent file."""
        # Arrange
        nonexistent = tmp_path / "does_not_exist.txt"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            compute_sha256(nonexistent)

    def test_handles_empty_file(self, tmp_path: Path) -> None:
        """Verify empty files are handled correctly."""
        # Arrange
        empty_file = tmp_path / "empty.txt"
        empty_file.write_bytes(b"")
        expected_hash = hashlib.sha256(b"").hexdigest()

        # Act
        result = compute_sha256(empty_file)

        # Assert
        assert result == expected_hash

    def test_accepts_custom_chunk_size(self, tmp_path: Path) -> None:
        """Verify custom chunk size works correctly."""
        # Arrange
        test_content = b"test content"
        expected_hash = hashlib.sha256(test_content).hexdigest()
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(test_content)

        # Act - Use small chunk size to force multiple reads
        result = compute_sha256(test_file, chunk_size=4)

        # Assert
        assert result == expected_hash

"""Checksum computation utilities.

This module provides functions for computing cryptographic hashes of files,
using chunked reading for memory efficiency with large files.
"""

import hashlib
from pathlib import Path


def compute_sha256(path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file using chunked reading.

    Args:
        path: Path to the file to hash.
        chunk_size: Size of chunks to read in bytes (default 64KB).

    Returns:
        Lowercase hex-encoded SHA-256 hash string.

    Raises:
        FileNotFoundError: If path does not exist.

    Example:
        >>> from pathlib import Path
        >>> hash_value = compute_sha256(Path("document.pdf"))
        >>> print(hash_value)  # 64 character hex string
        'a1b2c3...'
    """
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

"""Factory for the classification-enabled Docling processor.

Both the vision pass and the standalone-image rule need Docling's picture
classifier. Importing Docling is deferred to the call so that lightweight
commands never load it, and callers get ``None`` when Docling is missing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nest.adapters.docling_processor import DoclingProcessor


def create_classification_processor() -> DoclingProcessor | None:
    """Build a classification-enabled Docling processor, or ``None`` without Docling."""
    try:
        from nest.adapters.docling_processor import DoclingProcessor
    except ImportError:
        return None
    return DoclingProcessor(enable_classification=True)

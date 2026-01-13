"""Docling model downloader adapter.

Wraps Docling's download_models() utility for ML model management.
"""

import time
from pathlib import Path

from docling.datamodel.settings import settings
from docling.utils.model_downloader import download_models

from nest.core.exceptions import ModelError


class DoclingModelDownloader:
    """Adapter for downloading and caching Docling ML models.

    Uses Docling's built-in model downloader with retry logic for
    network failures. Manages model cache at ~/.cache/docling/models/.
    """

    DEFAULT_MODELS = {
        "layout": True,
        "tableformer": True,
        "code_formula": True,
        "picture_classifier": True,
        "rapidocr": True,
    }

    MAX_RETRIES = 3
    REQUIRED_CACHE_FOLDERS = [
        "docling-project--docling-models",
    ]

    def are_models_cached(self) -> bool:
        """Check if required models are already cached.

        Returns:
            True if all required model folders exist, False otherwise.
        """
        cache_dir = self.get_cache_path()

        for folder in self.REQUIRED_CACHE_FOLDERS:
            if not (cache_dir / folder).exists():
                return False

        return True

    def download_if_needed(self, progress: bool = True) -> bool:
        """Download models if not already cached.

        Args:
            progress: Whether to show download progress bars.

        Returns:
            True if download occurred, False if already cached.

        Raises:
            ModelError: If download fails after retries.
        """
        if self.are_models_cached():
            return False

        self._download_with_retry(progress)
        return True

    def get_cache_path(self) -> Path:
        """Get the path to the model cache directory.

        Returns:
            Path to the cache directory (~/.cache/docling/models/).
        """
        return settings.cache_dir / "models"

    def _download_with_retry(self, progress: bool) -> None:
        """Download models with exponential backoff retry logic.

        Args:
            progress: Whether to show download progress bars.

        Raises:
            ModelError: If all retry attempts fail.
        """
        last_exception: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                download_models(
                    output_dir=None,  # Uses default cache location
                    force=False,
                    progress=progress,
                    with_layout=self.DEFAULT_MODELS["layout"],
                    with_tableformer=self.DEFAULT_MODELS["tableformer"],
                    with_code_formula=self.DEFAULT_MODELS["code_formula"],
                    with_picture_classifier=self.DEFAULT_MODELS["picture_classifier"],
                    with_rapidocr=self.DEFAULT_MODELS["rapidocr"],
                )
                return  # Success!
            except Exception as e:
                last_exception = e
                if attempt < self.MAX_RETRIES - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    time.sleep(2 ** attempt)

        # All retries exhausted
        raise ModelError(
            "Failed to download ML models after 3 attempts. "
            "Check your internet connection and try again."
        ) from last_exception

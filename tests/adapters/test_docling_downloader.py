"""Tests for DoclingModelDownloader adapter."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nest.adapters.docling_downloader import DoclingModelDownloader
from nest.core.exceptions import ModelError

# Shared patch target for the lazy settings helper
_SETTINGS_TARGET = "nest.adapters.docling_downloader._get_docling_settings"
_DOWNLOAD_TARGET = "nest.adapters.docling_downloader._get_download_models"


def _mock_settings(tmp_path: Path) -> MagicMock:
    """Create a mock settings object pointing cache_dir at tmp_path."""
    mock = MagicMock()
    mock.cache_dir = tmp_path
    return mock


class TestDoclingModelDownloader:
    """Tests for DoclingModelDownloader adapter."""

    def test_are_models_cached_when_folders_exist(self, tmp_path: Path) -> None:
        """Test cache detection returns True when folders exist."""
        downloader = DoclingModelDownloader()
        cache_dir = tmp_path / "models" / "docling-project--docling-models"
        cache_dir.mkdir(parents=True)
        with patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)):
            result = downloader.are_models_cached()
        assert result is True

    def test_are_models_cached_when_folders_missing(self, tmp_path: Path) -> None:
        """Test cache detection returns False when folders missing."""
        downloader = DoclingModelDownloader()
        with patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)):
            result = downloader.are_models_cached()
        assert result is False

    def test_get_cache_path_returns_models_directory(self, tmp_path: Path) -> None:
        """Test cache path returns settings.cache_dir/models."""
        downloader = DoclingModelDownloader()
        with patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)):
            result = downloader.get_cache_path()
        assert result == tmp_path / "models"

    def test_download_if_needed_when_already_cached(self, tmp_path: Path) -> None:
        """Test download skipped when models already cached."""
        downloader = DoclingModelDownloader()
        cache_dir = tmp_path / "models" / "docling-project--docling-models"
        cache_dir.mkdir(parents=True)
        mock_download = MagicMock()
        with (
            patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)),
            patch(_DOWNLOAD_TARGET, return_value=mock_download),
        ):
            result = downloader.download_if_needed(progress=True)
        assert result is False
        mock_download.assert_not_called()

    def test_download_if_needed_when_not_cached(self, tmp_path: Path) -> None:
        """Test download occurs when models not cached."""
        downloader = DoclingModelDownloader()
        mock_download = MagicMock()
        with (
            patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)),
            patch(_DOWNLOAD_TARGET, return_value=mock_download),
        ):
            result = downloader.download_if_needed(progress=True)
        assert result is True
        mock_download.assert_called_once_with(
            output_dir=None,
            force=False,
            progress=True,
            with_layout=True,
            with_tableformer=True,
            with_code_formula=True,
            with_picture_classifier=True,
            with_rapidocr=True,
        )

    @patch("nest.adapters.docling_downloader.time.sleep")
    def test_download_retries_on_network_error(
        self, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        """Test download retries on network errors."""
        downloader = DoclingModelDownloader()
        mock_download = MagicMock(
            side_effect=[
                ConnectionError("Network error"),
                ConnectionError("Network error"),
                None,
            ]
        )
        with (
            patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)),
            patch(_DOWNLOAD_TARGET, return_value=mock_download),
        ):
            result = downloader.download_if_needed(progress=True)
        assert result is True
        assert mock_download.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("nest.adapters.docling_downloader.time.sleep")
    def test_download_raises_model_error_after_max_retries(
        self, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        """Test ModelError raised after all retries exhausted."""
        downloader = DoclingModelDownloader()
        mock_download = MagicMock(side_effect=ConnectionError("Network error"))
        with (
            patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)),
            patch(_DOWNLOAD_TARGET, return_value=mock_download),
        ):
            with pytest.raises(ModelError) as exc_info:
                downloader.download_if_needed(progress=True)
        assert "Failed to download ML models after 3 attempts" in str(exc_info.value)
        assert "Check your internet connection" in str(exc_info.value)
        assert mock_download.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("nest.adapters.docling_downloader.time.sleep")
    def test_download_exponential_backoff(
        self, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        """Test exponential backoff between retries."""
        downloader = DoclingModelDownloader()
        mock_download = MagicMock(
            side_effect=[
                ConnectionError("Network error"),
                ConnectionError("Network error"),
                None,
            ]
        )
        with (
            patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)),
            patch(_DOWNLOAD_TARGET, return_value=mock_download),
        ):
            downloader.download_if_needed(progress=True)
        assert mock_sleep.call_args_list[0][0][0] == 1  # 2^0
        assert mock_sleep.call_args_list[1][0][0] == 2  # 2^1

    @patch("nest.adapters.docling_downloader.shutil.disk_usage")
    def test_download_raises_error_on_insufficient_disk_space(
        self, mock_disk_usage: MagicMock, tmp_path: Path
    ) -> None:
        """Test ModelError raised when insufficient disk space available."""
        downloader = DoclingModelDownloader()
        mock_usage = MagicMock()
        mock_usage.free = 1024 * 1024 * 1024  # 1GB in bytes
        mock_disk_usage.return_value = mock_usage
        with patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)):
            with pytest.raises(ModelError) as exc_info:
                downloader.download_if_needed(progress=True)
        assert "Insufficient disk space" in str(exc_info.value)
        assert "2500MB required" in str(exc_info.value)


class TestGetCacheSize:
    """Tests for get_cache_size() method."""

    def test_get_cache_size_with_files(self, tmp_path: Path) -> None:
        """Test cache size calculation with files in cache."""
        downloader = DoclingModelDownloader()
        cache_dir = tmp_path / "models"
        cache_dir.mkdir(parents=True)
        (cache_dir / "model1.bin").write_bytes(b"x" * 1000)
        (cache_dir / "model2.bin").write_bytes(b"y" * 2000)
        subdir = cache_dir / "subfolder"
        subdir.mkdir()
        (subdir / "model3.bin").write_bytes(b"z" * 500)
        with patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)):
            size = downloader.get_cache_size()
        assert size == 3500

    def test_get_cache_size_empty_directory(self, tmp_path: Path) -> None:
        """Test cache size returns 0 for empty directory."""
        downloader = DoclingModelDownloader()
        cache_dir = tmp_path / "models"
        cache_dir.mkdir(parents=True)
        with patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)):
            size = downloader.get_cache_size()
        assert size == 0

    def test_get_cache_size_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test cache size returns 0 when cache does not exist."""
        downloader = DoclingModelDownloader()
        with patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)):
            size = downloader.get_cache_size()
        assert size == 0


class TestGetCacheStatus:
    """Tests for get_cache_status() method."""

    def test_get_cache_status_not_created(self, tmp_path: Path) -> None:
        """Test cache status when directory does not exist."""
        downloader = DoclingModelDownloader()
        with patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)):
            status = downloader.get_cache_status()
        assert status == "not_created"

    def test_get_cache_status_empty(self, tmp_path: Path) -> None:
        """Test cache status when directory is empty."""
        downloader = DoclingModelDownloader()
        cache_dir = tmp_path / "models"
        cache_dir.mkdir(parents=True)
        with patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)):
            status = downloader.get_cache_status()
        assert status == "empty"

    def test_get_cache_status_exists(self, tmp_path: Path) -> None:
        """Test cache status when directory has files."""
        downloader = DoclingModelDownloader()
        cache_dir = tmp_path / "models"
        cache_dir.mkdir(parents=True)
        (cache_dir / "model.bin").write_bytes(b"content")
        with patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)):
            status = downloader.get_cache_status()
        assert status == "exists"

    def test_get_cache_status_with_only_subdirectories(self, tmp_path: Path) -> None:
        """Test cache status treats empty subdirectories as empty."""
        downloader = DoclingModelDownloader()
        cache_dir = tmp_path / "models"
        cache_dir.mkdir(parents=True)
        (cache_dir / "subdir").mkdir()
        with patch(_SETTINGS_TARGET, return_value=_mock_settings(tmp_path)):
            status = downloader.get_cache_status()
        assert status == "empty"

"""Tests for status display formatting."""

from datetime import datetime, timedelta, timezone

from rich.console import Console

from nest.services.status_service import StatusReport
from nest.ui.status_display import display_status, format_relative_time


class TestFormatRelativeTime:
    def test_none_is_never(self) -> None:
        assert format_relative_time(None) == "never"

    def test_just_now(self) -> None:
        dt = datetime.now(timezone.utc) - timedelta(seconds=10)
        assert format_relative_time(dt) == "just now"

    def test_minutes(self) -> None:
        dt = datetime.now(timezone.utc) - timedelta(minutes=2)
        assert format_relative_time(dt) == "2 minutes ago"

    def test_hours(self) -> None:
        dt = datetime.now(timezone.utc) - timedelta(hours=1)
        assert format_relative_time(dt) == "1 hour ago"

    def test_days(self) -> None:
        dt = datetime.now(timezone.utc) - timedelta(days=3)
        assert format_relative_time(dt) == "3 days ago"


class TestDisplayStatus:
    def test_all_up_to_date_message(self) -> None:
        console = Console(record=True)
        report = StatusReport(
            project_name="X",
            nest_version="1.0.0",
            source_total=1,
            source_new=0,
            source_modified=0,
            source_unchanged=1,
            context_files=1,
            context_orphaned=0,
            last_sync=None,
            pending_count=0,
        )

        display_status(report, console)
        out = console.export_text()
        assert "All files up to date" in out
        assert "Run `nest sync`" not in out

    def test_pending_prompt(self) -> None:
        console = Console(record=True)
        report = StatusReport(
            project_name="X",
            nest_version="1.0.0",
            source_total=2,
            source_new=1,
            source_modified=1,
            source_unchanged=0,
            context_files=0,
            context_orphaned=0,
            last_sync=None,
            pending_count=2,
        )

        display_status(report, console)
        out = console.export_text()
        assert "Run `nest sync` to process 2 pending files" in out

# Story 2.8: Sync Command CLI Integration

Status: done
Branch: feat/2-8-sync-command-cli-integration

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

**As a** user,
**I want** clear visual feedback during sync,
**So that** I know what's happening with my documents.

## Acceptance Criteria

### AC1: Rich Progress Display During Processing
**Given** sync processes multiple files
**When** Rich progress displays
**Then** a progress bar shows:
- Current file being processed
- Progress: `[████████████--------] 60%`
- Count: `Processing 30/50 files`

### AC2: Sync Completion Summary
**Given** sync completes
**When** summary is displayed
**Then** output shows:
```
✓ Sync complete

  Processed: 15 files
  Skipped:   32 unchanged
  Failed:    2 (see .nest_errors.log)
  Orphans:   3 removed

  Index updated: 00_MASTER_INDEX.md
```

### AC3: Error When Outside Nest Project
**Given** sync runs outside a Nest project (no manifest)
**When** command executes
**Then** error displays: "No Nest project found. Run `nest init` first."

### AC4: CLI Layer Wires Dependencies Correctly
**Given** CLI layer (`sync_cmd.py`)
**When** it creates SyncService
**Then** it injects: FileSystemAdapter, DoclingProcessor, ManifestAdapter
**And** passes flag values (on_error, dry_run, force, no_clean)

## Tasks / Subtasks

- [x] **Task 1: Add Rich Progress Bar to SyncService** (AC: #1)
  - [x] 1.1 Create `src/nest/ui/progress.py` module
    - Implement `SyncProgress` class wrapping Rich `Progress`
    - Methods: `start(total: int)`, `advance(current_file: str)`, `finish()`
    - Progress format: `[████████████--------] 60% (30/50) processing contract.pdf`
  - [x] 1.2 Add optional `progress` callback to `SyncService.sync()`
    - Accept callback `progress: SyncProgress | None = None`
    - Call `progress.advance(file.name)` after each file processed
  - [x] 1.3 Update CLI to create and pass `SyncProgress` instance
    - Create progress context manager in sync_cmd.py
    - Only show progress when files_to_process > 0

- [x] **Task 2: Enhance Sync Completion Summary** (AC: #2)
  - [x] 2.1 Update `SyncService` to return `SyncResult` model (not just `OrphanCleanupResult`)
    - Create `SyncResult` model in `core/models.py`:
    ```python
    class SyncResult(BaseModel):
        processed_count: int
        skipped_count: int
        failed_count: int
        orphans_removed: int
        orphans_detected: int
        skipped_orphan_cleanup: bool
    ```
  - [x] 2.2 Track processing counts within SyncService processing loop
    - Count successful, skipped, and failed files
    - Include orphan info from OrphanCleanupResult
  - [x] 2.3 Update `_display_sync_summary()` in `sync_cmd.py`
    - Accept `SyncResult` instead of `OrphanCleanupResult`
    - Display full summary with all counts:
      ```
      ✓ Sync complete

        Processed: 15 files
        Skipped:   32 unchanged
        Failed:    2 (see .nest_errors.log)
        Orphans:   3 removed

        Index updated: 00_MASTER_INDEX.md
      ```

- [x] **Task 3: Add Project Validation Check** (AC: #3)
  - [x] 3.1 Add check at start of `sync_command()` for `.nest_manifest.json`
    - Use `(project_root / ".nest_manifest.json").exists()` check
    - If missing, call `error("No Nest project found")` and `raise typer.Exit(1)`
  - [x] 3.2 Display What → Why → Action format:
    ```
    ✗ No Nest project found
      Reason: .nest_manifest.json not found in this directory
      Action: Run `nest init "Project Name"` to initialize
    ```

- [x] **Task 4: Verify and Document CLI Wiring** (AC: #4)
  - [x] 4.1 Review `create_sync_service()` composition root
    - Confirm all adapters are injected: FileSystemAdapter, DoclingProcessor, ManifestAdapter
    - Confirm all flags flow correctly: on_error, dry_run, force, no_clean
  - [x] 4.2 Add inline docstring comments documenting the wiring
  - [x] 4.3 Verify existing test coverage in `tests/cli/test_sync_cmd.py`

- [x] **Task 5: Testing** (AC: all)
  - [x] 5.1 Unit tests for progress helper (`tests/ui/test_progress.py`):
    - Test progress bar creation and advancement
    - Test progress message format
  - [x] 5.2 Service tests for SyncResult model:
    - Test count tracking (processed, skipped, failed)
    - Test orphan counts included
  - [x] 5.3 CLI tests for project validation:
    - Test error when no manifest
    - Test proper error message format
  - [x] 5.4 Integration test `tests/integration/test_sync_cli.py`:
    - Test full CLI with progress display
    - Test summary output format
    - Test project validation

## Dev Notes

### Architecture Compliance

**Layer Responsibilities:**
```
cli/sync_cmd.py              → Project validation, progress setup, summary display
services/sync_service.py     → Processing with progress callbacks, count tracking
core/models.py               → SyncResult model (NEW)
ui/progress.py               → Rich progress bar wrapper (NEW)
ui/messages.py               → Summary formatting helpers
```

**Dependency Flow:**
```
CLI Layer
  ↓ (validates project, creates progress)
SyncService
  ↓ (calls progress callback on each file)
ProcessingLoop
  ↓ (returns SyncResult with counts)
CLI Layer
  ↓ (displays formatted summary)
Console
```

### Existing Infrastructure (DO NOT REINVENT)

**Already Implemented (from Stories 2.1-2.7):**
- `sync_cmd.py` with all flag handling (on_error, dry_run, force, no_clean)
- `SyncService.sync()` orchestration with full processing loop
- `DryRunResult` model for dry-run output
- `OrphanCleanupResult` model with orphan counts
- Rich console output helpers in `ui/messages.py`
- Error logging via `ui/logger.py`
- `_display_dry_run_result()` and `_display_sync_summary()` helpers

**Stub Command Was Already Replaced:**
The dev note in epics mentions "A stub `sync` command already exists... Replace the stub with the real implementation." This was done in Story 2.7 — `sync_cmd.py` now has the full implementation. This story adds polish: progress bar, enhanced summary, and project validation.

### Rich Progress Pattern

Use Rich's `Progress` class with custom columns:
```python
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn

with Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    TextColumn("{task.completed}/{task.total}"),
) as progress:
    task = progress.add_task("Processing files", total=50)
    for file in files:
        process(file)
        progress.update(task, advance=1, description=f"Processing {file.name}")
```

### Testing Patterns

**Mocking Progress for Tests:**
```python
class MockProgress:
    def __init__(self) -> None:
        self.advances: list[str] = []
    
    def advance(self, filename: str) -> None:
        self.advances.append(filename)
```

**Testing Console Output:**
```python
from io import StringIO
from rich.console import Console

def test_summary_shows_counts():
    output = StringIO()
    console = Console(file=output, force_terminal=True)
    # ... call display function with console
    assert "Processed: 15 files" in output.getvalue()
```

### Project Structure Notes

**New Files to Create:**
- `src/nest/ui/progress.py` — Progress bar wrapper
- `tests/ui/test_progress.py` — Progress unit tests
- `tests/integration/test_sync_cli.py` — CLI integration tests (may merge with existing)

**Files to Modify:**
- `src/nest/core/models.py` — Add `SyncResult` model
- `src/nest/services/sync_service.py` — Add progress callback, return SyncResult
- `src/nest/cli/sync_cmd.py` — Project validation, progress integration, enhanced summary

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.8] — Original acceptance criteria
- [Source: _bmad-output/project-context.md#CLI Output Patterns] — Rich output rules
- [Source: _bmad-output/project-context.md#Architecture & Dependency Injection] — Layer structure
- [Source: src/nest/cli/sync_cmd.py] — Existing CLI implementation with flags
- [Source: src/nest/services/sync_service.py] — Current service implementation
- [Source: src/nest/ui/messages.py] — Existing console helpers
- [Source: _bmad-output/implementation-artifacts/2-7-sync-command-flags-and-error-handling.md] — Previous story patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (via GitHub Copilot)

### Debug Log References

No significant issues encountered during implementation.

### Code Review Fixes (2026-01-16)

**Medium Issues Fixed:**
- **Double Discovery Performance Hit**: Refactored `SyncService` to expose `discover()` method and accept optional `changes` argument in `sync()`. CLI now calls `discover()` once and passes results to `sync()`.
- **Duplicate Service Instantiation**: Removed manual instantiation of `DiscoveryService` and adapters in CLI, reusing the service instance from `create_sync_service`.

**Low Issues Fixed:**
- **Local Imports in CLI**: Removed local imports in `sync_command`, relying on the injected service.

**Tests Added:**
- `TestSyncDiscovery` in `tests/services/test_sync_service.py` to verify discovery delegation and changes injection.

### Completion Notes List

- Created `src/nest/ui/progress.py` with `SyncProgress` class wrapping Rich Progress
- Added `progress_callback` parameter to `SyncService.sync()` for progress updates
- Created `SyncResult` model to replace `OrphanCleanupResult` for sync return values
- Updated `SyncService` to track processed/skipped/failed counts during processing
- Enhanced `_display_sync_summary()` to show full counts with formatted output
- Added project validation check (manifest existence) at start of sync command
- Enhanced `create_sync_service()` docstring with full dependency documentation
- Added comprehensive tests: 267 total (up from 254)

### File List

**New Files Created:**
- `src/nest/ui/progress.py` — SyncProgress class for Rich progress bar
- `tests/ui/test_progress.py` — Unit tests for SyncProgress
- `tests/integration/test_sync_cli.py` — Integration tests for sync CLI

**Files Modified:**
- `src/nest/core/models.py` — Added SyncResult model
- `src/nest/services/sync_service.py` — Added progress_callback, count tracking, returns SyncResult
- `src/nest/cli/sync_cmd.py` — Project validation, progress integration, enhanced summary
- `tests/cli/test_sync_cmd.py` — Project validation tests
- `tests/services/test_sync_service.py` — SyncResult count tests

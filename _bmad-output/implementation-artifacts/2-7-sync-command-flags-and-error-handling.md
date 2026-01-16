# Story 2.7: Sync Command Flags & Error Handling

Status: ready-for-dev
Branch: feat/2-7-sync-command-flags-and-error-handling

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

**As a** user,
**I want** control over sync behavior,
**So that** I can handle errors and preview changes as needed.

## Acceptance Criteria

### AC1: Default Error Handling (--on-error=skip)
**Given** `--on-error=skip` (default)
**When** a file fails processing
**Then** error is logged, file is skipped, sync continues
**And** exit code is 0 if any files succeeded

### AC2: Fail-Fast Error Handling (--on-error=fail)
**Given** `--on-error=fail`
**When** a file fails processing
**Then** sync aborts immediately
**And** exit code is 1

### AC3: Dry Run Preview (--dry-run)
**Given** `--dry-run` flag
**When** sync runs
**Then** files are analyzed but NOT processed
**And** output shows what WOULD be processed:
- "Would process: 12 new, 3 modified"
- "Would skip: 32 unchanged"
- "Would remove: 2 orphans"

### AC4: Force Reprocessing (--force)
**Given** `--force` flag
**When** sync runs
**Then** all files are re-processed regardless of checksum
**And** manifest checksums are ignored

### AC5: Error Logging
**Given** any errors occur during sync
**When** error logging runs
**Then** errors are appended to `.nest_errors.log` with format:
`2026-01-12T10:30:00 ERROR [sync] file.pdf: Error description`

## Tasks / Subtasks

- [ ] **Task 1: Add Error Logging Infrastructure** (AC: #5)
  - [ ] 1.1 Create `src/nest/ui/logger.py` module
  - [ ] 1.2 Implement `setup_error_logger()` function
    - Creates Python logger instance for error logging
    - Configures file handler for `.nest_errors.log`
    - Uses format: `{timestamp} {level} [{service}] {message}`
    - Appends to existing log (doesn't overwrite)
  - [ ] 1.3 Implement `log_processing_error()` helper
    - Takes: file path, error message, service name
    - Writes formatted entry to error log
  - [ ] 1.4 Add error logger to SyncService
    - Accept logger in constructor (injected from CLI)
    - Log all processing failures

- [ ] **Task 2: Implement OnError Strategy in SyncService** (AC: #1, #2)
  - [ ] 2.1 Add `on_error: Literal["skip", "fail"]` parameter to `SyncService.sync()`
  - [ ] 2.2 Update processing loop in SyncService:
    - If processing fails and `on_error="skip"`: log error, continue to next file
    - If processing fails and `on_error="fail"`: raise exception immediately
  - [ ] 2.3 Update return code logic:
    - If `on_error="skip"` and any files succeeded: return success (exit 0)
    - If `on_error="fail"` and processing fails: raise NestError (exit 1)

- [ ] **Task 3: Implement Dry-Run Mode** (AC: #3)
  - [ ] 3.1 Add `dry_run: bool` parameter to `SyncService.sync()`
  - [ ] 3.2 Update SyncService logic:
    - If `dry_run=True`: perform discovery, checksum comparison, orphan detection
    - Skip: actual processing, file writing, manifest updates
    - Return counts: new/modified/unchanged/orphans
  - [ ] 3.3 Create `DryRunResult` model in `core/models.py`:
    ```python
    class DryRunResult(BaseModel):
        new_count: int
        modified_count: int
        unchanged_count: int
        orphan_count: int
    ```

- [ ] **Task 4: Implement Force Reprocessing** (AC: #4)
  - [ ] 4.1 Add `force: bool` parameter to `SyncService.sync()`
  - [ ] 4.2 Update ChangeDetector logic:
    - If `force=True`: mark ALL files as "modified" (ignore checksums)
    - Skip checksum comparison when force is enabled
  - [ ] 4.3 Ensure manifest is still updated after forced processing

- [ ] **Task 5: Add CLI Flags to sync_cmd.py** (AC: all)
  - [ ] 5.1 Add Typer options to `sync()` command:
    ```python
    @app.command()
    def sync(
        on_error: str = typer.Option("skip", "--on-error", help="..."),
        dry_run: bool = typer.Option(False, "--dry-run", help="..."),
        force: bool = typer.Option(False, "--force", help="..."),
        no_clean: bool = typer.Option(False, "--no-clean", help="..."),  # Already exists from 2-6
    ):
    ```
  - [ ] 5.2 Validate `--on-error` value (must be "skip" or "fail")
  - [ ] 5.3 Pass all flags to SyncService.sync()
  - [ ] 5.4 Setup error logger before creating service
  - [ ] 5.5 Handle exceptions based on `on_error` mode:
    - Skip mode: catch exceptions, show summary, exit 0 if any succeeded
    - Fail mode: let exceptions propagate, exit 1

- [ ] **Task 6: Update CLI Output for New Flags** (AC: #3)
  - [ ] 6.1 Add dry-run output format to `ui/messages.py`:
    ```
    🔍 Dry Run Preview

      Would process: 12 new, 3 modified
      Would skip:    32 unchanged
      Would remove:  2 orphans

      Run without --dry-run to execute.
    ```
  - [ ] 6.2 Update sync summary to show error log location when failures occur:
    ```
    ✓ Sync complete

      Processed: 15 files
      Skipped:   32 unchanged
      Failed:    2 (see .nest_errors.log)
      Orphans:   3 removed
    ```

- [ ] **Task 7: Testing** (AC: all)
  - [ ] 7.1 Unit tests for error logger (`tests/ui/test_logger.py`):
    - Test log file creation
    - Test log format correctness
    - Test log appending (not overwriting)
  - [ ] 7.2 Service tests for `on_error` modes:
    - Test skip mode continues after failure
    - Test fail mode aborts on first failure
    - Test exit codes for both modes
  - [ ] 7.3 Service tests for dry-run:
    - Test no files are actually processed
    - Test counts are accurate
    - Test manifest is not modified
  - [ ] 7.4 Service tests for force mode:
    - Test all files marked as modified
    - Test checksums are ignored
  - [ ] 7.5 Integration test `tests/integration/test_sync_flags.py`:
    - Test full sync with each flag combination
    - Test error logging end-to-end
    - Test CLI output for each mode

## Dev Notes

### Architecture Compliance

**Layer Responsibilities:**
```
cli/sync_cmd.py              → Argument parsing, error logger setup, flag validation
services/sync_service.py     → Orchestration with flag-aware logic
core/change_detector.py      → Modified to support force mode
core/models.py               → Add DryRunResult model
ui/logger.py                 → Error logging infrastructure (NEW)
ui/messages.py               → Dry-run and error summary formatting
```

**Dependency Flow:**
```
CLI Layer
  ↓ (injects logger + flags)
SyncService
  ↓ (checks force flag)
ChangeDetector
  ↓ (returns FileChange results)
ProcessingLoop
  ↓ (logs errors via logger)
ErrorLog (.nest_errors.log)
```

### Existing Infrastructure (DO NOT REINVENT)

**Already Implemented (from Stories 2.1-2.6):**
- `ChangeDetector` with checksum comparison - extend for force mode
- `SyncService.sync()` orchestration - add flags as parameters
- `OrphanService` with `no_clean` flag - reference this pattern
- `ProcessingResult` model - use for error tracking
- Rich console output helpers in `ui/messages.py`

**Pattern from Story 2-6 (no_clean flag):**
```python
# Service layer
def sync(self, ..., no_clean: bool = False):
    # Pass flag to sub-service
    orphan_result = self.orphan_service.cleanup(no_clean=no_clean)

# CLI layer
@app.command()
def sync(no_clean: bool = typer.Option(False, "--no-clean")):
    service.sync(..., no_clean=no_clean)
```

**Apply same pattern for new flags:**
- Add parameters to `SyncService.sync()`
- Pass to relevant sub-components
- CLI validates and passes through

### Critical Implementation Details

**Error Logger Setup:**
```python
# ui/logger.py
import logging
from pathlib import Path
from datetime import datetime

def setup_error_logger(log_file: Path = Path(".nest_errors.log")) -> logging.Logger:
    """Setup file logger for error tracking."""
    logger = logging.getLogger("nest.errors")
    logger.setLevel(logging.ERROR)
    
    handler = logging.FileHandler(log_file, mode='a')
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

def log_processing_error(logger: logging.Logger, file_path: Path, error: str):
    """Log a processing error with standard format."""
    logger.error(f"{file_path.name}: {error}")
```

**OnError Strategy in SyncService:**
```python
def sync(
    self,
    ...,
    on_error: Literal["skip", "fail"] = "skip",
):
    results = []
    for file_change in changes:
        try:
            result = self._process_file(file_change)
            results.append(result)
        except ProcessingError as e:
            if on_error == "fail":
                raise  # Abort immediately
            else:  # skip mode
                # Log error
                self.logger.error(f"{file_change.path.name}: {str(e)}")
                # Add failed result
                results.append(ProcessingResult(
                    source_path=file_change.path,
                    status="failed",
                    error=str(e)
                ))
                continue  # Skip to next file
    
    # Determine exit code
    success_count = sum(1 for r in results if r.status == "success")
    if on_error == "skip" and success_count > 0:
        return results  # Exit 0 (some succeeded)
    elif any(r.status == "failed" for r in results):
        # Exit 1 handled at CLI layer
        pass
```

**Dry-Run Implementation:**
```python
def sync(self, ..., dry_run: bool = False):
    # Always do discovery and change detection
    all_files = self.discovery_service.discover(raw_dir)
    changes = self.change_detector.detect_changes(all_files, manifest)
    
    if dry_run:
        # Count what WOULD happen
        new = sum(1 for c in changes if c.change_type == "new")
        modified = sum(1 for c in changes if c.change_type == "modified")
        unchanged = sum(1 for c in changes if c.change_type == "unchanged")
        
        # Detect orphans but don't remove
        orphans = self.orphan_service.detect_orphans(...)
        
        return DryRunResult(
            new_count=new,
            modified_count=modified,
            unchanged_count=unchanged,
            orphan_count=len(orphans)
        )
    
    # Normal processing...
```

**Force Mode in ChangeDetector:**
```python
def detect_changes(
    self,
    files: list[Path],
    manifest: Manifest,
    force: bool = False
) -> list[FileChange]:
    changes = []
    for file_path in files:
        if force:
            # Treat all files as modified
            changes.append(FileChange(
                path=file_path,
                change_type="modified",
                reason="force reprocessing"
            ))
            continue
        
        # Normal checksum comparison...
```

### Previous Story Intelligence (2-6)

From Story 2-6 implementation:
- `OrphanService` accepts `no_clean` flag for conditional cleanup
- `SyncService` passes flag through to sub-services
- CLI validates flag and injects into service
- Pattern works well - reuse for `on_error`, `dry_run`, `force`

**Key Learning:** Keep flag logic in service layer, not CLI. CLI should only parse and validate, then pass to service.

### Git Intelligence

Recent commits show pattern:
```
feat(sync): add orphan cleanup for stale processed files
feat(sync): implement master index generation and SyncService
feat(sync): implement manifest tracking and updates
```

**Pattern to follow:**
- Commit message: `feat(sync): add command flags and error handling`
- Branch: `feat/2-7-sync-command-flags-and-error-handling`
- Keep commits atomic: one commit per task or logical unit
- Run CI scripts before each commit

### Testing Patterns

**Mock Logger Pattern:**
```python
@pytest.fixture
def mock_logger():
    class MockLogger:
        def __init__(self):
            self.errors: list[str] = []
        
        def error(self, msg: str):
            self.errors.append(msg)
    
    return MockLogger()

def test_skip_mode_logs_errors(mock_logger):
    service = SyncService(..., logger=mock_logger)
    service.sync(..., on_error="skip")
    assert len(mock_logger.errors) > 0
```

**Integration Test Pattern (from 2-6):**
```python
def test_sync_with_dry_run(tmp_path):
    # Setup files
    raw_dir = tmp_path / "raw_inbox"
    new_file = raw_dir / "new.pdf"
    new_file.write_bytes(b"content")
    
    # Run with dry-run
    result = sync_service.sync(raw_dir, dry_run=True)
    
    # Assert nothing was processed
    assert result.new_count == 1
    assert not (tmp_path / "processed_context" / "new.md").exists()
```

### Edge Cases to Handle

1. **Empty project with dry-run** - Should show "0 files to process"
2. **Force mode with no files** - Should handle gracefully
3. **Invalid --on-error value** - CLI should reject (not "skip" or "fail")
4. **Conflicting flags** - Document behavior (e.g., `--force --dry-run`)
5. **Error log permissions** - Handle read-only filesystem gracefully
6. **Multiple errors in skip mode** - All should be logged, summary should show count
7. **Fail mode on first file** - Should abort immediately, not process remaining

### Project Structure Notes

**New Files:**
- `src/nest/ui/logger.py` - Error logging setup and helpers
- `tests/ui/test_logger.py` - Logger unit tests
- `tests/integration/test_sync_flags.py` - End-to-end flag tests

**Modified Files:**
- `src/nest/cli/sync_cmd.py` - Add CLI flags (--on-error, --dry-run, --force)
- `src/nest/services/sync_service.py` - Add flag parameters, implement strategies
- `src/nest/core/change_detector.py` - Add force mode support
- `src/nest/core/models.py` - Add DryRunResult model
- `src/nest/ui/messages.py` - Add dry-run and error summary formats

### References

**From Epics:**
- [Story 2.7: Sync Command Flags & Error Handling](epics.md#story-27-sync-command-flags--error-handling)
- Acceptance criteria defined in Epic 2

**From PRD:**
- [FR12](prd.md): `nest sync` supports `--on-error` flag (skip | fail)
- [FR13](prd.md): `nest sync` supports `--dry-run` flag
- [FR14](prd.md): `nest sync` supports `--force` flag
- [NFR3](prd.md): Error logging to `.nest_errors.log` with configurable fail modes

**From Architecture:**
- [Error Handling](architecture.md#error-handling): Custom exception hierarchy
- [CLI Output Patterns](architecture.md#cli-output-patterns): Two output streams (console + log)
- [Testing Rules](architecture.md#testing-rules): Structure and naming conventions
- [Project Structure](architecture.md#project-structure): Layer responsibilities

**From Project Context:**
- [Python Language Rules](project-context.md#python-language-rules): Type hints, import order
- [Error Handling](project-context.md#error-handling): NestError, ProcessingError exceptions
- [CLI Output Patterns](project-context.md#cli-output-patterns): Rich helpers, message formatting
- [Testing Rules](project-context.md#testing-rules): Arrange-Act-Assert, file naming

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (via GitHub Copilot)

### Debug Log References

N/A

### Completion Notes List

_To be filled by Dev agent during implementation_

### File List

_To be filled by Dev agent after implementation_

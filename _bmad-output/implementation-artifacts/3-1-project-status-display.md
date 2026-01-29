# Story 3.1: Project Status Display

Status: ready-for-dev
Branch: feat/3-1-project-status-display

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user managing my knowledge base**,
I want **to quickly see the state of my project**,
so that **I know what needs attention before running sync**.

## Business Context

This is the first story in Epic 3 (Project Visibility & Health), which focuses on giving users insight into their Nest project state. The `nest status` command provides a quick at-a-glance summary that helps users understand:

1. How many files are pending processing (new/modified)
2. How many orphaned files exist (source deleted)
3. When the last sync occurred
4. Whether sync needs to be run

This reduces friction by eliminating the need to run `nest sync --dry-run` just to see project state.

**Functional Requirements Covered:** FR18

## Acceptance Criteria

### AC1: Basic Status Display

**Given** I run `nest status` in a Nest project with pending work
**When** the command executes
**Then** output displays formatted status including:
- Project name from manifest
- Nest version
- Source folder file counts (total, new, modified, unchanged)
- Context folder file counts (files, orphaned)
- Last sync timestamp (relative time)
- Actionable next step message

### AC2: All Files Up to Date

**Given** no files need processing (all checksums match, no orphans)
**When** `nest status` displays
**Then** message shows: "✓ All files up to date"
**And** no "Run `nest sync`" prompt is shown

### AC3: Relative Time Display

**Given** manifest has `last_sync` timestamp
**When** status displays
**Then** relative time is shown (e.g., "2 hours ago", "3 days ago", "never")

### AC4: No Project Error

**Given** `nest status` runs outside a Nest project (no `.nest_manifest.json`)
**When** command executes
**Then** error displays: "No Nest project found. Run `nest init` first."
**And** exit code is 1

### AC5: Reuses Checksum Logic

**Given** StatusService computes file states
**When** comparing source files to manifest
**Then** it reuses checksum logic from `core/checksum.py`
**And** compares against manifest entries using same algorithm as sync

## E2E Testing Requirements

- [ ] Existing E2E tests cover this story's functionality: No - status command is new
- [ ] New E2E tests required: Yes - add E2E tests for status command
- [ ] E2E test execution required for story completion: Yes

**New E2E Tests Needed:**
1. `test_status_shows_pending_files()` - Status shows correct counts after adding files
2. `test_status_after_sync_shows_up_to_date()` - Status shows all up to date after sync
3. `test_status_outside_project_fails()` - Status fails gracefully outside Nest project

## Tasks / Subtasks

### Task 1: Create StatusService (AC: 1, 5)
- [ ] 1.1: Create `src/nest/services/status_service.py`
  - Inject `FileSystemProtocol` and `ManifestProtocol`
  - Reuse `core/checksum.py` for file state comparison
- [ ] 1.2: Implement `get_status()` method returning `StatusReport` dataclass
- [ ] 1.3: Create `StatusReport` dataclass with all required fields:
  ```python
  @dataclass
  class StatusReport:
      project_name: str
      nest_version: str
      source_total: int
      source_new: int
      source_modified: int
      source_unchanged: int
      context_files: int
      context_orphaned: int
      last_sync: datetime | None
      pending_count: int  # new + modified
  ```

### Task 2: Implement File State Analysis (AC: 1, 5)
- [ ] 2.1: Create `analyze_source_files()` method in StatusService
  - Scan `_nest_sources/` for supported files
  - Compare checksums against manifest
  - Categorize as new/modified/unchanged
- [ ] 2.2: Create `analyze_context_files()` method
  - Count files in `_nest_context/`
  - Identify orphaned files (in manifest but source missing)
- [ ] 2.3: Ensure consistent use of `SUPPORTED_EXTENSIONS` from `core/paths.py`

### Task 3: Create Status CLI Command (AC: 1, 4)
- [ ] 3.1: Create `src/nest/cli/status_cmd.py`
  - Register `status` command with Typer app
  - Implement composition root (inject dependencies)
  - Handle "no project" error case
- [ ] 3.2: Add `status` command to `cli/main.py` app registration

### Task 4: Implement Rich Output Formatting (AC: 1, 2, 3)
- [ ] 4.1: Create `src/nest/ui/status_display.py` for Rich formatting
  - Tree-structured output with Rich Tree or nested formatting
  - Color-coded counts (green=✓, yellow=pending, red=errors)
- [ ] 4.2: Implement relative time formatting helper
  - "just now", "X minutes ago", "X hours ago", "X days ago", "never"
- [ ] 4.3: Implement "All up to date" message when nothing pending
- [ ] 4.4: Implement actionable prompt: "Run `nest sync` to process N pending files"

### Task 5: Add Unit Tests (AC: all)
- [ ] 5.1: Create `tests/services/test_status_service.py`
  - Test file state categorization (new/modified/unchanged)
  - Test orphan detection
  - Test with empty project
  - Test with fully synced project
- [ ] 5.2: Create `tests/cli/test_status_cmd.py`
  - Test successful status display
  - Test "no project" error handling
- [ ] 5.3: Create `tests/ui/test_status_display.py`
  - Test relative time formatting
  - Test output formatting

### Task 6: Add E2E Tests (AC: all)
- [ ] 6.1: Add `test_status_shows_pending_files()` to `tests/e2e/test_status_e2e.py`
- [ ] 6.2: Add `test_status_after_sync_shows_up_to_date()`
- [ ] 6.3: Add `test_status_outside_project_fails()`

### Task 7: Run Full Test Suite
- [ ] 7.1: Run `pytest -m "not e2e"` - all unit/integration tests pass
- [ ] 7.2: Run `pytest -m "e2e"` - all E2E tests pass
- [ ] 7.3: Run `ruff check` - no linting errors
- [ ] 7.4: Run `pyright` - no type errors

## Dev Notes

### Architecture Compliance

**Layer Structure:**
- `cli/status_cmd.py` → Argument parsing, composition root
- `services/status_service.py` → Orchestration, calls core + adapters
- `core/checksum.py` → Reuse existing checksum logic (NO new code)
- `adapters/` → Reuse existing `FileSystemAdapter`, `ManifestAdapter`
- `ui/status_display.py` → Rich formatted output

**Protocol-Based DI:**
```python
class StatusService:
    def __init__(
        self,
        filesystem: FileSystemProtocol,
        manifest: ManifestProtocol,
    ):
        self._filesystem = filesystem
        self._manifest = manifest
```

**Composition Root (cli/status_cmd.py):**
```python
def create_status_service() -> StatusService:
    return StatusService(
        filesystem=FileSystemAdapter(),
        manifest=ManifestAdapter(),
    )
```

### Output Format Reference

Expected output format (from epics.md):
```
📁 Project: Nike
   Nest Version: 1.0.0

   Raw Inbox:
   ├─ Total files:    47
   ├─ New:            12  (not yet processed)
   ├─ Modified:        3  (source changed since last sync)
   └─ Unchanged:      32

   Processed Context:
   ├─ Files:          32
   ├─ Orphaned:        2  (source deleted, run sync to remove)
   └─ Last sync:       2 hours ago

   Run `nest sync` to process 15 pending files.
```

**Note:** Update folder names in output to use new naming convention:
- "Raw Inbox" → "Sources" (folder: `_nest_sources/`)
- "Processed Context" → "Context" (folder: `_nest_context/`)

### Relative Time Formatting

Implement helper function for human-readable relative times:
```python
def format_relative_time(dt: datetime | None) -> str:
    """Format datetime as relative time string."""
    if dt is None:
        return "never"
    
    delta = datetime.now(timezone.utc) - dt
    seconds = delta.total_seconds()
    
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(seconds // 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
```

### Reusing Existing Code

**Checksum Logic:** Reuse `core/checksum.py` `compute_sha256()` function
**File Discovery:** Leverage patterns from `services/discovery_service.py`
**Orphan Detection:** Reuse logic from `core/orphan_detector.py` (manifest-aware version from Story 2.10)
**Path Constants:** Use `core/paths.py` for `SOURCES_DIR`, `CONTEXT_DIR`, `SUPPORTED_EXTENSIONS`

### File Impact Summary

| Category | Files | Notes |
|----------|-------|-------|
| New source files | 3 | `status_cmd.py`, `status_service.py`, `status_display.py` |
| Modified source files | 1 | `cli/main.py` (add status command) |
| New test files | 3 | `test_status_service.py`, `test_status_cmd.py`, `test_status_e2e.py` |
| **Total new files** | **6** | Minimal footprint |

### Previous Story Learnings

From Story 2.10 (Folder Naming Refactor):
- Use constants from `core/paths.py` for all folder names
- Orphan detection is now manifest-aware (only manifest-tracked files can be orphans)
- User-curated files in `_nest_context/` are NOT counted as orphans

From Story 2.8 (Sync CLI Integration):
- Follow same Rich output patterns (spinners, checkmarks, tree structure)
- Use `ui/messages.py` helpers for consistent formatting
- Exit code 1 for errors, exit code 0 for success

### Project Structure Notes

Alignment with unified project structure:
- Follows layered architecture: `cli/` → `services/` → `core/` + `adapters/`
- Uses dependency injection via protocols
- All paths use `pathlib.Path`
- Rich console for user-facing output, never `print()`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.1: Project Status Display]
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure]
- [Source: _bmad-output/project-context.md#Architecture & Dependency Injection]
- [Source: src/nest/core/paths.py] - Path constants
- [Source: src/nest/core/checksum.py] - Checksum computation
- [Source: src/nest/core/orphan_detector.py] - Orphan detection logic

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

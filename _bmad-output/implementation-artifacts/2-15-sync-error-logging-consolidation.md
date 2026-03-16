# Story 2.15: Sync Pipeline Error Logging Consolidation

Status: done
Branch: fix/2-15-sync-error-logging-consolidation

## Story

As a **Nest user running sync on Windows with non-ASCII filenames**,
I want **error logging to work reliably without crashing**,
So that **when document processing fails, I get a clear error message and the sync pipeline continues gracefully**.

## Business Context

### The Problem

A Windows user running `nest sync` with Danish-named files hit a logging crash:

```
ValueError: Formatting field not found in record: 'context'
```

**Root Cause:** Two competing error logging implementations exist in the codebase:
1. **Legacy** `src/nest/core/logging.py` — creates logger `"nest.errors"` with `%(context)s` format field
2. **Current** `src/nest/ui/logger.py` — creates child logger `"nest.errors.sync.<id>"` with `%(service)s` format field

When `DoclingProcessor` (the only remaining consumer of the legacy module) fails and calls the old `log_processing_error`, it creates the `"nest.errors"` parent logger with a `%(context)s` formatter. Then `SyncService` logs the same failure via the new `ui/logger.py` through the child logger. Python's logging propagation sends the record up to the parent, which tries to format with `%(context)s` — a field not present — causing the crash.

**Additionally:**
- `doctor_service.py` directly references `logging.getLogger("nest.errors")` with no handler setup, creating another latent collision point
- The collision resolution in `_resolve_collisions()` drops same-type collisions (e.g., `.docx` + `.pdf` → same `.md`) from the output map without tracking them in the manifest

**Impact:**
- Windows users with file processing errors see a cryptic Python traceback instead of a clean error message
- Same-type collisions (rare but possible) result in untracked files in the manifest
- The dead `core/logging.py` module creates ongoing maintenance confusion about which logging API to use

### Reproduction Case

```
User has:
  _nest_sources/
    2 - Bilag 1.1 Løsningsbeskrivelse - trimmed.docx
    2 - Bilag 1.1 Løsningsbeskrivelse - trimmed.pdf

1. Both files collide → .docx is dropped, .pdf is kept (collision warning logged)
2. Docling fails to process the .pdf (Windows-specific backend issue)
3. DoclingProcessor catches exception → calls legacy core.logging.log_processing_error()
   → creates "nest.errors" logger with %(context)s formatter
4. SyncService sees status="failed" → calls new ui.logger.log_processing_error()
   → logs via child "nest.errors.sync.<id>" logger
5. Python propagates record to parent "nest.errors" → %(context)s not found → CRASH
```

## Acceptance Criteria

### AC1: Remove Legacy Error Logging Module

**Given** the legacy module `src/nest/core/logging.py`
**When** error logging consolidation is applied
**Then** `src/nest/core/logging.py` is deleted
**And** `tests/core/test_logging.py` is deleted
**And** no code in the project imports from `nest.core.logging`

### AC2: DoclingProcessor Stops Doing Its Own Error Logging

**Given** `DoclingProcessor.process()` in `src/nest/adapters/docling_processor.py`
**When** a document fails to convert
**Then** the error is returned in `ProcessingResult(status="failed", error=error_msg)`
**And** `DoclingProcessor` does NOT import or call any logging module
**And** `DoclingProcessor` does NOT accept or store an `error_log` path
**And** the calling service (`SyncService`) is solely responsible for error logging

**Rationale:** Adapters return results; services orchestrate and log. This follows the project's layered architecture where adapters never do I/O beyond their primary concern.

### AC3: DoctorService Uses Standard Module Logger

**Given** `src/nest/services/doctor_service.py` line 25
**When** it needs a logger for diagnostic output
**Then** it uses `logging.getLogger(__name__)` (standard Python pattern)
**And** it does NOT use `logging.getLogger("nest.errors")` (the legacy hardcoded name)
**And** the `"nest.errors"` logger namespace is no longer referenced anywhere in the codebase

### AC4: Same-Type Collision Tracking in Manifest

**Given** two Docling-convertible files that produce the same output path
  (e.g., `report.docx` and `report.pdf` both → `report.md`)
**When** `_resolve_collisions()` resolves the collision
**Then** the displaced file is appended to `collision_skipped` list
**And** it is recorded in the manifest via `record_skipped()` with a descriptive reason
**And** a warning is logged identifying both files and which one was kept

### AC5: Error Logging Works End-to-End on Processing Failures

**Given** a file that fails Docling processing
**When** `SyncService.sync()` runs with `on_error="skip"` (default)
**Then** the error is written to `.nest/errors.log` via `ui/logger.py`
**And** the log format is: `{timestamp} ERROR [sync] {filename}: {error_message}`
**And** no Python traceback or `ValueError` occurs in the log output
**And** sync continues processing remaining files

### AC6: All Existing Tests Pass

**Given** the consolidated logging module
**When** the full test suite runs (`pytest`)
**Then** all unit tests pass
**And** all integration tests pass
**And** all E2E tests pass
**And** the only test file removed is `tests/core/test_logging.py`

## Tasks / Subtasks

### Task 1: Remove Legacy Logging Module & Migrate DoclingProcessor (AC1, AC2)

- [x] 1.1: Delete `src/nest/core/logging.py`
- [x] 1.2: Delete `tests/core/test_logging.py`
- [x] 1.3: Update `src/nest/adapters/docling_processor.py`:
  - Remove `from nest.core.logging import log_processing_error` import
  - Remove `error_log` parameter from `__init__()` and stored `self._error_log`
  - Remove `DEFAULT_ERROR_LOG` class constant
  - Remove `log_processing_error()` call from `except` block in `process()`
  - Keep the `ProcessingResult(status="failed", error=error_msg)` return — this is how the adapter communicates errors to the orchestrator
- [x] 1.4: Update `src/nest/cli/sync_cmd.py` (or wherever `DoclingProcessor` is instantiated):
  - Remove `error_log=...` kwarg from `DoclingProcessor()` constructor call
- [x] 1.5: Update any tests in `tests/adapters/test_docling_processor.py` that reference `error_log` parameter

### Task 2: Fix DoctorService Logger Reference (AC3)

- [x] 2.1: In `src/nest/services/doctor_service.py` line 25, change:
  ```python
  # Before:
  logger = logging.getLogger("nest.errors")
  # After:
  logger = logging.getLogger(__name__)
  ```
- [x] 2.2: Verify no other files reference `logging.getLogger("nest.errors")`

### Task 3: Fix Same-Type Collision Tracking (AC4)

- [x] 3.1: In `src/nest/services/sync_service.py`, update the `else` branch in `_resolve_collisions()` (the "Both same type" case):
  ```python
  # Before:
  else:
      existing_file, _ = output_map[output_key]
      logger.warning(
          "Output path collision: %s and %s both produce %s — keeping %s",
          existing_file.path.name,
          file_info.path.name,
          output_key,
          file_info.path.name,
      )
      output_map[output_key] = (file_info, is_pt)

  # After:
  else:
      existing_file, _ = output_map[output_key]
      reason = (
          f"Output path collision: {existing_file.path.name} and "
          f"{file_info.path.name} both produce {output_key} "
          f"— keeping {file_info.path.name}"
      )
      logger.warning(reason)
      existing_file.collision_reason = reason
      collision_skipped.append(existing_file)
      output_map[output_key] = (file_info, is_pt)
  ```
- [x] 3.2: Add test in `tests/services/test_sync_service.py` for same-type collision tracking

### Task 4: Verification Testing (AC5, AC6)

- [x] 4.1: Run full test suite to confirm no regressions: `pytest`
- [x] 4.2: Run linting: `ruff check src/ tests/`
- [x] 4.3: Run type checking: `pyright`
- [x] 4.4: Verify error logging integration test still passes in `tests/integration/test_sync_flags.py`
- [x] 4.5: Verify no remaining references to `nest.core.logging` in codebase

## Dev Notes

### Architecture Compliance

This story enforces the project's established layered architecture:

```
cli/          → Composition root, creates error logger, passes to services
services/     → SyncService orchestrates and logs errors via injected logger
adapters/     → DoclingProcessor returns ProcessingResult, NEVER logs directly
core/         → Pure business logic, no logging infrastructure
ui/           → logger.py provides the SINGLE error logging API
```

**Key principle:** Adapters return results; services orchestrate and log. The `DoclingProcessor` was violating this by importing `core/logging.py` and logging directly.

### Files to Modify

| File | Action |
|------|--------|
| `src/nest/core/logging.py` | DELETE |
| `tests/core/test_logging.py` | DELETE |
| `src/nest/adapters/docling_processor.py` | Remove logging import, error_log param, logging call |
| `src/nest/cli/sync_cmd.py` | Remove error_log kwarg from DoclingProcessor constructor |
| `src/nest/services/doctor_service.py` | Change logger from `"nest.errors"` to `__name__` |
| `src/nest/services/sync_service.py` | Fix same-type collision tracking in `_resolve_collisions()` |
| `tests/adapters/test_docling_processor.py` | Update tests removing error_log references |
| `tests/services/test_sync_service.py` | Add same-type collision tracking test |

### What This Does NOT Address

- **Docling PDF backend issue on Windows:** The `"Inconsistent number of pages: 14!=-1"` and `"Input document ... is not valid"` errors are Docling-internal issues on Windows. This is an upstream dependency problem, not a Nest bug. Nest's responsibility is to handle the failure gracefully (which this story ensures).
- **Output path collision policy change:** The current "last one wins" policy for same-type collisions is maintained. A future story could add user-configurable collision strategies if needed.

### References

- [Source: src/nest/core/logging.py] — Legacy module to be removed
- [Source: src/nest/ui/logger.py] — Canonical error logging module (kept as-is)
- [Source: src/nest/adapters/docling_processor.py] — Adapter violating layered architecture
- [Source: src/nest/services/sync_service.py#_resolve_collisions] — Collision tracking gap
- [Source: src/nest/services/doctor_service.py#L25] — Hardcoded legacy logger name
- [Source: _bmad-output/project-context.md#Architecture & Dependency Injection] — Architecture rules
- [Source: _bmad-output/implementation-artifacts/2-2-docling-document-processing.md] — Original story that created core/logging.py
- [Source: _bmad-output/implementation-artifacts/2-7-sync-command-flags-and-error-handling.md] — Story that created ui/logger.py

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
No debug issues encountered.

### Completion Notes List
- **Task 1 (AC1, AC2):** Deleted legacy `src/nest/core/logging.py` and `tests/core/test_logging.py`. Removed all legacy logging from `DoclingProcessor` — import, `DEFAULT_ERROR_LOG`, `error_log` param, and `log_processing_error()` call. Adapter now purely returns `ProcessingResult` without side-effect logging. `sync_cmd.py` already instantiated `DoclingProcessor()` without `error_log` kwarg. Replaced `TestDoclingProcessorErrorLogging` test class with `TestDoclingProcessorErrorHandling` that verifies adapter returns failed result without logging.
- **Task 2 (AC3):** Changed `doctor_service.py` logger from `logging.getLogger("nest.errors")` to `logging.getLogger(__name__)`. Verified no other production code references `"nest.errors"` logger name.
- **Task 3 (AC4):** Fixed `_resolve_collisions()` same-type collision branch to track displaced file in `collision_skipped` list with `collision_reason` and warning. Added `test_same_type_collision_tracks_skipped_file` test.
- **Task 4 (AC5, AC6):** Full suite: 851 passed, 6 skipped, 0 failures. Linting: all checks passed. Pyright: 0 errors. No `nest.core.logging` references in production code.
- **Review remediation (2026-03-16):** Fixed the remaining consolidation gaps found in code review. `ui/logger.py` no longer creates loggers under the legacy `nest.errors` namespace and now disables propagation so sync error records cannot bubble into parent handlers with incompatible formatters. `DoclingProcessor` no longer performs any adapter-side debug logging in its failure path and now only returns `ProcessingResult(status="failed")`. Added regression coverage for logger namespace/propagation and for the adapter not importing or using logging.
- **Post-remediation validation:** Targeted regression suite passed (`tests/ui/test_logger.py`, `tests/adapters/test_docling_processor.py`, `tests/integration/test_sync_flags.py`: 35 passed). Full non-E2E suite passed: 819 passed, 57 deselected.

### Change Log
- Removed legacy error logging module and consolidated to single `ui/logger.py` API (Date: 2026-03-12)
- Fixed same-type collision tracking in `_resolve_collisions()` (Date: 2026-03-12)
- Fixed `doctor_service.py` hardcoded logger name (Date: 2026-03-12)
- Fixed logger namespace propagation and removed residual adapter-side logging after code review (Date: 2026-03-16)

### File List
- `src/nest/core/logging.py` — DELETED
- `tests/core/test_logging.py` — DELETED
- `src/nest/adapters/docling_processor.py` — Modified (removed legacy logging)
- `src/nest/services/doctor_service.py` — Modified (fixed logger name)
- `src/nest/services/sync_service.py` — Modified (same-type collision tracking)
- `src/nest/ui/logger.py` — Modified (moved off legacy logger namespace, disabled propagation)
- `tests/adapters/test_docling_processor.py` — Modified (replaced error logging tests)
- `tests/services/test_sync_service.py` — Modified (added same-type collision test)
- `tests/ui/test_logger.py` — Modified (added logger namespace/propagation regression tests)

# Story 2.4: Manifest Tracking & Updates

Status: review
Branch: feat/2-4-manifest-tracking-updates

---

## Story

**As a** user,
**I want** the system to remember what was processed,
**So that** subsequent syncs are fast and only process changes.

---

## Acceptance Criteria

### AC1: Successful File Entry Creation
**Given** a file is successfully processed
**When** manifest is updated
**Then** entry includes:
- `sha256`: file checksum
- `processed_at`: ISO timestamp
- `output`: relative path to processed file
- `status`: "success"

### AC2: Failed File Entry Creation
**Given** a file fails processing
**When** manifest is updated
**Then** entry includes:
- `status`: "failed"
- `error`: error description message

### AC3: Sync Completion Updates
**Given** sync completes
**When** manifest is saved
**Then** `last_sync` timestamp is updated
**And** `nest_version` reflects current version

### AC4: Corrupt Manifest Handling
**Given** manifest file is corrupt or invalid JSON
**When** sync attempts to load it
**Then** a `ManifestError` is raised
**And** user is advised to run `nest doctor`

---

## Tasks / Subtasks

- [x] **Task 1: Create ManifestService for Orchestration** (AC: #1, #2, #3)
  - [x] 1.1 Create `src/nest/services/manifest_service.py`
  - [x] 1.2 Implement `ManifestService` class with constructor:
    ```python
    def __init__(
        self,
        manifest: ManifestProtocol,
        project_root: Path,
    ):
    ```
  - [x] 1.3 Implement `record_success(source_path: Path, checksum: str, output_path: Path) -> FileEntry`:
    - Create FileEntry with status="success"
    - Set processed_at to current UTC timestamp
    - Compute relative output path for portability
  - [x] 1.4 Implement `record_failure(source_path: Path, checksum: str, error: str) -> FileEntry`:
    - Create FileEntry with status="failed"
    - Include error message in entry
    - Set output to empty string (no output file created)
  - [x] 1.5 Implement `commit() -> None` (renamed from update_manifest for clarity):
    - Merge pending entries into existing manifest.files
    - Update last_sync timestamp
    - Update nest_version to current version
    - Call manifest.save()

- [x] **Task 2: Extend ManifestProtocol for Update Operations** (AC: #1, #2, #3)
  - [x] 2.1 Verify `ManifestProtocol.save()` accepts complete Manifest with modified files dict
  - [x] 2.2 Confirm `Manifest.files` dict uses relative source paths as keys (not absolute)
  - [x] 2.3 Document expected key format: `contracts/2024/alpha.pdf` (forward slashes, relative to raw_inbox)

- [x] **Task 3: Implement ManifestError Exception** (AC: #4)
  - [x] 3.1 Verify `ManifestError` exists in `src/nest/core/exceptions.py`
  - [x] 3.2 Already present — no action needed
  - [x] 3.3 Update `ManifestAdapter.load()` to catch `json.JSONDecodeError` and re-raise as `ManifestError`
  - [x] 3.4 Update `ManifestAdapter.load()` to catch Pydantic `ValidationError` and re-raise as `ManifestError`
  - [x] 3.5 Include actionable message: "Manifest file is corrupt. Run `nest doctor` to repair."

- [x] **Task 4: Add Path-to-Key Conversion Utility** (AC: #1, #2)
  - [x] 4.1 Add function to `core/paths.py`:
    ```python
    def source_path_to_manifest_key(source: Path, raw_inbox: Path) -> str:
        """Convert absolute source path to manifest key (portable relative path).
        
        Args:
            source: Absolute path to source file.
            raw_inbox: Absolute path to raw_inbox directory.
            
        Returns:
            Forward-slash separated relative path string.
        
        Example:
            source = Path("/project/raw_inbox/contracts/2024/alpha.pdf")
            raw_inbox = Path("/project/raw_inbox")
            Result: "contracts/2024/alpha.pdf"
        """
    ```
  - [x] 4.2 Use `relative_to_project()` pattern from Story 2.3
  - [x] 4.3 Ensure forward slashes for cross-platform compatibility (`.as_posix()`)

- [x] **Task 5: Comprehensive Testing** (AC: all)
  - [x] 5.1 Create `tests/services/test_manifest_service.py`:
    - Test `record_success()` creates correct FileEntry
    - Test `record_failure()` includes error message
    - Test `commit()` merges entries correctly
    - Test `commit()` sets last_sync timestamp
    - Test `commit()` updates nest_version
  - [x] 5.2 Create `tests/adapters/test_manifest.py`:
    - Test `load()` raises ManifestError on invalid JSON
    - Test `load()` raises ManifestError on Pydantic validation failure
    - Test error message includes "nest doctor" guidance
  - [x] 5.3 Add tests to `tests/core/test_paths.py`:
    - Test `source_path_to_manifest_key()` returns forward-slash path
    - Test with nested subdirectories
    - Test with file at raw_inbox root level
  - [x] 5.4 Integration test `tests/integration/test_manifest_integration.py`:
    - Process file → check manifest updated
    - Fail processing → check manifest records failure
    - Re-process → check manifest entry updated (not duplicated)

---

## Dev Notes

### Architecture Compliance

**Layer Responsibilities:**
```
core/paths.py                  → Pure path-to-key conversion (no I/O)
core/exceptions.py             → ManifestError exception class
adapters/protocols.py          → ManifestProtocol (already defined)
adapters/manifest.py           → ManifestAdapter with error handling
services/manifest_service.py   → ManifestService orchestration (NEW)
```

**Dependency Flow:**
```
SyncService → ManifestService → [ManifestProtocol]
                                       ↓
                               ManifestAdapter → .nest_manifest.json
```

### Existing Infrastructure (DO NOT REINVENT)

**Already Implemented:**
- `ManifestAdapter` in [adapters/manifest.py](src/nest/adapters/manifest.py) - has `exists()`, `create()`, `load()`, `save()`
- `Manifest` model in [core/models.py](src/nest/core/models.py) - with `files: dict[str, FileEntry]`
- `FileEntry` model in [core/models.py](src/nest/core/models.py) - has all required fields
- `relative_to_project()` in [core/paths.py](src/nest/core/paths.py) - returns portable paths

**Key Pattern from Story 2.3:**
```python
# From core/paths.py - reuse this pattern
def relative_to_project(path: Path, project_root: Path) -> str:
    relative = path.relative_to(project_root)
    return relative.as_posix()  # Forward slashes for portability
```

### Critical Implementation Details

**Manifest Key Format:**
- Keys are relative paths from raw_inbox root
- Use forward slashes for cross-platform compatibility
- Example: `contracts/2024/alpha.pdf`

**FileEntry Structure (already defined in core/models.py):**
```python
class FileEntry(BaseModel):
    sha256: str
    processed_at: datetime
    output: str  # Relative path to output, e.g., "contracts/2024/alpha.md"
    status: Literal["success", "failed", "skipped"]
    error: str | None = None
```

**ManifestService Pattern:**
```python
# services/manifest_service.py
from datetime import datetime, timezone
from pathlib import Path

from nest import __version__
from nest.adapters.protocols import ManifestProtocol
from nest.core.models import FileEntry
from nest.core.paths import source_path_to_manifest_key


class ManifestService:
    """Orchestrates manifest tracking and updates during sync."""

    def __init__(
        self,
        manifest: ManifestProtocol,
        project_root: Path,
        raw_inbox_name: str = "raw_inbox",
        output_dir_name: str = "processed_context",
    ):
        self._manifest_adapter = manifest
        self._project_root = project_root
        self._raw_inbox = project_root / raw_inbox_name
        self._output_dir = project_root / output_dir_name
        self._pending_entries: dict[str, FileEntry] = {}

    def record_success(
        self,
        source_path: Path,
        checksum: str,
        output_path: Path,
    ) -> FileEntry:
        """Record a successfully processed file."""
        key = source_path_to_manifest_key(source_path, self._raw_inbox)
        output_relative = output_path.relative_to(self._output_dir).as_posix()
        
        entry = FileEntry(
            sha256=checksum,
            processed_at=datetime.now(timezone.utc),
            output=output_relative,
            status="success",
        )
        self._pending_entries[key] = entry
        return entry

    def record_failure(
        self,
        source_path: Path,
        checksum: str,
        error: str,
    ) -> FileEntry:
        """Record a failed processing attempt."""
        key = source_path_to_manifest_key(source_path, self._raw_inbox)
        
        entry = FileEntry(
            sha256=checksum,
            processed_at=datetime.now(timezone.utc),
            output="",  # No output for failures
            status="failed",
            error=error,
        )
        self._pending_entries[key] = entry
        return entry

    def commit(self) -> None:
        """Write all pending entries to manifest."""
        manifest = self._manifest_adapter.load(self._project_root)
        
        # Merge pending entries
        manifest.files.update(self._pending_entries)
        
        # Update metadata
        manifest.last_sync = datetime.now(timezone.utc)
        manifest.nest_version = __version__
        
        self._manifest_adapter.save(self._project_root, manifest)
        self._pending_entries.clear()
```

**ManifestError Exception:**
```python
# core/exceptions.py
class ManifestError(NestError):
    """Raised when manifest file is invalid or corrupt."""
    pass
```

**Enhanced ManifestAdapter.load():**
```python
# adapters/manifest.py additions
import json
from pydantic import ValidationError
from nest.core.exceptions import ManifestError

def load(self, project_dir: Path) -> Manifest:
    manifest_path = project_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    try:
        content = manifest_path.read_text()
        data = json.loads(content)
        return Manifest.model_validate(data)
    except json.JSONDecodeError as e:
        raise ManifestError(
            f"Manifest file is corrupt (invalid JSON). "
            f"Run `nest doctor` to repair. Details: {e}"
        ) from e
    except ValidationError as e:
        raise ManifestError(
            f"Manifest file is corrupt (invalid structure). "
            f"Run `nest doctor` to repair. Details: {e}"
        ) from e
```

### Previous Story Intelligence

**From Story 2.3 (Output Mirroring):**
- `core/paths.py` has `relative_to_project()` - reuse this pattern for manifest keys
- `core/paths.py` has `mirror_path()` - the output path computation is already handled
- Use `.as_posix()` for all stored paths (cross-platform compatibility)

**From Story 2.2 (Docling Processing):**
- `ProcessingResult` has `source_path`, `status`, `output_path`, `error` - perfect for feeding ManifestService
- DoclingProcessor already returns `ProcessingResult` with all needed data

**From Story 2.1 (File Discovery):**
- `DiscoveredFile` has `checksum` already computed - no need to recompute

### Git Intelligence

**Recent Commits (patterns to follow):**
```
6a061cf fix(2-3): code review fixes - type errors, lint, docstrings
f6de35f feat(sync): implement output mirroring and file writing
d66a632 fix(2-2): code review fixes - TableFormer config and error logging
3cb4dac feat(processing): implement Docling document processor
```

**Patterns Established:**
- Use `feat(<scope>):` for new functionality
- Use `fix(<scope>):` for code review fixes
- Scope matches story/feature area (sync, processing)
- Commit message describes what was added

### Project Structure Notes

**Files to Create:**
```
src/nest/services/manifest_service.py    # NEW - ManifestService class
tests/services/test_manifest_service.py  # NEW - Unit tests
```

**Files to Modify:**
```
src/nest/core/exceptions.py              # Add ManifestError if missing
src/nest/core/paths.py                   # Add source_path_to_manifest_key()
src/nest/adapters/manifest.py            # Enhance load() error handling
tests/adapters/test_manifest.py          # Add error handling tests
tests/core/test_paths.py                 # Add manifest key tests
```

### Testing Requirements

**Follow Established Patterns:**
```python
# Arrange-Act-Assert structure
def test_record_success_creates_entry():
    # Arrange
    mock_manifest = MockManifestAdapter(...)
    service = ManifestService(mock_manifest, Path("/project"))
    
    # Act
    entry = service.record_success(
        source_path=Path("/project/raw_inbox/doc.pdf"),
        checksum="abc123",
        output_path=Path("/project/processed_context/doc.md"),
    )
    
    # Assert
    assert entry.status == "success"
    assert entry.sha256 == "abc123"
    assert entry.output == "doc.md"
```

**Test Naming Convention:**
- `test_{behavior}_when_{condition}` or `test_{behavior}`
- Example: `test_load_raises_manifest_error_when_json_invalid`

### References

- [Source: epics.md#Story 2.4](../_bmad-output/planning-artifacts/epics.md)
- [Source: architecture.md#Protocol-Based DI](../_bmad-output/planning-artifacts/architecture.md)
- [Source: project-context.md#Error Handling](../_bmad-output/project-context.md)
- [Source: core/models.py](../src/nest/core/models.py) - FileEntry, Manifest models
- [Source: adapters/manifest.py](../src/nest/adapters/manifest.py) - Existing ManifestAdapter
- [Source: core/paths.py](../src/nest/core/paths.py) - relative_to_project() pattern

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (GitHub Copilot)

### Debug Log References

None — all tests passing on first implementation.

### Completion Notes List

1. **Task 4 completed first** — `source_path_to_manifest_key()` added to `core/paths.py` following established `relative_to_project()` pattern
2. **Task 3 completed** — `ManifestError` already existed; enhanced `ManifestAdapter.load()` with try/except for `JSONDecodeError` and `ValidationError`, re-raising as `ManifestError` with actionable message
3. **Task 2 verified** — Protocol already supports all needed operations; updated docstring to document `ManifestError` can be raised
4. **Task 1 completed** — Created `ManifestService` with `record_success()`, `record_failure()`, and `commit()` methods (renamed from `update_manifest` for clarity)
5. **Task 5 completed** — 29 new tests added:
   - 5 unit tests for `source_path_to_manifest_key()` in `test_paths.py`
   - 5 unit tests for `ManifestAdapter.load()` error handling in `test_manifest.py`
   - 14 unit tests for `ManifestService` in `test_manifest_service.py`
   - 5 integration tests in `test_manifest_integration.py`
6. **All 167 tests passing**, linting and type checks clean on new files

### File List

**New Files:**
- `src/nest/services/manifest_service.py` — ManifestService class
- `tests/services/test_manifest_service.py` — 14 unit tests
- `tests/adapters/test_manifest.py` — 5 unit tests
- `tests/integration/test_manifest_integration.py` — 5 integration tests

**Modified Files:**
- `src/nest/core/paths.py` — Added `source_path_to_manifest_key()` function
- `src/nest/adapters/manifest.py` — Enhanced `load()` with ManifestError handling
- `src/nest/adapters/protocols.py` — Updated `load()` docstring
- `tests/core/test_paths.py` — Added 5 tests for `source_path_to_manifest_key()`

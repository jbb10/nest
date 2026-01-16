# Story 2.6: Orphan Cleanup

Status: review
Branch: feat/2-6-orphan-cleanup

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

**As a** user,
**I want** outdated processed files removed when I delete sources,
**So that** my knowledge base stays in sync with my actual documents.

## Acceptance Criteria

### AC1: Automatic Orphan Removal
**Given** `processed_context/old_report.md` exists
**When** `raw_inbox/old_report.pdf` is deleted and sync runs
**Then** `processed_context/old_report.md` is automatically removed
**And** the file is removed from manifest

### AC2: --no-clean Flag Preserves Orphans
**Given** sync runs with `--no-clean` flag
**When** orphan files are detected
**Then** orphan files are NOT removed
**And** they remain in `processed_context/`

### AC3: Orphan Count in Summary
**Given** orphan cleanup removes files
**When** sync summary is displayed
**Then** count of removed orphans is shown

## Tasks / Subtasks

- [x] **Task 1: Add File Deletion to FileSystemProtocol & Adapter** (AC: #1)
  - [x] 1.1 Add `delete_file(path: Path) -> None` method to `FileSystemProtocol` in [adapters/protocols.py](src/nest/adapters/protocols.py)
  - [x] 1.2 Implement `delete_file()` in `FileSystemAdapter` in [adapters/filesystem.py](src/nest/adapters/filesystem.py)
    - Use `path.unlink(missing_ok=True)` for safe deletion
  - [x] 1.3 Add `list_files(directory: Path) -> list[Path]` method to `FileSystemProtocol` (needed to scan processed_context)
  - [x] 1.4 Implement `list_files()` in `FileSystemAdapter`
    - Recursively list all files (not directories)
    - Exclude hidden files (starting with `.`)
    - Return sorted list for deterministic behavior

- [x] **Task 2: Create OrphanDetector in Core Layer** (AC: #1, #2)
  - [x] 2.1 Create `src/nest/core/orphan_detector.py`
  - [x] 2.2 Implement `OrphanDetector` class (pure logic, no I/O)
  - [x] 2.3 Logic: For each file in `output_files`:
    - Compute relative path from `output_dir`
    - If relative path NOT in `manifest_outputs` → it's an orphan
    - Exclude `00_MASTER_INDEX.md` (system file, not orphan)

- [x] **Task 3: Create OrphanCleanupResult Model** (AC: #3)
  - [x] 3.1 Add to `src/nest/core/models.py`:
    ```python
    class OrphanCleanupResult(BaseModel):
        """Result of orphan cleanup operation."""
        
        orphans_detected: list[str]   # Relative paths
        orphans_removed: list[str]    # Relative paths (only if cleanup enabled)
        skipped: bool                 # True if --no-clean flag was set
    ```

- [x] **Task 4: Create OrphanService** (AC: #1, #2, #3)
  - [x] 4.1 Create `src/nest/services/orphan_service.py`
  - [x] 4.2 Implement `OrphanService` class
  - [x] 4.3 Implementation steps:
    1. Load manifest to get `manifest.files` entries with `status="success"`
    2. Extract set of output paths: `{entry.output for entry in manifest.files.values() if entry.status == "success"}`
    3. List all files in `processed_context/` using filesystem adapter
    4. Use `OrphanDetector.detect()` to find orphans
    5. If `no_clean=False`:
       - Delete each orphan file
       - Remove corresponding entry from manifest
    6. Return `OrphanCleanupResult`
  - [x] 4.4 Also remove orphan entries from manifest:
    - Find manifest keys where the output path matches an orphan
    - Remove those keys from `manifest.files`
    - Save updated manifest

- [x] **Task 5: Integrate OrphanService into SyncService** (AC: #1, #2, #3)
  - [x] 5.1 Add `OrphanService` as dependency to `SyncService.__init__()`
  - [x] 5.2 Add `no_clean: bool = False` parameter to `SyncService.sync()`
  - [x] 5.3 Call orphan cleanup AFTER processing files but BEFORE manifest commit
  - [x] 5.4 Return `OrphanCleanupResult` as part of sync result

- [x] **Task 6: Update SyncResult to Include Orphan Data** (AC: #3)
  - [x] 6.1 Add orphan tracking to sync result (for CLI summary display):
    - sync() now returns OrphanCleanupResult directly
  - [x] 6.2 Ensure orphan count is available for CLI layer to display

- [x] **Task 7: Testing** (AC: all)
  - [x] 7.1 Unit tests for `OrphanDetector`:
    - Test detection when orphans exist
    - Test no orphans when all files in manifest
    - Test `00_MASTER_INDEX.md` is excluded
  - [x] 7.2 Unit tests for `OrphanService`:
    - Test cleanup removes files when `no_clean=False`
    - Test cleanup preserves files when `no_clean=True`
    - Test manifest entries are removed for orphans
  - [x] 7.3 Integration test `tests/integration/test_orphan_cleanup.py`:
    - Create processed file, remove source, run sync
    - Verify orphan deleted and removed from manifest
    - Test with `--no-clean` flag

## Dev Notes

### Architecture Compliance

**Layer Responsibilities:**
```
core/orphan_detector.py       → Pure detection logic (no I/O)
core/models.py                → OrphanCleanupResult model
adapters/protocols.py         → FileSystemProtocol extensions
adapters/filesystem.py        → FileSystemAdapter with delete_file, list_files
services/orphan_service.py    → Orchestration (NEW)
services/sync_service.py      → Integration point
```

**Dependency Flow:**
```
SyncService → OrphanService → [FileSystemProtocol, ManifestProtocol]
                    ↓
              OrphanDetector (pure logic)
```

### Existing Infrastructure (DO NOT REINVENT)

**Already Implemented:**
- `ManifestAdapter` with `load()`, `save()` - reuse for orphan tracking
- `Manifest.files` dict with `FileEntry` objects - query for existing outputs
- `FileSystemAdapter` - extend with delete/list methods
- `SyncService` - add orphan cleanup step

**Key Patterns to Follow (from Story 2.5):**
- Services accept protocols, not implementations
- Pure logic in `core/`, orchestration in `services/`
- Use `Path.as_posix()` for portable manifest keys

### Critical Implementation Details

**Orphan Detection Logic:**
```python
# From manifest, get all valid output paths
manifest_outputs = {
    entry.output
    for entry in manifest.files.values()
    if entry.status == "success"
}

# From filesystem, get all files in processed_context
output_files = filesystem.list_files(output_dir)

# Compare: files not in manifest are orphans
for file_path in output_files:
    relative = file_path.relative_to(output_dir).as_posix()
    if relative not in manifest_outputs and relative != "00_MASTER_INDEX.md":
        orphans.append(file_path)
```

**Manifest Entry Removal:**
```python
# Find manifest keys that produced orphaned outputs
orphan_outputs = {orphan.relative_to(output_dir).as_posix() for orphan in orphans}
keys_to_remove = [
    key for key, entry in manifest.files.items()
    if entry.output in orphan_outputs
]
for key in keys_to_remove:
    del manifest.files[key]
```

**Index Generation Timing:**
Orphan cleanup MUST happen before index regeneration so the index doesn't include orphaned files.

### Previous Story Intelligence (2-5)

From Story 2.5 implementation:
- `SyncService` orchestrates discovery → processing → manifest → index
- `ManifestService.load_current_manifest()` returns current manifest state
- Index uses `manifest.files` with `status="success"` for file list
- Pattern: filter manifest, extract outputs, pass to downstream service

### Testing Patterns (from 2-4, 2-5)

**Mock Setup Pattern:**
```python
@pytest.fixture
def mock_filesystem():
    class MockFileSystem:
        def __init__(self):
            self.deleted_files: list[Path] = []
            
        def delete_file(self, path: Path) -> None:
            self.deleted_files.append(path)
            
        def list_files(self, directory: Path) -> list[Path]:
            return [...]
    return MockFileSystem()
```

**Integration Test Pattern:**
```python
def test_orphan_cleanup_removes_stale_files(tmp_path):
    # Setup: Create project with processed file
    output_dir = tmp_path / "processed_context"
    output_dir.mkdir()
    orphan_file = output_dir / "deleted_source.md"
    orphan_file.write_text("# Old content")
    
    # Manifest has no entry for this file
    manifest = Manifest(nest_version="1.0.0", project_name="test", files={})
    
    # Run sync...
    
    # Assert orphan removed
    assert not orphan_file.exists()
```

### Project Structure Notes

**New Files:**
- `src/nest/core/orphan_detector.py` - Pure detection logic
- `src/nest/services/orphan_service.py` - Orchestration service
- `tests/core/test_orphan_detector.py` - Unit tests
- `tests/services/test_orphan_service.py` - Service tests
- `tests/integration/test_orphan_cleanup.py` - End-to-end tests

**Modified Files:**
- `src/nest/adapters/protocols.py` - Add `delete_file()`, `list_files()`
- `src/nest/adapters/filesystem.py` - Implement new methods
- `src/nest/core/models.py` - Add `OrphanCleanupResult`
- `src/nest/services/sync_service.py` - Integrate orphan cleanup

### Edge Cases to Handle

1. **Empty processed_context** - No orphans to detect
2. **No manifest entries** - All processed files are orphans
3. **00_MASTER_INDEX.md** - System file, never an orphan
4. **Nested orphans** - Handle subdirectory cleanup
5. **Permission errors** - Graceful handling if file can't be deleted
6. **Race conditions** - File deleted between detection and removal (use `missing_ok=True`)

### References

- [Architecture: Error Handling](architecture.md#error-handling) - Result types pattern
- [Architecture: Project Structure](architecture.md#project-structure) - Layer responsibilities
- [Epics: Story 2.6](epics.md#story-26-orphan-cleanup) - Acceptance criteria
- [PRD: FR9](prd.md) - "nest sync removes orphaned files from processed_context/"

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (via GitHub Copilot)

### Debug Log References

N/A

### Completion Notes List

✅ **Task 1 Complete**: Added `delete_file()` and `list_files()` methods to FileSystemProtocol and FileSystemAdapter
- delete_file() uses path.unlink(missing_ok=True) for safe deletion
- list_files() recursively lists all files, excludes hidden files, returns sorted results
- All 7 new filesystem adapter tests passing

✅ **Task 2 Complete**: Created OrphanDetector in core layer
- Pure detection logic with no I/O dependencies
- Computes relative paths and compares against manifest outputs
- Excludes 00_MASTER_INDEX.md system file
- All 6 unit tests passing

✅ **Task 3 Complete**: Added OrphanCleanupResult model to core/models.py
- Tracks detected vs removed orphans
- Includes skipped flag for --no-clean mode

✅ **Task 4 Complete**: Implemented OrphanService orchestration layer
- Integrates filesystem, manifest, and orphan detector
- Handles no_clean flag for dry-run mode
- Removes orphan files AND their manifest entries
- All 5 service tests passing

✅ **Task 5 Complete**: Integrated OrphanService into SyncService
- Added as dependency in constructor
- Added no_clean parameter to sync()
- Orphan cleanup runs after processing, before manifest commit
- Returns OrphanCleanupResult for CLI display
- Updated all existing SyncService tests to work with new dependency

✅ **Task 6 Complete**: sync() return type updated
- Now returns OrphanCleanupResult directly
- Orphan count available for CLI summary

✅ **Task 7 Complete**: Comprehensive testing
- 6 OrphanDetector unit tests
- 5 OrphanService unit tests  
- 4 integration tests
- All 43 orphan-related tests passing
- No regressions in existing tests

**Implementation follows architecture patterns:**
- Protocol-based DI (services depend on protocols)
- Pure logic in core/ (OrphanDetector)
- Orchestration in services/ (OrphanService)
- Red-green-refactor cycle throughout
- Comprehensive test coverage at all layers

### File List

- src/nest/core/orphan_detector.py (NEW)
- src/nest/core/models.py (MODIFIED - added OrphanCleanupResult)
- src/nest/adapters/protocols.py (MODIFIED - added delete_file, list_files)
- src/nest/adapters/filesystem.py (MODIFIED - implemented new methods)
- src/nest/services/orphan_service.py (NEW)
- src/nest/services/sync_service.py (MODIFIED - integrated orphan cleanup)
- tests/core/test_orphan_detector.py (NEW)
- tests/services/test_orphan_service.py (NEW)
- tests/services/test_sync_service.py (MODIFIED - updated for new dependency)
- tests/adapters/test_filesystem.py (MODIFIED - added new tests)
- tests/integration/test_orphan_cleanup.py (NEW)

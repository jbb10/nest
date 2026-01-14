# Story 2.1: File Discovery & Checksum Engine

Status: done
Branch: feat/2-1-file-discovery-checksum-engine

---

## Story

**As a** user with documents in `raw_inbox/`,
**I want** the system to detect which files are new, modified, or unchanged,
**So that** only necessary files are processed, saving time.

---

## Acceptance Criteria

### AC1: Recursive File Discovery
**Given** `raw_inbox/` contains files (.pdf, .docx, .pptx, .xlsx, .html)
**When** sync runs file discovery
**Then** all supported files are found recursively (including subdirectories)
**And** unsupported file types are ignored (e.g., .txt, .jpg, .zip)

### AC2: New File Detection
**Given** a file exists in `raw_inbox/` but NOT in manifest
**When** checksum comparison runs
**Then** the file is marked as "new" for processing

### AC3: Modified File Detection
**Given** a file exists in both `raw_inbox/` and manifest
**When** the SHA-256 checksum differs from manifest
**Then** the file is marked as "modified" for processing

### AC4: Unchanged File Detection
**Given** a file exists in both `raw_inbox/` and manifest
**When** the SHA-256 checksum matches manifest
**Then** the file is marked as "unchanged" and skipped

### AC5: Efficient Checksum Computation
**Given** checksum computation runs on a file
**When** `core/checksum.py` processes the file
**Then** it reads in chunks to handle large files efficiently (e.g., 64KB chunks)
**And** returns hex-encoded SHA-256 hash string

---

## Tasks / Subtasks

- [x] **Task 1: Create Checksum Module** (AC: #5)
  - [x] 1.1 Create `src/nest/core/checksum.py`
  - [x] 1.2 Implement `compute_sha256(path: Path) -> str` function
  - [x] 1.3 Use chunked reading (64KB default) for memory efficiency
  - [x] 1.4 Return lowercase hex-encoded hash string
  - [x] 1.5 Handle `FileNotFoundError` with clear error message
  - [x] 1.6 Add comprehensive docstrings (Google style)

- [x] **Task 2: Create FileDiscoveryProtocol** (AC: #1)
  - [x] 2.1 Add `FileDiscoveryProtocol` to `src/nest/adapters/protocols.py`
  - [x] 2.2 Define method: `discover(directory: Path, extensions: set[str]) -> list[Path]`
  - [x] 2.3 Add docstrings explaining recursive discovery behavior

- [x] **Task 3: Implement FileDiscoveryAdapter** (AC: #1)
  - [x] 3.1 Create `src/nest/adapters/file_discovery.py`
  - [x] 3.2 Implement `FileDiscoveryAdapter` class implementing `FileDiscoveryProtocol`
  - [x] 3.3 Use `pathlib.Path.rglob()` for recursive file discovery
  - [x] 3.4 Filter by supported extensions (case-insensitive): `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`
  - [x] 3.5 Return sorted list of absolute paths for deterministic ordering
  - [x] 3.6 Ignore hidden files and directories (starting with `.`)

- [x] **Task 4: Create FileStatus Model** (AC: #2, #3, #4)
  - [x] 4.1 Add `FileStatus` Literal type to `src/nest/core/models.py`: `Literal["new", "modified", "unchanged"]`
  - [x] 4.2 Add `DiscoveredFile` dataclass to `src/nest/core/models.py`:
    ```python
    class DiscoveredFile(BaseModel):
        path: Path
        status: FileStatus
        checksum: str
    ```

- [x] **Task 5: Create FileChangeDetector in Core** (AC: #2, #3, #4, #5)
  - [x] 5.1 Create `src/nest/core/change_detector.py`
  - [x] 5.2 Implement `FileChangeDetector` class (pure logic, no I/O)
  - [x] 5.3 Constructor accepts manifest `files` dict
  - [x] 5.4 Implement `classify(path: Path, checksum: str) -> FileStatus`:
    - Returns "new" if path not in manifest
    - Returns "modified" if checksum differs from manifest entry
    - Returns "unchanged" if checksum matches
  - [x] 5.5 Use relative paths for manifest key lookups
  - [x] 5.6 Add comprehensive docstrings

- [x] **Task 6: Create DiscoveryService** (AC: all)
  - [x] 6.1 Create `src/nest/services/discovery_service.py`
  - [x] 6.2 Implement `DiscoveryService` class with DI:
    ```python
    def __init__(
        self,
        file_discovery: FileDiscoveryProtocol,
        manifest: ManifestProtocol,
    ):
    ```
  - [x] 6.3 Implement `discover_changes(project_dir: Path) -> DiscoveryResult`:
    - Load manifest
    - Discover files in `raw_inbox/`
    - Compute checksum for each file
    - Classify as new/modified/unchanged
    - Return structured result
  - [x] 6.4 Add `DiscoveryResult` model:
    ```python
    class DiscoveryResult(BaseModel):
        new_files: list[DiscoveredFile]
        modified_files: list[DiscoveredFile]
        unchanged_files: list[DiscoveredFile]
        
        @property
        def pending_count(self) -> int:
            return len(self.new_files) + len(self.modified_files)
    ```

- [x] **Task 7: Add Supported Extensions Constant** (AC: #1)
  - [x] 7.1 Add `SUPPORTED_EXTENSIONS` constant to `src/nest/core/constants.py` (create file):
    ```python
    SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
        ".pdf", ".docx", ".pptx", ".xlsx", ".html"
    })
    ```

- [x] **Task 8: Comprehensive Testing** (AC: all)
  - [x] 8.1 Create `tests/core/test_checksum.py`
    - Test checksum computation produces correct SHA-256
    - Test chunked reading handles large files
    - Test FileNotFoundError handling
  - [x] 8.2 Create `tests/adapters/test_file_discovery.py`
    - Test recursive file discovery
    - Test extension filtering (includes supported, ignores others)
    - Test hidden file/directory exclusion
    - Test empty directory handling
  - [x] 8.3 Create `tests/core/test_change_detector.py`
    - Test new file classification
    - Test modified file classification
    - Test unchanged file classification
  - [x] 8.4 Create `tests/services/test_discovery_service.py`
    - Test full discovery workflow with mocks
    - Test discovery result counts
    - Test integration with manifest

---

## Dev Notes

### Architecture Compliance

**Layer Responsibilities:**
```
core/checksum.py           → Pure SHA-256 computation (no I/O except file read)
core/change_detector.py    → Pure classification logic (no I/O)
core/constants.py          → SUPPORTED_EXTENSIONS definition
core/models.py             → FileStatus, DiscoveredFile, DiscoveryResult models
adapters/protocols.py      → FileDiscoveryProtocol definition
adapters/file_discovery.py → FileDiscoveryAdapter implementation
services/discovery_service.py → Orchestration layer
```

**Dependency Injection Pattern:**
```python
# services/discovery_service.py
class DiscoveryService:
    def __init__(
        self,
        file_discovery: FileDiscoveryProtocol,
        manifest: ManifestProtocol,
    ):
        self._file_discovery = file_discovery
        self._manifest = manifest
```

### Critical Implementation Details

**Checksum Chunking:**
```python
# core/checksum.py
def compute_sha256(path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash of a file using chunked reading.
    
    Args:
        path: Path to the file to hash.
        chunk_size: Size of chunks to read (default 64KB).
        
    Returns:
        Lowercase hex-encoded SHA-256 hash string.
        
    Raises:
        FileNotFoundError: If path does not exist.
    """
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
```

**Path Normalization for Manifest Keys:**
- Store relative paths in manifest (e.g., `contracts/2024/alpha.pdf`)
- Convert discovered absolute paths to relative before lookup
- Use forward slashes consistently (cross-platform)

**Extension Matching:**
- Case-insensitive: `.PDF` and `.pdf` both match
- Use `path.suffix.lower()` for comparison

### File Structure to Create/Modify

```
src/nest/
├── core/
│   ├── checksum.py           # NEW: SHA-256 computation
│   ├── change_detector.py    # NEW: Classification logic
│   ├── constants.py          # NEW: SUPPORTED_EXTENSIONS
│   └── models.py             # UPDATE: Add FileStatus, DiscoveredFile, DiscoveryResult
├── adapters/
│   ├── protocols.py          # UPDATE: Add FileDiscoveryProtocol
│   └── file_discovery.py     # NEW: FileDiscoveryAdapter
└── services/
    └── discovery_service.py  # NEW: Orchestration

tests/
├── core/
│   ├── test_checksum.py         # NEW
│   └── test_change_detector.py  # NEW
├── adapters/
│   └── test_file_discovery.py   # NEW
└── services/
    └── test_discovery_service.py # NEW
```

### Testing Strategy

**Unit Tests (core/):**
- Pure functions with no mocking needed for checksum
- Change detector tested with sample manifest data

**Adapter Tests:**
- Use `tmp_path` fixture for real filesystem operations
- Create sample directory structures with various file types

**Service Tests:**
- Mock both FileDiscoveryProtocol and ManifestProtocol
- Verify correct orchestration flow

### Project Structure Notes

- Follows established `src/nest/` layout pattern from Epic 1
- All new modules use absolute imports: `from nest.core.checksum import compute_sha256`
- Models use Pydantic v2 with `BaseModel`
- Type hints use modern Python 3.10+ syntax (`list[]`, `dict[]`, `|`)

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure] — Layer organization
- [Source: _bmad-output/planning-artifacts/architecture.md#Dependency Injection] — Protocol pattern
- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.1] — Acceptance criteria
- [Source: _bmad-output/project-context.md#Python Language Rules] — Naming and type hints
- [Source: _bmad-output/project-context.md#Testing Rules] — Test structure and naming

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5

### Debug Log References

N/A

### Completion Notes List

- ✅ Task 1: Implemented `compute_sha256()` with 64KB chunked reading, FileNotFoundError handling, Google-style docstrings
- ✅ Task 2: Added `FileDiscoveryProtocol` to protocols.py with recursive discovery method signature
- ✅ Task 3: Implemented `FileDiscoveryAdapter` with rglob, case-insensitive extension filtering, hidden file exclusion, sorted absolute paths
- ✅ Task 4: Added `FileStatus` Literal type, `DiscoveredFile` and `DiscoveryResult` models to core/models.py
- ✅ Task 5: Implemented `FileChangeDetector` pure logic class for new/modified/unchanged classification
- ✅ Task 6: Implemented `DiscoveryService` orchestration with DI pattern
- ✅ Task 7: Added `SUPPORTED_EXTENSIONS` frozenset to core/constants.py
- ✅ Task 8: Added comprehensive test coverage (33 new tests across 4 test files)

All 72 tests passing. Linting clean. Type checking clean.

### File List

**New Files:**
- src/nest/core/checksum.py
- src/nest/core/change_detector.py
- src/nest/core/constants.py
- src/nest/adapters/file_discovery.py
- src/nest/services/discovery_service.py
- tests/core/test_checksum.py
- tests/core/test_change_detector.py
- tests/adapters/test_file_discovery.py
- tests/services/test_discovery_service.py

### Code Review Fixes (2026-01-14)
- **High**: Fixed `DiscoveryService` crash on first run (missing manifest) by handling `FileNotFoundError`.
- **Medium**: Fixed `DiscoveryService` crash on file read error (race condition) by handling `OSError`.
- **Medium**: Fixed `FileDiscoveryAdapter` unsafe file checking by adding `is_file()` check.
- **Low**: Added input validation to `FileChangeDetector` to enforce relative paths.
- Added regression tests for all fixes.


**Modified Files:**
- src/nest/core/models.py (added FileStatus, DiscoveredFile, DiscoveryResult)
- src/nest/adapters/protocols.py (added FileDiscoveryProtocol)

---

## Change Log

| Date | Changes |
|------|---------|
| 2026-01-13 | Story 2.1 implementation complete - File discovery and checksum engine with full test coverage |

---

## Status

review
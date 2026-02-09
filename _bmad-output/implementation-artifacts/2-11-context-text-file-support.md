# Story 2.11: Context Text File Support in Index and Status

Status: done
Branch: feat/2-11-context-text-file-support

## Story

As a **user who manually adds plain text files (`.txt`, `.yaml`, `.csv`, etc.) to `_nest_context/`**,
I want **those files to appear in the master index and be counted correctly in status**,
so that **my AI agent can discover and reference all text-based context I've curated, not just Markdown files**.

## Business Context

Story 2.10 established user-curated context support — users can drop files directly into `_nest_context/` and they are preserved during orphan cleanup and included in the index. However, index generation (`index_service.py`) currently filters on `.suffix == ".md"` only, meaning plain text files like `.txt`, `.yaml`, `.csv`, etc. are invisible to the master index and therefore invisible to the `@nest` agent.

The same `.md`-only bias exists (or could exist) in status counting and user-curated file counting. This story introduces a single `CONTEXT_TEXT_EXTENSIONS` constant and applies it consistently across all context-scanning logic.

## Acceptance Criteria

### AC1: CONTEXT_TEXT_EXTENSIONS Constant

**Given** the `core/paths.py` module
**When** the developer references supported context file types
**Then** a `CONTEXT_TEXT_EXTENSIONS` list constant is available containing:
`.md`, `.txt`, `.text`, `.rst`, `.csv`, `.json`, `.yaml`, `.yml`, `.toml`, `.xml`
**And** all modules that filter context files import this constant from `core/paths.py`

### AC2: Index Generation Includes All Text Types

**Given** `_nest_context/` contains files with various text extensions
**When** `nest sync` runs and regenerates `00_MASTER_INDEX.md`
**Then** ALL files matching `CONTEXT_TEXT_EXTENSIONS` are listed in the index
**And** files with unsupported extensions (e.g., `.png`, `.zip`) are NOT listed

### AC3: User-Added .txt File Indexed

**Given** I manually add `meeting-notes.txt` to `_nest_context/`
**When** `nest sync` runs
**Then** `meeting-notes.txt` appears in `00_MASTER_INDEX.md`

### AC4: User-Added .yaml File Indexed

**Given** I manually add `api-spec.yaml` to `_nest_context/`
**When** `nest sync` runs
**Then** `api-spec.yaml` appears in `00_MASTER_INDEX.md`

### AC5: Status Counting Uses Text Extensions

**Given** `_nest_context/` contains files of varying types
**When** `nest status` analyzes context files
**Then** only files matching `CONTEXT_TEXT_EXTENSIONS` are counted in the context file total
**And** unsupported file types are excluded from counts

### AC6: User-Curated Counting Uses Text Extensions

**Given** `_nest_context/` contains manifest-tracked `.md` files and user-added `.txt`/`.yaml`/`.csv` files
**When** orphan service counts user-curated files
**Then** only files matching `CONTEXT_TEXT_EXTENSIONS` (and not in manifest) are counted as user-curated
**And** binary/unsupported files are excluded from user-curated count

### AC7: Orphan Detection Unchanged

**Given** a user adds `report.txt` directly to `_nest_context/` (not via sync)
**When** `nest sync` runs orphan cleanup
**Then** `report.txt` is NOT removed (not in manifest = user-curated, preserved)

### AC8: Agent Template Updated

**Given** the VS Code agent template
**When** `nest init` generates the agent file
**Then** the agent instructions mention that context files may be in various text formats

### AC9: All Existing Tests Pass

**Given** all unit, integration, and E2E tests
**When** the changes are complete
**Then** all tests pass with no regressions

## E2E Testing Requirements

- [ ] Existing E2E tests cover this story's functionality: Partially — sync E2E tests verify `.md` indexing
- [ ] New E2E tests required: Yes — test non-Markdown text files in context indexing
- [ ] E2E test execution required for story completion: Yes — all E2E tests must pass

**New E2E Tests Needed:**
```python
def test_sync_indexes_user_curated_txt_file():
    """A .txt file added to _nest_context/ should appear in the master index."""
    # 1. Init project
    # 2. Manually create _nest_context/notes.txt
    # 3. Run nest sync
    # 4. Read 00_MASTER_INDEX.md
    # 5. Assert notes.txt is listed

def test_sync_indexes_user_curated_yaml_file():
    """A .yaml file added to _nest_context/ should appear in the master index."""
    # 1. Init project
    # 2. Manually create _nest_context/api-spec.yaml
    # 3. Run nest sync
    # 4. Read 00_MASTER_INDEX.md
    # 5. Assert api-spec.yaml is listed

def test_sync_ignores_binary_in_context():
    """A .png file added to _nest_context/ should NOT appear in the master index."""
    # 1. Init project
    # 2. Manually create _nest_context/diagram.png (binary content)
    # 3. Run nest sync
    # 4. Read 00_MASTER_INDEX.md
    # 5. Assert diagram.png is NOT listed
```

## Tasks / Subtasks

### Task 1: Add CONTEXT_TEXT_EXTENSIONS Constant (AC: 1)
- [x] 1.1: Add `CONTEXT_TEXT_EXTENSIONS` list to `src/nest/core/paths.py`:
  ```python
  CONTEXT_TEXT_EXTENSIONS = [
      ".md", ".txt", ".text", ".rst",
      ".csv", ".json", ".yaml", ".yml", ".toml", ".xml",
  ]
  ```

### Task 2: Update Index Service (AC: 2, 3, 4)
- [x] 2.1: Import `CONTEXT_TEXT_EXTENSIONS` in `src/nest/services/index_service.py`
- [x] 2.2: Change filter from `file_path.suffix == ".md"` to `file_path.suffix.lower() in CONTEXT_TEXT_EXTENSIONS`
- [x] 2.3: Update docstring/comment from "all .md files" to "all supported text files"

### Task 3: Update Status Service (AC: 5)
- [x] 3.1: Import `CONTEXT_TEXT_EXTENSIONS` in `src/nest/services/status_service.py`
- [x] 3.2: In `analyze_context_files()`, add filter: only count files whose suffix is in `CONTEXT_TEXT_EXTENSIONS`
- [x] 3.3: Update docstring to reflect text extension filtering

### Task 4: Update Orphan Service User-Curated Counting (AC: 6)
- [x] 4.1: Import `CONTEXT_TEXT_EXTENSIONS` in `src/nest/services/orphan_service.py`
- [x] 4.2: In `count_user_curated_files()`, add filter: only count files whose suffix is in `CONTEXT_TEXT_EXTENSIONS`
- [x] 4.3: Update docstring to reflect text extension filtering

### Task 5: Update Sync Service Comment (AC: 2)
- [x] 5.1: Update comment in `src/nest/services/sync_service.py` from "scans entire context directory for all .md files" to "scans entire context directory for all supported text files"

### Task 6: Update Agent Template (AC: 8)
- [x] 6.1: Update `src/nest/agents/templates/vscode.md.jinja` to mention that context files may include various text formats (`.txt`, `.yaml`, `.csv`, etc.), not just Markdown

### Task 7: Unit Tests (AC: 1, 2, 3, 4, 5, 6, 9)
- [x] 7.1: Add test to `tests/core/test_paths.py` verifying `CONTEXT_TEXT_EXTENSIONS` contains all 10 expected extensions
- [x] 7.2: Update `tests/services/test_index_service.py`:
  - Add test: `.txt` file is included in generated index
  - Add test: `.yaml` file is included in generated index
  - Add test: `.png` file is excluded from generated index
  - Update existing tests if they assert `.md`-only behavior
- [x] 7.3: Update `tests/services/test_status_service.py`:
  - Add test: status counts `.txt` files in context
  - Add test: status excludes `.png` files from context count
- [x] 7.4: Update orphan service tests:
  - Add test: `.txt` user-curated file is counted
  - Add test: `.png` file is not counted as user-curated

### Task 8: E2E Tests (AC: 2, 3, 4, 9)
- [x] 8.1: Add `test_sync_indexes_user_curated_txt_file()` to E2E test suite
- [x] 8.2: Add `test_sync_indexes_user_curated_yaml_file()` to E2E test suite
- [x] 8.3: Add `test_sync_ignores_binary_in_context()` to E2E test suite

### Task 9: Run Full Test Suite (AC: 9)
- [x] 9.1: Run `pytest -m "not e2e"` — 390 passed
- [x] 9.2: Run `pytest -m "e2e"` — 30 passed
- [x] 9.3: Run `ruff check` — no linting errors on changed files (1 pre-existing E501 in test_docling_processor.py)
- [x] 9.4: Run `pyright` — 0 errors, 0 warnings

## Dev Notes

### Critical Implementation Details

**Single Source of Truth:**
The `CONTEXT_TEXT_EXTENSIONS` constant in `core/paths.py` is the ONLY place these extensions are defined. Every module that needs to filter context files MUST import from there. Never hardcode `.md` checks elsewhere.

**Case Sensitivity:**
Use `.suffix.lower()` when comparing against the constant to handle edge cases like `.TXT` or `.Yaml`.

**Exclude the Index Itself:**
Continue to exclude `00_MASTER_INDEX.md` from index listing (existing behavior). The `MASTER_INDEX_FILE` constant check remains.

**Orphan Detector Unchanged:**
The `core/orphan_detector.py` does NOT need changes. It determines orphan status based on manifest tracking, not file extension. The extension filter only applies to *counting* and *indexing* operations.

### File Impact Summary

| Category | File Count | Change Type |
|----------|------------|-------------|
| `src/nest/core/paths.py` | 1 | Add constant |
| `src/nest/services/index_service.py` | 1 | Change filter |
| `src/nest/services/status_service.py` | 1 | Add filter |
| `src/nest/services/orphan_service.py` | 1 | Add filter |
| `src/nest/services/sync_service.py` | 1 | Update comment |
| `src/nest/agents/templates/vscode.md.jinja` | 1 | Update text |
| `tests/` | ~4-5 files | Add/update tests |
| **Total** | **~10 files** | |

### Estimated Effort

Small story — primarily additive changes with minimal risk. Core logic change is a single filter swap in `index_service.py`. All other changes are consistency alignment.

### References

- [Source: Architecture — Path Handling Patterns] — `CONTEXT_TEXT_EXTENSIONS` constant definition
- [Source: PRD Section 4.2] — Sync behavior step 5 (index generation with text extensions)
- [Source: Epics Story 2.10] — User-curated context support (predecessor story)
- [Source: Epics Story 2.5] — Master index generation (original index story)
- [Source: Sprint Change Proposal 2026-01-21] — User-curated files design rationale

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (GitHub Copilot)

### Completion Notes List

- Added `CONTEXT_TEXT_EXTENSIONS` constant with 10 text extensions to `core/paths.py`
- Changed `index_service.py` filter from `.md`-only to `CONTEXT_TEXT_EXTENSIONS` with case-insensitive matching
- Added text extension filter to `status_service.py` `analyze_context_files()` — unsupported types excluded from count
- Added text extension filter to `orphan_service.py` `count_user_curated_files()` — binary files excluded from user-curated count
- Updated sync_service.py comment to reflect "all supported text files"
- Updated agent template to list supported text formats
- Added 3 unit tests for the constant, 6 unit tests for index service text extensions, 2 unit tests for status service, 3 unit tests for orphan service user-curated counting
- Added 3 E2E tests: txt indexing, yaml indexing, binary exclusion
- All 390 unit tests + 30 E2E tests pass. Pyright clean. Ruff clean on changed files.

### File List

- `src/nest/core/paths.py` — Added `CONTEXT_TEXT_EXTENSIONS` constant
- `src/nest/services/index_service.py` — Changed filter to use `CONTEXT_TEXT_EXTENSIONS`
- `src/nest/services/status_service.py` — Added text extension filter in `analyze_context_files()`
- `src/nest/services/orphan_service.py` — Added text extension filter in `count_user_curated_files()`
- `src/nest/services/sync_service.py` — Updated comment
- `src/nest/agents/templates/vscode.md.jinja` — Updated technical context section
- `tests/core/test_paths.py` — Added `TestContextTextExtensions` (3 tests)
- `tests/services/test_index_service.py` — Added `TestUpdateIndexTextExtensions` (6 tests)
- `tests/services/test_status_service.py` — Added 2 tests for text extension filtering
- `tests/services/test_orphan_service.py` — Added `TestCountUserCuratedFiles` (3 tests)
- `tests/e2e/test_sync_e2e.py` — Added `TestSyncContextTextFilesE2E` (3 tests)

## Change Log

- 2026-02-09: Implemented Story 2.11 — Context Text File Support. Added `CONTEXT_TEXT_EXTENSIONS` constant and applied it consistently across index generation, status counting, and user-curated file counting. All 420 tests pass.- 2026-02-09: Code Review Fixes (Amelia): 
  - Fixed hardcoded string in orphan service (used constant).
  - Improved index sort order to be case-insensitive.
  - Fixed CRITICAL CLI fragility by implementing lazy imports and NoOp fallbacks for `docling` dependency in init, sync, and doctor commands. This allows E2E tests to run even if docling is missing.
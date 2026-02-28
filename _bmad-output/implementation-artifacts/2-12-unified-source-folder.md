# Story 2.12: Unified Source Folder — Text File Passthrough

Status: done
Branch: feat/2-12-unified-source-folder

## Story

As a **user who wants to add reference materials for my AI agent**,
I want **to drop ALL my files — PDFs, Word docs, AND plain text files — into a single `_nest_sources/` folder**,
So that **I don't need to understand the internal processing pipeline, and everything appears indexed in `_nest_context/` after running `nest sync`**.

## Business Context

Currently Nest has a two-folder mental model that leaks implementation details:

- **`_nest_sources/`** — Only for Docling-convertible formats (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`). These get processed into Markdown and written to `_nest_context/`.
- **`_nest_context/`** — For user-curated text files (`.md`, `.txt`, `.yaml`, `.csv`, etc.) that users must drop here directly since they don't need conversion.

This forces users to know which file types need conversion and which don't — an unnecessary cognitive burden. The fix: extend the discovery service to recognize `CONTEXT_TEXT_EXTENSIONS` in `_nest_sources/`, and route those files through a **passthrough copy** pipeline instead of Docling conversion. The result is a single-folder experience: put everything in `_nest_sources/`, run `nest sync`, done.

**User-curated files dropped directly into `_nest_context/` remain fully supported** (backward compatibility). This story adds a second path, not a replacement.

### Key Insight

Text files don't need conversion — they need a **copy**. The sync pipeline already handles routing per-file via `OutputMirrorService.process_file()`. By extending discovery to find text files and adding a passthrough code path in the processing layer, we get unified folder behavior with minimal architectural change.

## Acceptance Criteria

### AC1: Discovery Includes Text Files in Sources

**Given** `_nest_sources/` contains text files matching `CONTEXT_TEXT_EXTENSIONS` (`.md`, `.txt`, `.yaml`, `.csv`, `.json`, `.yml`, `.toml`, `.xml`, `.text`, `.rst`)
**When** the discovery service scans for changes
**Then** those text files are discovered, checksummed, and classified (new/modified/unchanged) just like Docling-convertible files
**And** the existing `SUPPORTED_EXTENSIONS` filtering is expanded to include `CONTEXT_TEXT_EXTENSIONS`

### AC2: Text Files Copied (Not Converted) to Context

**Given** a text file `notes.txt` exists in `_nest_sources/`
**When** `nest sync` processes this file
**Then** `notes.txt` is **copied** to `_nest_context/notes.txt` (preserving original content and extension)
**And** the file is NOT passed to the Docling document processor

### AC3: Directory Structure Preserved for Passthrough

**Given** `_nest_sources/team/meeting-notes.md` exists
**When** `nest sync` runs
**Then** `_nest_context/team/meeting-notes.md` is created with the same content
**And** intermediate directories are created as needed

### AC4: Passthrough Files Tracked in Manifest

**Given** `notes.txt` was copied from `_nest_sources/` to `_nest_context/`
**When** the manifest is updated
**Then** `notes.txt` has a manifest entry with:
- `sha256`: checksum of the source file
- `output`: relative path in `_nest_context/` (e.g., `notes.txt`)
- `status`: `"success"`
- `processed_at`: current timestamp
**And** subsequent sync runs skip the file if checksum is unchanged

### AC5: Passthrough Files Indexed

**Given** `notes.txt` was copied to `_nest_context/` via passthrough
**When** `nest sync` regenerates `00_MASTER_INDEX.md`
**Then** `notes.txt` appears in the index
(This is already handled by Story 2.11's `CONTEXT_TEXT_EXTENSIONS` indexing logic — no new index work needed.)

### AC6: Orphan Cleanup for Passthrough Files

**Given** `notes.txt` was previously synced from `_nest_sources/` to `_nest_context/`
**And** the user deletes `notes.txt` from `_nest_sources/`
**When** `nest sync` runs orphan cleanup
**Then** `notes.txt` is removed from `_nest_context/` (it is manifest-tracked, therefore an orphan)
**And** its manifest entry is removed

### AC7: Name Collision — Source Text vs Docling Output

**Given** both `report.pdf` and `report.md` exist in `_nest_sources/`
**When** `nest sync` runs
**Then** `report.md` (passthrough) and `report.pdf` (Docling conversion → `report.md`) would collide
**And** the passthrough text file wins (it is the user's explicit content)
**And** a warning is logged: `"Skipping Docling conversion of report.pdf — output path report.md conflicts with passthrough source file report.md"`
**And** the Docling-convertible file is recorded with `status: "skipped"` and an error message in the manifest

### AC8: Dry Run Shows Passthrough Files

**Given** `_nest_sources/` contains new text files
**When** `nest sync --dry-run` runs
**Then** passthrough text files appear in the "new files" count
**And** they are indistinguishable from Docling-convertible files in the dry-run summary (both are just file counts)

### AC9: Status Shows Unified Counts

**Given** `_nest_sources/` contains a mix of Docling-convertible and passthrough text files
**When** `nest status` runs
**Then** all source files (regardless of type) are counted in the source file totals
**And** all context files (regardless of origin) are counted in context file totals

### AC10: Force Flag Recopies Text Files

**Given** `notes.txt` was previously synced via passthrough
**When** `nest sync --force` runs
**Then** `notes.txt` is re-copied to `_nest_context/` even if checksum is unchanged

### AC11: User-Curated Context Files Still Supported

**Given** a user drops `custom-notes.txt` directly into `_nest_context/` (not via `_nest_sources/`)
**When** `nest sync` runs
**Then** `custom-notes.txt` is indexed, counted, and preserved (not removed by orphan cleanup)
**And** behavior is identical to pre-2.12 behavior for user-curated files

### AC12: All Existing Tests Pass

**Given** all unit, integration, and E2E tests
**When** the changes are complete
**Then** all tests pass with no regressions

## E2E Testing Requirements

- [ ] Existing E2E tests cover this story's functionality: No — existing E2E tests only exercise Docling-convertible formats in sources
- [ ] New E2E tests required: Yes
- [ ] E2E test execution required for story completion: Yes — all E2E tests must pass

**New E2E Tests Needed:**
```python
def test_sync_passthrough_txt_file():
    """A .txt file in _nest_sources/ should be copied to _nest_context/ and indexed."""
    # 1. Init project
    # 2. Create _nest_sources/notes.txt with known content
    # 3. Run nest sync
    # 4. Assert _nest_context/notes.txt exists with same content
    # 5. Assert notes.txt appears in 00_MASTER_INDEX.md
    # 6. Assert .nest_manifest.json has entry for notes.txt with status "success"

def test_sync_passthrough_yaml_file():
    """A .yaml file in _nest_sources/ should be copied to _nest_context/ and indexed."""
    # 1. Init project
    # 2. Create _nest_sources/api-spec.yaml
    # 3. Run nest sync
    # 4. Assert _nest_context/api-spec.yaml exists with same content
    # 5. Assert api-spec.yaml appears in 00_MASTER_INDEX.md

def test_sync_passthrough_preserves_subdirectory():
    """Passthrough files in subdirectories should mirror the structure."""
    # 1. Init project
    # 2. Create _nest_sources/team/notes.txt
    # 3. Run nest sync
    # 4. Assert _nest_context/team/notes.txt exists

def test_sync_passthrough_incremental_skip():
    """Unchanged passthrough files should be skipped on subsequent sync."""
    # 1. Init project, create _nest_sources/notes.txt
    # 2. Run nest sync (first time — processes)
    # 3. Run nest sync again (second time — skips)
    # 4. Assert processed_count == 0 on second run

def test_sync_passthrough_orphan_cleanup():
    """Removing a passthrough source should orphan-clean its context copy."""
    # 1. Init project, create _nest_sources/notes.txt
    # 2. Run nest sync
    # 3. Delete _nest_sources/notes.txt
    # 4. Run nest sync
    # 5. Assert _nest_context/notes.txt is removed
    # 6. Assert notes.txt no longer in 00_MASTER_INDEX.md

def test_sync_passthrough_ignores_binary():
    """A .png file in _nest_sources/ should not be processed or copied."""
    # 1. Init project
    # 2. Create _nest_sources/diagram.png (binary content)
    # 3. Run nest sync
    # 4. Assert _nest_context/diagram.png does NOT exist
    # 5. Assert diagram.png NOT in 00_MASTER_INDEX.md

def test_sync_user_curated_still_preserved():
    """Files dropped directly into _nest_context/ should still work as before."""
    # 1. Init project
    # 2. Create _nest_context/custom.txt directly (user-curated)
    # 3. Run nest sync
    # 4. Assert _nest_context/custom.txt still exists
    # 5. Assert custom.txt appears in 00_MASTER_INDEX.md
```

## Tasks / Subtasks

### Task 1: Introduce ALL_SOURCE_EXTENSIONS Constant (AC: 1)
- [x] 1.1: Add `ALL_SOURCE_EXTENSIONS` to `src/nest/core/paths.py` that combines `SUPPORTED_EXTENSIONS` and `CONTEXT_TEXT_EXTENSIONS` (deduplicated)
  ```python
  # All file extensions recognized in _nest_sources/ (Docling-convertible + passthrough text)
  ALL_SOURCE_EXTENSIONS = sorted(set(SUPPORTED_EXTENSIONS + CONTEXT_TEXT_EXTENSIONS))
  ```
- [x] 1.2: Add helper function `is_passthrough_extension(suffix: str) -> bool` to `core/paths.py`:
  ```python
  def is_passthrough_extension(suffix: str) -> bool:
      """Check if file extension should be passthrough-copied (not Docling-converted)."""
      return suffix.lower() in {ext.lower() for ext in CONTEXT_TEXT_EXTENSIONS}
  ```

### Task 2: Update Discovery Service (AC: 1)
- [x] 2.1: In `src/nest/services/discovery_service.py`, change `SUPPORTED_EXTENSIONS` import to `ALL_SOURCE_EXTENSIONS`
- [x] 2.2: Update `discover_changes()` to use `ALL_SOURCE_EXTENSIONS` for file discovery
- [x] 2.3: Update docstring to reflect that both Docling-convertible and passthrough text files are discovered

### Task 3: Add Passthrough Copy Logic (AC: 2, 3, 4)
- [x] 3.1: Create `src/nest/adapters/passthrough_processor.py` implementing `DocumentProcessorProtocol`:
  ```python
  class PassthroughProcessor:
      """Copies text files without conversion, preserving original content and extension."""
      
      def process(self, source: Path, output: Path) -> ProcessingResult:
          """Copy source file to output location."""
          # Create parent directories if needed
          output.parent.mkdir(parents=True, exist_ok=True)
          # Copy file content
          shutil.copy2(source, output)
          return ProcessingResult(
              source_path=source,
              status="success",
              output_path=output,
          )
  ```
- [x] 3.2: Update `mirror_path()` in `core/paths.py` or add a `passthrough_mirror_path()` that preserves the original extension instead of converting to `.md`:
  ```python
  def passthrough_mirror_path(source: Path, source_root: Path, target_root: Path) -> Path:
      """Compute mirrored output path preserving original extension."""
      relative = source.relative_to(source_root)
      return target_root / relative
  ```

### Task 4: Route Files by Extension in Sync Pipeline (AC: 2, 7)
- [x] 4.1: Update `OutputMirrorService.process_file()` or `SyncService.sync()` to route by extension:
  - If `is_passthrough_extension(file.suffix)`: use `PassthroughProcessor` + `passthrough_mirror_path()`
  - Else: use existing Docling `DocumentProcessorProtocol` + `mirror_path()`
- [x] 4.2: Implementation approach — inject `PassthroughProcessor` into `OutputMirrorService` (or create a routing wrapper):
  ```python
  class OutputMirrorService:
      def __init__(self, filesystem, processor, passthrough_processor):
          ...
      
      def process_file(self, source, raw_dir, output_dir):
          if is_passthrough_extension(source.suffix):
              output_path = passthrough_mirror_path(source, raw_dir, output_dir)
              return self._passthrough.process(source, output_path)
          else:
              output_path = self._filesystem.compute_output_path(source, raw_dir, output_dir)
              return self._processor.process(source, output_path)
  ```

### Task 5: Name Collision Detection (AC: 7)
- [x] 5.1: Before processing the file list, build a map of `output_path → source_path` and detect collisions
- [x] 5.2: When a passthrough text file and a Docling-convertible file would produce the same output path (e.g., `report.md` from both `report.md` source and `report.pdf` conversion):
  - The passthrough file wins
  - The Docling-convertible file is skipped with a warning log
  - The skipped file is recorded in manifest with `status: "skipped"`, error explaining the collision
- [x] 5.3: Add collision detection either as a pre-processing step in `SyncService.sync()` or in `OutputMirrorService`

### Task 6: Update Status Service (AC: 9)
- [x] 6.1: Verify `status_service.py` source-file scanning uses `ALL_SOURCE_EXTENSIONS` (or update if it uses `SUPPORTED_EXTENSIONS`)
- [x] 6.2: Ensure source file counts include both Docling and passthrough types

### Task 7: Update Dry Run (AC: 8)
- [x] 7.1: Verify dry run counts include passthrough files (should work automatically via discovery change)
- [x] 7.2: Update dry run display text if it mentions "documents" to also say "text files"

### Task 8: Wire Up CLI Factory (AC: 2, 4)
- [x] 8.1: Update the CLI command factory/wiring (wherever `OutputMirrorService` and `DiscoveryService` are constructed) to:
  - Inject `PassthroughProcessor` into `OutputMirrorService`
  - Use `ALL_SOURCE_EXTENSIONS` in discovery

### Task 9: Update Agent Template (AC: 2)
- [x] 9.1: Update `src/nest/agents/templates/vscode.md.jinja` to tell users they can place all files (including text) in `_nest_sources/`

### Task 10: Unit Tests (AC: 1–12)
- [x] 10.1: Test `ALL_SOURCE_EXTENSIONS` contains all expected extensions (union of both lists)
- [x] 10.2: Test `is_passthrough_extension()` returns True for text extensions, False for Docling extensions
- [x] 10.3: Test `passthrough_mirror_path()` preserves original extension
- [x] 10.4: Test `PassthroughProcessor` copies file content accurately
- [x] 10.5: Test `PassthroughProcessor` creates parent directories
- [x] 10.6: Test discovery service finds `.txt`, `.yaml`, `.md` files in sources
- [x] 10.7: Test `OutputMirrorService` routes passthrough files to `PassthroughProcessor`
- [x] 10.8: Test `OutputMirrorService` routes `.pdf` files to Docling processor
- [x] 10.9: Test collision detection: passthrough wins over Docling when output paths collide
- [x] 10.10: Test passthrough files get manifest entries with `status: "success"`
- [x] 10.11: Test orphan cleanup removes passthrough-origin files when source is deleted

### Task 11: E2E Tests (AC: 1–12)
- [x] 11.1: Add `test_sync_passthrough_txt_file()` 
- [x] 11.2: Add `test_sync_passthrough_yaml_file()`
- [x] 11.3: Add `test_sync_passthrough_preserves_subdirectory()`
- [x] 11.4: Add `test_sync_passthrough_incremental_skip()`
- [x] 11.5: Add `test_sync_passthrough_orphan_cleanup()`
- [x] 11.6: Add `test_sync_passthrough_ignores_binary()`
- [x] 11.7: Add `test_sync_user_curated_still_preserved()`

### Task 12: Run Full Test Suite (AC: 12)
- [x] 12.1: Run `pytest -m "not e2e"` — all pass
- [x] 12.2: Run `pytest -m "e2e"` — all pass
- [x] 12.3: Run `ruff check` — clean
- [x] 12.4: Run `pyright` — 0 errors

## Dev Notes

### Critical Implementation Details

**Routing Logic is the Core Change:**
The sync pipeline already processes files one-by-one via `OutputMirrorService.process_file()`. The key change is checking `is_passthrough_extension()` to decide: copy vs. Docling-convert. This keeps the change surgical.

**Passthrough Mirror Path:**
The existing `mirror_path()` function forces `.md` suffix (`new_suffix=".md"`). Passthrough files must keep their original extension. Add a new `passthrough_mirror_path()` or pass `new_suffix=source.suffix` — whichever is cleaner.

**Manifest Key Format:**
Manifest keys are relative to `_nest_sources/` (e.g., `notes.txt`, `team/meeting.md`). This doesn't change. The `output` field changes: for passthrough files, it will be `notes.txt` instead of `notes.md`. The orphan detector uses this mapping, so orphan cleanup works for free.

**No Double-Processing:**
If a user puts `notes.txt` in BOTH `_nest_sources/` and `_nest_context/`, the sync-originated copy is manifest-tracked and the direct drop is user-curated. If they have identical content this is harmless (two entries in the index). This edge case doesn't need special handling — document it in the agent template.

**File Collision Strategy:**
The only realistic collision scenario is `report.md` (passthrough) vs `report.pdf` → `report.md` (Docling output). Passthrough wins because it represents the user's explicit intent. The Docling file is skipped with a warning. This must be checked BEFORE processing begins (pre-scan the file list, build output path set, flag collisions).

**Backward Compatibility:**
User-curated files directly in `_nest_context/` remain fully supported. The orphan service's `count_user_curated_files()` continues to work because it specifically excludes manifest-tracked files. Passthrough-copied files WILL be in the manifest, so they won't be double-counted as user-curated.

### File Impact Summary

| Category | File | Change Type |
|----------|------|-------------|
| `src/nest/core/paths.py` | Add `ALL_SOURCE_EXTENSIONS`, `is_passthrough_extension()`, `passthrough_mirror_path()` | Add constants + functions |
| `src/nest/adapters/passthrough_processor.py` | New — passthrough file copier | New file |
| `src/nest/services/discovery_service.py` | Use `ALL_SOURCE_EXTENSIONS` | Change import + usage |
| `src/nest/services/output_service.py` | Route by extension (passthrough vs Docling) | Add routing logic |
| `src/nest/services/sync_service.py` | Collision detection pre-scan | Add pre-processing step |
| `src/nest/services/status_service.py` | Verify source counts use all extensions | Verify/update |
| `src/nest/cli/` (factory/wiring) | Inject `PassthroughProcessor` | Update wiring |
| `src/nest/agents/templates/vscode.md.jinja` | Update user instructions | Update text |
| `tests/` | ~8-12 files | Add/update tests |
| **Total** | **~12-15 files** | |

### Estimated Effort

Medium story — the core routing change is small, but wiring the passthrough processor through the DI layer, adding collision detection, and comprehensive testing make this a full story. No architectural changes — this extends the existing pipeline.

### Dependencies

- **Story 2.11 (done):** `CONTEXT_TEXT_EXTENSIONS` constant — reused directly
- **Story 2.1 (done):** Checksum engine — works as-is for text files
- **Story 2.3 (done):** Output mirroring — extended with passthrough routing
- **Story 2.4 (done):** Manifest tracking — works as-is (key format unchanged)
- **Story 2.6 (done):** Orphan cleanup — works as-is (manifest-based detection)

### References

- [Source: Architecture — Layered Architecture] — Service → Adapter routing pattern
- [Source: Architecture — DI Pattern] — Protocol-based processor injection
- [Source: Epics Story 2.11] — `CONTEXT_TEXT_EXTENSIONS` constant (predecessor)
- [Source: Epics Story 2.1] — Discovery + checksum engine
- [Source: Epics Story 2.3] — Output mirroring service pattern
- [Source: PRD Section 4.2] — Sync pipeline steps

## Change Log

- 2026-02-21: Story created from party-mode discussion — unified source folder via text file passthrough in sync pipeline.
- 2026-02-26: Implementation complete — all tasks done, all tests passing.
- 2026-02-26: Code review complete — fixed 4 issues: pre-computed passthrough set, same-type collision warning, added E2E collision test (AC7), added E2E force+passthrough test (AC10). Noted out-of-scope changes (README, init_service, uv.lock) for separate handling.

## Dev Agent Record

### Implementation Summary

Implemented unified source folder support via text file passthrough in the sync pipeline. Users can now drop ALL files into `_nest_sources/` — text files are copied as-is, Docling-convertible files are converted to Markdown.

### Key Implementation Decisions

1. **Passthrough routing in OutputMirrorService**: Added optional `passthrough_processor` parameter (backward compatible — defaults to `None`). Routes by `is_passthrough_extension()` check.
2. **Collision detection via `_resolve_collisions()`**: Pre-scan in `SyncService.sync()` builds output path map, passthrough wins over Docling when output paths collide. Skipped files recorded in manifest with `status: "skipped"`.
3. **Defensive `ValueError` handling**: Collision detection gracefully handles files whose paths can't be made relative to `raw_inbox` (avoids breaking existing unit tests with mock paths).
4. **`DiscoveredFile.collision_reason` field**: Added optional field to carry collision context from detection to manifest recording.
5. **`ManifestService.record_skipped()`**: New method for recording collision-skipped files with `status: "skipped"` and reason.
6. **Updated negative E2E test**: Changed `test_sync_ignores_unsupported_file_types` from testing `.txt` (now supported) to `.png` (truly unsupported binary format).

### Tests Created

- `tests/core/test_paths.py` — `TestAllSourceExtensions` (5 tests), `TestIsPassthroughExtension` (4 tests), `TestPassthroughMirrorPath` (5 tests)
- `tests/adapters/test_passthrough_processor.py` — `TestPassthroughProcessor` (9 tests)
- `tests/services/test_output_service.py` — `TestOutputMirrorServicePassthrough` (7 tests)
- `tests/services/test_discovery_service.py` — `TestDiscoveryServiceTextFiles` (4 tests)
- `tests/services/test_sync_service.py` — `TestSyncCollisionDetection` (2 tests)
- `tests/e2e/test_sync_e2e.py` — `TestSyncPassthroughE2E` (9 tests, +2 from code review: collision + force)

### Code Review Fixes Applied

1. **M3 — Pre-computed passthrough set**: `is_passthrough_extension()` now uses module-level `_PASSTHROUGH_EXTENSIONS` frozenset instead of creating set per call.
2. **M4 — Same-type collision warning**: `_resolve_collisions()` now logs a warning when two files of the same type produce the same output path.
3. **M1 — E2E collision test (AC7)**: Added `test_sync_passthrough_collision_passthrough_wins` — validates passthrough wins end-to-end.
4. **M2 — E2E force+passthrough test (AC10)**: Added `test_sync_passthrough_force_recopies` — validates `--force` reprocesses unchanged passthrough files.
5. **H1 — Out-of-scope changes noted**: `README.md`, `init_service.py`, `test_init_service.py`, `uv.lock` are in git diff but not part of this story. Flagged for separate handling.

### Test Results

- `pytest -m "not e2e"`: 579 passed
- `pytest -m "e2e"`: 43 passed
- `ruff check src/`: 0 errors (1 pre-existing in test file)
- `pyright src/`: 0 errors, 0 warnings

## File List

| File | Change |
|------|--------|
| `src/nest/core/paths.py` | Added `ALL_SOURCE_EXTENSIONS`, `is_passthrough_extension()`, `passthrough_mirror_path()` |
| `src/nest/core/models.py` | Added `collision_reason` field to `DiscoveredFile` |
| `src/nest/adapters/passthrough_processor.py` | **New** — passthrough file copier |
| `src/nest/services/discovery_service.py` | Changed to use `ALL_SOURCE_EXTENSIONS` |
| `src/nest/services/output_service.py` | Added passthrough routing via `is_passthrough_extension()` |
| `src/nest/services/sync_service.py` | Added `_resolve_collisions()` pre-scan + collision manifest recording |
| `src/nest/services/manifest_service.py` | Added `record_skipped()` method |
| `src/nest/services/status_service.py` | Changed to use `ALL_SOURCE_EXTENSIONS` |
| `src/nest/cli/sync_cmd.py` | Wired `PassthroughProcessor` into `OutputMirrorService` |
| `src/nest/agents/templates/vscode.md.jinja` | Updated user instructions for unified source folder |
| `tests/core/test_paths.py` | Added 14 tests for new constants/functions |
| `tests/adapters/test_passthrough_processor.py` | **New** — 9 tests |
| `tests/services/test_output_service.py` | Added 7 passthrough routing tests |
| `tests/services/test_discovery_service.py` | Added 4 text file discovery tests |
| `tests/services/test_sync_service.py` | Added 2 collision detection tests |
| `tests/e2e/test_sync_e2e.py` | Added 9 passthrough E2E tests (7 original + 2 from code review) |
| `tests/e2e/test_negative_e2e.py` | Updated unsupported file type test (.txt → .png) |

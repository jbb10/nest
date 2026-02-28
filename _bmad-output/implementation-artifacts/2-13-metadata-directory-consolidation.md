# Story 2.13: Metadata Directory Consolidation (`.nest/`)

Status: in-progress
Branch: feat/2-13-metadata-directory-consolidation

## Story

As a **user managing a Nest project**,
I want **all Nest metadata files to live in a single `.nest/` directory instead of being scattered across the project root and mixed into `_nest_context/`**,
So that **my project root stays clean, my context folder contains only actual content, and I only need one `.gitignore` entry for all Nest internals**.

## Business Context

The current Nest project layout scatters internal metadata across multiple locations:

- **`.nest_manifest.json`** sits at the project root — visible noise alongside the user's own files
- **`.nest_errors.log`** sits at the project root — another dotfile cluttering `ls` output
- **`00_MASTER_INDEX.md`** lives inside `_nest_context/` — mixing system-generated metadata with actual content the AI agent should read
- Future stories (5.1, 5.2) plan to add `00_INDEX_HINTS.yaml` and `00_GLOSSARY_HINTS.yaml` to `_nest_context/` — more metadata pollution

This creates three problems:
1. **Root clutter:** Users see Nest internals in their project root and must `.gitignore` each one individually
2. **Context pollution:** `_nest_context/` contains metadata files that require special-case exclusion logic in orphan detection, index generation, and status counting
3. **Cognitive overhead:** Users must understand which dotfiles belong to Nest vs their own project

The fix: consolidate all Nest metadata into a single `.nest/` directory — the same pattern used by `.git/`, `.venv/`, and `.vscode/`. One folder to rule them all, one `.gitignore` entry to ignore them.

### Key Insight

Moving metadata into `.nest/` **eliminates special-case code** throughout the codebase. Currently, `orphan_detector.py`, `index_service.py`, `status_service.py`, and `orphan_service.py` all contain logic to skip `00_MASTER_INDEX.md` (and will need more exclusions for hints files). With the index and hints in `.nest/`, these exclusions vanish — `_nest_context/` becomes purely user content and processed output.

## Project Layout — Before & After

### Before (current + planned Stories 5.1/5.2)

```
project/
├── .nest_manifest.json           ← metadata at root
├── .nest_errors.log              ← metadata at root
├── _nest_sources/
│   └── ...
├── _nest_context/
│   ├── 00_MASTER_INDEX.md        ← metadata mixed with content
│   ├── 00_INDEX_HINTS.yaml       ← (planned 5.1) metadata mixed with content
│   ├── 00_GLOSSARY_HINTS.yaml    ← (planned 5.2) metadata mixed with content
│   ├── contracts/alpha.md        ← actual content
│   └── ...
├── .github/agents/
│   ├── nest.agent.md
│   ├── nest-enricher.agent.md    ← (planned 5.1)
│   └── nest-glossary.agent.md   ← (planned 5.2)
└── .gitignore                    ← must list each Nest file individually
```

### After (this story)

```
project/
├── .nest/                        ← ALL metadata consolidated here
│   ├── manifest.json             ← was .nest_manifest.json
│   ├── errors.log                ← was .nest_errors.log
│   └── 00_MASTER_INDEX.md        ← was in _nest_context/
├── _nest_sources/
│   └── ...
├── _nest_context/                ← now PURE content — no metadata
│   ├── contracts/alpha.md
│   └── ...
├── .github/agents/
│   ├── nest.agent.md
│   └── ...
└── .gitignore                    ← just needs: .nest/
```

**Future-proof:** When Stories 5.1 and 5.2 are implemented, their hints files (`00_INDEX_HINTS.yaml`, `00_GLOSSARY_HINTS.yaml`) go directly into `.nest/` — no code changes needed for exclusion logic since they never touch `_nest_context/`.

## Acceptance Criteria

### AC1: `.nest/` Directory Created on Init

**Given** I run `nest init "ProjectName"` in a fresh directory
**When** the command completes
**Then** a `.nest/` directory is created
**And** `.nest/manifest.json` is created (not `.nest_manifest.json` at root)
**And** the manifest contains the standard structure (`nest_version`, `project_name`, `last_sync`, `files`)
**And** `_nest_sources/` and `_nest_context/` are still created at root (unchanged)
**And** `.github/agents/` is still created (unchanged)

### AC2: Manifest Lives in `.nest/`

**Given** a Nest project has been initialized
**When** any command reads or writes the manifest
**Then** the manifest path is `.nest/manifest.json` (not `.nest_manifest.json` at project root)
**And** the filename constant is `manifest.json` (not `.nest_manifest.json`)

### AC3: Error Log Lives in `.nest/`

**Given** `nest sync` encounters processing errors
**When** errors are logged
**Then** the error log is written to `.nest/errors.log` (not `.nest_errors.log` at project root)
**And** the default error log path references `.nest/errors.log`

### AC4: Master Index Lives in `.nest/`

**Given** `nest sync` completes and index generation runs
**When** `00_MASTER_INDEX.md` is written
**Then** it is written to `.nest/00_MASTER_INDEX.md` (not `_nest_context/00_MASTER_INDEX.md`)
**And** the index content is unchanged (same file listing format)

### AC5: Index Exclusion Logic Removed

**Given** `00_MASTER_INDEX.md` no longer lives in `_nest_context/`
**When** orphan detection, index generation, and status counting scan `_nest_context/`
**Then** there is NO special-case code to skip or exclude `00_MASTER_INDEX.md`
**And** the `if relative == MASTER_INDEX_FILE` checks in `orphan_detector.py`, `orphan_service.py`, and `status_service.py` are removed
**And** the `if relative != MASTER_INDEX_FILE` check in `index_service.py` is removed

### AC6: Agent Template Updated

**Given** the VS Code agent template references the index location
**When** `nest init` generates the agent file
**Then** the agent instructions reference `.nest/00_MASTER_INDEX.md` as the index location
**And** the agent instructions list `.nest/` as a system directory (not to be modified by users)
**And** references to `.nest_manifest.json` and `.nest_errors.log` are updated to use `.nest/` paths

### AC7: Doctor Validates `.nest/` Directory

**Given** the user runs `nest doctor` in a Nest project
**When** project validation runs
**Then** the check validates that `.nest/` directory exists
**And** if `.nest/` is missing, it is reported as an issue: "`.nest/` metadata directory missing"
**And** if old-layout files are detected (`.nest_manifest.json` at root), it is reported: "Legacy layout detected — run `nest update` to migrate"

### AC8: Doctor `--fix` Migrates Legacy Layout

**Given** the user runs `nest doctor --fix` in a project with old-layout files
**When** legacy layout is detected
**Then** `.nest/` directory is created
**And** `.nest_manifest.json` is moved to `.nest/manifest.json`
**And** `.nest_errors.log` is moved to `.nest/errors.log` (if exists)
**And** `_nest_context/00_MASTER_INDEX.md` is moved to `.nest/00_MASTER_INDEX.md` (if exists)
**And** `_nest_context/00_INDEX_HINTS.yaml` is moved to `.nest/00_INDEX_HINTS.yaml` (if exists — future-proofing for Story 5.1)
**And** `_nest_context/00_GLOSSARY_HINTS.yaml` is moved to `.nest/00_GLOSSARY_HINTS.yaml` (if exists — future-proofing for Story 5.2)
**And** a success message is shown for each file migrated
**And** the old files no longer exist at their original locations

### AC9: `nest update` Triggers Migration Automatically

**Given** a user runs `nest update` and a new version is installed
**When** the post-update checks run (after agent migration check)
**Then** if old-layout files are detected in the project directory:
  - `.nest/` is created
  - All metadata files are moved to `.nest/` (same list as AC8)
  - A summary message is shown: "Migrated metadata to .nest/ directory"
**And** if the project already uses `.nest/` layout, migration is silently skipped
**And** migration runs regardless of whether the user accepted/declined agent migration

### AC10: Migration Is Idempotent

**Given** migration has already been performed
**When** `nest update` or `nest doctor --fix` runs again
**Then** no files are moved (nothing to migrate)
**And** no errors or warnings are emitted
**And** the `.nest/` directory and its contents are preserved

### AC11: Partial Migration Handled Gracefully

**Given** a project has some old-layout files but not others (e.g., `.nest_manifest.json` exists but `.nest_errors.log` does not)
**When** migration runs
**Then** only existing files are moved
**And** missing files are silently skipped (not reported as errors)
**And** `.nest/` is still created even if only one file needs to move

### AC12: `.gitignore` Updated During Init

**Given** `nest init` creates a new project
**When** `.gitignore` is updated/created
**Then** `.nest/` is added (covering manifest, errors log, and index)
**And** `_nest_sources/` is added (unchanged from current behavior)
**And** individual entries like `.nest_manifest.json` or `.nest_errors.log` are NOT added

### AC13: `.gitignore` Updated During Migration

**Given** migration runs on an existing project
**When** `.gitignore` exists and contains old entries (`.nest_manifest.json`, `.nest_errors.log`)
**Then** the old entries are removed
**And** `.nest/` is added if not already present
**And** other `.gitignore` entries are preserved
**And** if `.gitignore` does not exist, it is created with `.nest/` and `_nest_sources/`

### AC14: Existing `nest sync` Detection Updated

**Given** a Nest project exists with `.nest/manifest.json`
**When** the user runs `nest init` in the same directory
**Then** the "already exists" check detects `.nest/manifest.json`
**And** the error message says: "Nest project already exists. Use `nest sync` to process documents."

### AC15: All Existing Tests Pass

**Given** all unit, integration, and E2E tests
**When** the changes are complete
**Then** all tests pass with no regressions

## E2E Testing Requirements

- [ ] Existing E2E tests cover this story's functionality: Partially — init/sync E2E tests exist but use old paths
- [ ] New E2E tests required: Yes — migration scenarios
- [ ] E2E test execution required for story completion: Yes — all E2E tests must pass

**New E2E Tests Needed:**
```python
def test_init_creates_nest_metadata_dir():
    """nest init should create .nest/ with manifest.json inside."""
    # 1. Run nest init "Test"
    # 2. Assert .nest/ directory exists
    # 3. Assert .nest/manifest.json exists with valid JSON
    # 4. Assert .nest_manifest.json does NOT exist at project root

def test_sync_writes_index_to_nest_dir():
    """After sync, 00_MASTER_INDEX.md should be in .nest/ not _nest_context/."""
    # 1. Init project, add a source file
    # 2. Run nest sync
    # 3. Assert .nest/00_MASTER_INDEX.md exists
    # 4. Assert _nest_context/00_MASTER_INDEX.md does NOT exist

def test_sync_writes_errors_to_nest_dir():
    """Sync errors should be logged to .nest/errors.log."""
    # 1. Init project, add an invalid/corrupt source file
    # 2. Run nest sync
    # 3. Assert .nest/errors.log exists
    # 4. Assert .nest_errors.log does NOT exist at project root

def test_context_dir_has_no_metadata():
    """_nest_context/ should contain only processed content, no system files."""
    # 1. Init project, add source files, run sync
    # 2. List all files in _nest_context/
    # 3. Assert no file named 00_MASTER_INDEX.md
    # 4. Assert no file named 00_INDEX_HINTS.yaml
    # 5. Assert no file named 00_GLOSSARY_HINTS.yaml

def test_migration_from_legacy_layout():
    """nest update migration should move files from old to new locations."""
    # 1. Init project using OLD layout (manually create .nest_manifest.json at root)
    # 2. Create .nest_errors.log at root
    # 3. Create _nest_context/00_MASTER_INDEX.md
    # 4. Run migration logic
    # 5. Assert .nest/manifest.json exists
    # 6. Assert .nest/errors.log exists
    # 7. Assert .nest/00_MASTER_INDEX.md exists
    # 8. Assert old files no longer exist

def test_migration_idempotent():
    """Running migration twice should not cause errors."""
    # 1. Create legacy layout, run migration
    # 2. Run migration again
    # 3. Assert no errors, .nest/ contents unchanged

def test_migration_partial():
    """Migration should handle projects with only some old files."""
    # 1. Create only .nest_manifest.json (no error log, no index)
    # 2. Run migration
    # 3. Assert .nest/manifest.json exists
    # 4. Assert no errors for missing .nest_errors.log

def test_doctor_detects_legacy_layout():
    """Doctor should report legacy layout as an issue."""
    # 1. Create project with .nest_manifest.json at root
    # 2. Run nest doctor
    # 3. Assert output contains "Legacy layout detected"

def test_gitignore_uses_nest_dir():
    """Init should add .nest/ to gitignore, not individual files."""
    # 1. Run nest init "Test"
    # 2. Read .gitignore
    # 3. Assert ".nest/" is present
    # 4. Assert ".nest_manifest.json" is NOT present
```

## Tasks / Subtasks

### Task 1: Add `.nest/` Constants to `core/paths.py` (AC: 1, 2, 3, 4)
- [ ] 1.1: Add `NEST_META_DIR = ".nest"` constant
- [ ] 1.2: Change `MANIFEST_FILENAME` from `".nest_manifest.json"` to `"manifest.json"` (**Note:** This constant currently lives in `adapters/manifest.py` — move it to `core/paths.py` for consistency with other path constants)
- [ ] 1.3: Add `ERROR_LOG_FILENAME = "errors.log"` constant
- [ ] 1.4: `MASTER_INDEX_FILE = "00_MASTER_INDEX.md"` remains unchanged (just the directory it's written to changes)

### Task 2: Update ManifestAdapter (AC: 2, 14)
- [ ] 2.1: Update `src/nest/adapters/manifest.py` to import `NEST_META_DIR` and use `MANIFEST_FILENAME` from `core/paths.py`
- [ ] 2.2: Change manifest path construction from `project_dir / MANIFEST_FILENAME` to `project_dir / NEST_META_DIR / MANIFEST_FILENAME`
- [ ] 2.3: Update `exists()`, `create()`, `load()`, `save()` methods with new path
- [ ] 2.4: When creating initial manifest, ensure `.nest/` directory exists first (`mkdir(parents=True, exist_ok=True)`)
- [ ] 2.5: Update all docstrings referencing `.nest_manifest.json` → `.nest/manifest.json`

### Task 3: Update Error Logger (AC: 3)
- [ ] 3.1: Update `src/nest/ui/logger.py` default path from `Path(".nest_errors.log")` to `Path(NEST_META_DIR) / ERROR_LOG_FILENAME`
- [ ] 3.2: Update `src/nest/adapters/docling_processor.py` `DEFAULT_ERROR_LOG` from `Path(".nest_errors.log")` to `Path(NEST_META_DIR) / ERROR_LOG_FILENAME`
- [ ] 3.3: Update `src/nest/cli/sync_cmd.py` error log path construction: `project_root / NEST_META_DIR / ERROR_LOG_FILENAME`
- [ ] 3.4: Ensure `.nest/` directory exists before opening log file for writing

### Task 4: Update IndexService (AC: 4, 5)
- [ ] 4.1: Update `src/nest/services/index_service.py` to write index to `.nest/` directory instead of `_nest_context/`
  - Change from `self._context_dir / MASTER_INDEX_FILE` to `self._meta_dir / MASTER_INDEX_FILE`
  - Constructor needs to accept `meta_dir: Path` parameter
- [ ] 4.2: Remove the `if relative != MASTER_INDEX_FILE` exclusion in file scanning — no longer needed since the index is not in `_nest_context/`

### Task 5: Remove Index Exclusion Special Cases (AC: 5)
- [ ] 5.1: In `src/nest/core/orphan_detector.py`: Remove `if relative == "00_MASTER_INDEX.md": continue` check
- [ ] 5.2: In `src/nest/services/orphan_service.py`: Remove `if relative == MASTER_INDEX_FILE` exclusion
- [ ] 5.3: In `src/nest/services/status_service.py`: Remove `if rel == MASTER_INDEX_FILE` skip logic
- [ ] 5.4: Verify no other files contain index exclusion logic

### Task 6: Update InitService (AC: 1, 12)
- [ ] 6.1: Update `src/nest/services/init_service.py` `INIT_DIRECTORIES` to include `NEST_META_DIR`:
  ```python
  INIT_DIRECTORIES = [
      SOURCES_DIR,
      CONTEXT_DIR,
      NEST_META_DIR,
      ".github/agents",
  ]
  ```
- [ ] 6.2: Add `.gitignore` creation/update logic to `InitService.execute()`:
  - If `.gitignore` exists: append `.nest/` and `_nest_sources/` if not already present
  - If `.gitignore` does not exist: create with:
    ```
    # Nest - source documents (private/confidential)
    _nest_sources/
    # Nest - internal metadata
    .nest/
    ```

### Task 7: Update ProjectChecker (AC: 7)
- [ ] 7.1: Add `meta_folder_exists(project_dir: Path) -> bool` to `src/nest/adapters/project_checker.py`
- [ ] 7.2: Add `has_legacy_layout(project_dir: Path) -> bool` — returns True if `.nest_manifest.json` exists at root (old layout indicator)
- [ ] 7.3: Update `manifest_exists()` to check `.nest/manifest.json` path
- [ ] 7.4: Add both methods to `ProjectCheckerProtocol` in `adapters/protocols.py`

### Task 8: Create Migration Service (AC: 8, 9, 10, 11, 13)
- [ ] 8.1: Create `src/nest/services/migration_service.py` with `MetadataMigrationService` class
- [ ] 8.2: Implement `detect_legacy_layout(project_dir: Path) -> bool`:
  - Returns True if `.nest_manifest.json` exists at `project_dir` root
- [ ] 8.3: Implement `migrate(project_dir: Path) -> MigrationResult`:
  ```python
  @dataclass
  class MigrationResult:
      migrated: bool           # True if any files were moved
      files_moved: list[str]   # Human-readable list of what moved
      errors: list[str]        # Any failures
  ```
  Migration steps:
  1. Create `.nest/` directory (`mkdir(parents=True, exist_ok=True)`)
  2. Move each file if it exists at old location:
     - `.nest_manifest.json` → `.nest/manifest.json`
     - `.nest_errors.log` → `.nest/errors.log`
     - `_nest_context/00_MASTER_INDEX.md` → `.nest/00_MASTER_INDEX.md`
     - `_nest_context/00_INDEX_HINTS.yaml` → `.nest/00_INDEX_HINTS.yaml` (future-proof for 5.1)
     - `_nest_context/00_GLOSSARY_HINTS.yaml` → `.nest/00_GLOSSARY_HINTS.yaml` (future-proof for 5.2)
  3. Update `.gitignore`: remove old entries, add `.nest/` if not present
  4. Return result summary
- [ ] 8.4: Implement graceful error handling: if a file move fails (permissions, locked), log warning, continue with remaining files, report failure in result
- [ ] 8.5: Ensure idempotence: if `.nest/manifest.json` already exists and `.nest_manifest.json` does not, skip silently. Never overwrite existing `.nest/` files.

### Task 9: Add MigrationResult Model (AC: 8, 9)
- [ ] 9.1: Add `MigrationResult` to `src/nest/core/models.py`:
  ```python
  class MigrationResult(BaseModel):
      migrated: bool = False
      files_moved: list[str] = []
      errors: list[str] = []
  ```

### Task 10: Wire Migration into `nest update` (AC: 9)
- [ ] 10.1: In `src/nest/cli/update_cmd.py`, add `_handle_metadata_migration()` function:
  ```python
  def _handle_metadata_migration(
      project_dir: Path,
      console: Console,
  ) -> None:
      """Migrate old-layout metadata files to .nest/ directory."""
      migration_service = MetadataMigrationService()
      
      if not migration_service.detect_legacy_layout(project_dir):
          return  # Already new layout or not a Nest project
      
      result = migration_service.migrate(project_dir)
      
      if result.migrated:
          for item in result.files_moved:
              info(item)
          success("Migrated metadata to .nest/ directory")
      
      if result.errors:
          for err in result.errors:
              warning(err)
  ```
- [ ] 10.2: Call `_handle_metadata_migration()` after `_handle_agent_migration()` in the successful update flow
- [ ] 10.3: Use `target_dir or Path.cwd()` for project directory (same as agent migration)

### Task 11: Wire Migration into `nest doctor` (AC: 7, 8)
- [ ] 11.1: Update `_count_issues()` in `src/nest/cli/doctor_cmd.py`:
  - If `.nest/` directory missing (and project is a nest project): add issue "`.nest/` metadata directory missing"
  - If legacy layout detected: add issue "Legacy layout detected — run `nest update` to migrate"
- [ ] 11.2: Update `_is_nest_project()` to also check for `.nest/manifest.json`
- [ ] 11.3: Wire `MetadataMigrationService` into doctor remediation (`--fix` and interactive modes)
- [ ] 11.4: Update `display_doctor_report()` to show `.nest/` status

### Task 12: Update Agent Template (AC: 6)
- [ ] 12.1: Update `src/nest/agents/templates/vscode.md.jinja`:
  - Change index reference: "Always begin by reading `.nest/00_MASTER_INDEX.md`"
  - Update "Stay Focused" rule: "Never read `_nest_sources/` (raw documents) or `.nest/` (system metadata)"
  - Remove references to `.nest_manifest.json` and `.nest_errors.log`

### Task 13: Update CLI User-Facing Messages (AC: 14)
- [ ] 13.1: In `src/nest/cli/init_cmd.py`: Update "already exists" message from `.nest_manifest.json` → `.nest/manifest.json`
- [ ] 13.2: In `src/nest/cli/sync_cmd.py`: Update manifest-not-found message
- [ ] 13.3: In `src/nest/cli/sync_cmd.py`: Update error log reference in summary output (`.nest_errors.log` → `.nest/errors.log`)

### Task 14: Unit Tests (AC: 1–15)
- [ ] 14.1: Test `NEST_META_DIR` constant equals `".nest"`
- [ ] 14.2: Test `ManifestAdapter` reads/writes from `.nest/manifest.json`
- [ ] 14.3: Test `ManifestAdapter.exists()` checks `.nest/manifest.json` path
- [ ] 14.4: Test error logger writes to `.nest/errors.log`
- [ ] 14.5: Test `IndexService` writes index to `.nest/00_MASTER_INDEX.md`
- [ ] 14.6: Test `IndexService` no longer skips `MASTER_INDEX_FILE` during context scanning
- [ ] 14.7: Test orphan detector no longer excludes `00_MASTER_INDEX.md`
- [ ] 14.8: Test status service no longer skips `00_MASTER_INDEX.md` in counts
- [ ] 14.9: Test `MetadataMigrationService.detect_legacy_layout()` — True when `.nest_manifest.json` at root
- [ ] 14.10: Test `MetadataMigrationService.detect_legacy_layout()` — False when `.nest/manifest.json` exists
- [ ] 14.11: Test `MetadataMigrationService.migrate()` — moves all existing files
- [ ] 14.12: Test `MetadataMigrationService.migrate()` — skips missing files gracefully
- [ ] 14.13: Test `MetadataMigrationService.migrate()` — idempotent (no-op on second run)
- [ ] 14.14: Test `MetadataMigrationService.migrate()` — updates `.gitignore`
- [ ] 14.15: Test `ProjectChecker.meta_folder_exists()` and `has_legacy_layout()`
- [ ] 14.16: Test `InitService` creates `.nest/` directory
- [ ] 14.17: Test `.gitignore` creation includes `.nest/` and `_nest_sources/`
- [ ] 14.18: Update ALL existing manifest tests to use new `.nest/manifest.json` path
- [ ] 14.19: Update ALL existing index tests to use new `.nest/` path
- [ ] 14.20: Update ALL existing orphan detector tests to remove index exclusion assertions

### Task 15: E2E Tests (AC: 1–15)
- [ ] 15.1: Add `test_init_creates_nest_metadata_dir()`
- [ ] 15.2: Add `test_sync_writes_index_to_nest_dir()`
- [ ] 15.3: Add `test_sync_writes_errors_to_nest_dir()`
- [ ] 15.4: Add `test_context_dir_has_no_metadata()`
- [ ] 15.5: Add `test_migration_from_legacy_layout()`
- [ ] 15.6: Add `test_migration_idempotent()`
- [ ] 15.7: Add `test_migration_partial()`
- [ ] 15.8: Add `test_doctor_detects_legacy_layout()`
- [ ] 15.9: Add `test_gitignore_uses_nest_dir()`
- [ ] 15.10: Update all existing E2E tests for new paths

### Task 16: Run Full Test Suite (AC: 15)
- [ ] 16.1: Run `pytest -m "not e2e"` — all pass
- [ ] 16.2: Run `pytest -m "e2e"` — all pass
- [ ] 16.3: Run `ruff check` — clean
- [ ] 16.4: Run `pyright` — 0 errors

## Dev Notes

### Critical Implementation Details

**Migration File Map (Comprehensive):**

This migration handles ALL metadata files from ALL stories — finished, in-progress, and future:

| Old Location | New Location | From Story | Status |
|---|---|---|---|
| `.nest_manifest.json` | `.nest/manifest.json` | 1.1 (done) | Will exist in all projects |
| `.nest_errors.log` | `.nest/errors.log` | 2.8 (done) | May or may not exist |
| `_nest_context/00_MASTER_INDEX.md` | `.nest/00_MASTER_INDEX.md` | 2.5 (done) | Exists if sync has run |
| `_nest_context/00_INDEX_HINTS.yaml` | `.nest/00_INDEX_HINTS.yaml` | 5.1 (future) | Won't exist yet but handles forward compatibility |
| `_nest_context/00_GLOSSARY_HINTS.yaml` | `.nest/00_GLOSSARY_HINTS.yaml` | 5.2 (future) | Won't exist yet but handles forward compatibility |

**Why future-proof the migration?** A user might:
1. Update to version with 5.1 (hints in `_nest_context/`)
2. Skip a release
3. Update to version with 2.13 (migration to `.nest/`)

The migration must handle this sequence correctly.

**Update Command Flow (After This Story):**

```
nest update
  ├── Check for updates → display versions → prompt
  ├── Execute update via uv
  ├── Post-update checks:
  │   ├── Agent template migration (existing — Story 4.4)
  │   └── Metadata directory migration (NEW — this story)
  └── Done
```

The metadata migration runs AFTER agent migration, regardless of whether the user accepted/declined the agent update. The migration is automatic (no prompt) because it's non-destructive — files are moved, not deleted or modified.

**Manifest Path Construction Pattern:**

Current pattern (scattered):
```python
# In manifest.py
manifest_path = project_dir / MANIFEST_FILENAME  # project_root/.nest_manifest.json

# In sync_cmd.py
error_log_path = project_root / ".nest_errors.log"

# In index_service.py
index_path = self._context_dir / MASTER_INDEX_FILE
```

New pattern (consistent):
```python
# In manifest.py
manifest_path = project_dir / NEST_META_DIR / MANIFEST_FILENAME  # project_root/.nest/manifest.json

# In sync_cmd.py
error_log_path = project_root / NEST_META_DIR / ERROR_LOG_FILENAME

# In index_service.py
index_path = self._meta_dir / MASTER_INDEX_FILE
```

**Index Exclusion Removal — Code Win:**

These special cases get DELETED:

```python
# orphan_detector.py — DELETE THIS:
if relative == "00_MASTER_INDEX.md":
    continue

# index_service.py — DELETE THIS:
if relative != MASTER_INDEX_FILE:

# status_service.py — DELETE THIS:
if rel == MASTER_INDEX_FILE:
    continue

# orphan_service.py — DELETE equivalent check
```

This is the biggest "cleanliness win" of the story — removing 4+ special-case blocks across the codebase.

**`.gitignore` Migration Logic:**

```python
def _update_gitignore(project_dir: Path) -> None:
    gitignore = project_dir / ".gitignore"
    
    # Old entries to remove
    old_entries = {".nest_manifest.json", ".nest_errors.log"}
    # New entries to ensure
    new_entries = [".nest/", "_nest_sources/"]
    
    if gitignore.exists():
        lines = gitignore.read_text().splitlines()
        # Remove old entries
        lines = [l for l in lines if l.strip() not in old_entries]
        # Add new entries if not present
        existing = {l.strip() for l in lines}
        for entry in new_entries:
            if entry not in existing:
                lines.append(entry)
        gitignore.write_text("\n".join(lines) + "\n")
    else:
        content = "# Nest - source documents (private/confidential)\n_nest_sources/\n# Nest - internal metadata\n.nest/\n"
        gitignore.write_text(content)
```

**Stories 5.1 and 5.2 Compatibility:**

When Stories 5.1 and 5.2 are implemented AFTER this story, they should:
- Write `00_INDEX_HINTS.yaml` to `.nest/` (not `_nest_context/`)
- Write `00_GLOSSARY_HINTS.yaml` to `.nest/` (not `_nest_context/`)
- Reference `INDEX_HINTS_FILE` and `GLOSSARY_HINTS_FILE` constants with `NEST_META_DIR` prefix
- NO exclusion logic needed — these files never touch `_nest_context/`

If Stories 5.1/5.2 are implemented BEFORE this story (unlikely given current status), this story's migration handles moving their files.

**Story 2.12 Compatibility:**

Story 2.12 (Unified Source Folder) changes discovery routing and passthrough processing. It does NOT interact with manifest/error/index storage locations. The only shared file is `core/paths.py` where 2.12 adds `ALL_SOURCE_EXTENSIONS` and `is_passthrough_extension()`. This story adds `NEST_META_DIR`, `ERROR_LOG_FILENAME`, and moves `MANIFEST_FILENAME`. No conflicts.

### File Impact Summary

| Category | File | Change Type |
|----------|------|-------------|
| `src/nest/core/paths.py` | Add `NEST_META_DIR`, `ERROR_LOG_FILENAME`; move `MANIFEST_FILENAME` here | Add constants |
| `src/nest/adapters/manifest.py` | Use new path: `.nest/manifest.json` | Change path construction |
| `src/nest/adapters/project_checker.py` | Add `meta_folder_exists()`, `has_legacy_layout()` | Add methods |
| `src/nest/adapters/protocols.py` | Add new protocol methods | Add protocol |
| `src/nest/adapters/docling_processor.py` | Update `DEFAULT_ERROR_LOG` | Change default |
| `src/nest/ui/logger.py` | Update default log path | Change default |
| `src/nest/services/init_service.py` | Add `.nest/` to init dirs, add `.gitignore` logic | Add directory + feature |
| `src/nest/services/index_service.py` | Write index to `.nest/`, remove exclusion | Change path + remove code |
| `src/nest/services/orphan_service.py` | Remove index exclusion | Remove code |
| `src/nest/services/status_service.py` | Remove index skip logic | Remove code |
| `src/nest/services/migration_service.py` | **New** — legacy layout migration | New file |
| `src/nest/core/orphan_detector.py` | Remove index exclusion | Remove code |
| `src/nest/core/models.py` | Add `MigrationResult` | Add model |
| `src/nest/cli/init_cmd.py` | Update error messages | Change strings |
| `src/nest/cli/sync_cmd.py` | Update manifest/error paths | Change path construction |
| `src/nest/cli/update_cmd.py` | Add metadata migration step | Add migration call |
| `src/nest/cli/doctor_cmd.py` | Add legacy detection + migration remediation | Add checks + remediation |
| `src/nest/agents/templates/vscode.md.jinja` | Update path references | Change strings |
| `tests/` | ~15-20 files | Update paths + add migration tests |
| **Total** | **~25-30 files** | |

### Estimated Effort

Medium-Large story — the core change (path consolidation) is straightforward, but the migration service, update integration, doctor integration, and comprehensive test updates across the entire test suite make this a full-sized story. No new architectural patterns — this extends existing DI and service patterns.

### Dependencies

- **Story 2.12 (ready-for-dev):** Should be completed FIRST. Both touch `core/paths.py` but in non-conflicting ways. Completing 2.12 first avoids merge conflicts.
- **Story 2.10 (done):** Folder naming refactor — established the `SOURCES_DIR`/`CONTEXT_DIR` constants pattern that this story extends.
- **Stories 5.1, 5.2 (ready-for-dev):** This story future-proofs for their hints files. If they are implemented after this story, they should write hints to `.nest/` directly. If implemented before, this story's migration handles moving them.

### Ordering Recommendation

**Recommended implementation order:**
1. Story 2.12 (Unified Source Folder) — already `ready-for-dev`
2. **Story 2.13 (this story)** — metadata consolidation
3. Stories 5.1, 5.2 — index enrichment + glossary (these benefit from `.nest/` being in place)

This order means Stories 5.1/5.2 can write directly to `.nest/` from the start, avoiding the need for their files to ever exist in `_nest_context/`.

### References

- [Source: Architecture — Layered Architecture] — Service layer patterns
- [Source: Architecture — DI Pattern] — Protocol-based dependency injection
- [Source: Story 2.10 — Folder Naming Refactor] — Precedent for path constant consolidation
- [Source: Story 5.1 — Index Enrichment Pipeline] — `INDEX_HINTS_FILE` planned for `_nest_context/`
- [Source: Story 5.2 — Glossary Agent Integration] — `GLOSSARY_HINTS_FILE` planned for `_nest_context/`
- [Source: Party Mode Discussion 2026-02-21] — Original proposal for `.nest/` directory

## Change Log

- 2026-02-26: Story created from party-mode discussion. Comprehensive migration logic covers all finished and planned stories. Update command post-update migration ensures seamless upgrade for existing Nest projects.

# Story 10.3: Multi-Agent Migration Service

Status: done

## Story

As a **user running `nest update`**,
I want **the migration check to cover all four agent files (coordinator + 3 subagents)**,
So that **after a version update, all my agent files are kept in sync with the latest templates**.

## Acceptance Criteria

### AC1: Migration Check Covers All Agent Files

**Given** a Nest project with all four agent files
**When** `AgentMigrationService.check_migration_needed()` runs
**Then** it compares ALL four local files against their respective rendered templates
**And** returns `migration_needed=True` if ANY file differs

### AC2: Migration Check Reports Which Files Changed

**Given** migration is needed
**When** the check result is returned
**Then** it includes a list of which specific files are outdated or missing
**And** the `message` field describes the situation (e.g., "2 agent files outdated, 1 missing")

### AC3: Migration Executes on All Changed Files

**Given** `execute_migration()` is called
**When** some agent files are outdated and some are current
**Then** only the outdated/missing files are regenerated
**And** up-to-date files are left untouched

### AC4: No Backup Files Created

**Given** an existing agent file will be overwritten during migration
**When** migration executes
**Then** the file is overwritten directly with the new template content
**And** NO `.bak` backup files are created
**And** `.github/agents/` contains exactly the 4 current agent files after migration (no leftover files)

### AC5: Legacy Single-Agent Upgrade

**Given** a legacy project with only the old generalist `nest.agent.md` (pre-multi-agent)
**When** `check_migration_needed()` runs
**Then** it detects that `nest.agent.md` content differs from the new coordinator template (outdated)
**And** it detects the three missing subagent files
**And** returns `migration_needed=True`

**When** `execute_migration()` runs for this legacy scenario
**Then** `nest.agent.md` is overwritten with the new coordinator template (no backup)
**And** the three subagent files are created fresh
**And** no `.bak` files are left behind

### AC6: CLI Prompt Shows File-Level Detail

**Given** migration is needed for multiple files
**When** the CLI prompts the user
**Then** it lists which files will be updated/created, e.g.:
```
Agent files need updating:
  Replace  nest.agent.md
  Create   nest-master-researcher.agent.md
  Create   nest-master-synthesizer.agent.md
  Create   nest-master-planner.agent.md
```
**And** user can accept or decline the batch in a single confirmation prompt

### AC7: All-Up-To-Date Scenario

**Given** all four agent files match their templates
**When** `check_migration_needed()` runs
**Then** `migration_needed=False`
**And** `message` is "All agent files are up to date"

### AC8: No Manifest Skips Check

**Given** the directory has no `.nest/manifest.json`
**When** `check_migration_needed()` runs
**Then** `migration_needed=False` and `skipped=True` (same as current behavior)

## Tasks / Subtasks

- [x] **Task 1: Update AgentMigrationCheckResult Model** (AC: #2, #5)
  - [x] 1.1 Add `outdated_files: list[str]` field — filenames whose content differs from template
  - [x] 1.2 Add `missing_files: list[str]` field — filenames that don't exist locally
  - [x] 1.3 Maintain backward compat: `migration_needed` bool, `agent_file_missing` bool (True if ANY file missing), `skipped` bool, `message` str

- [x] **Task 2: Update AgentMigrationResult Model** (AC: #3, #4)
  - [x] 2.1 Remove `backed_up: bool` field (no backups in multi-agent migration)
  - [x] 2.2 Add `files_replaced: list[str]` — filenames that were overwritten
  - [x] 2.3 Add `files_created: list[str]` — filenames that were newly created
  - [x] 2.4 Keep `success: bool` and `error: str | None`

- [x] **Task 3: Rewrite check_migration_needed()** (AC: #1, #2, #5, #7, #8)
  - [x] 3.1 Use `render_all()` instead of `render()` to get all 4 template contents
  - [x] 3.2 Import and use `AGENT_DIR` from `nest.core.paths`
  - [x] 3.3 For each file in rendered dict: check if local file exists, if content matches
  - [x] 3.4 Collect `outdated_files` (exists but content differs) and `missing_files` (doesn't exist)
  - [x] 3.5 Set `migration_needed = bool(outdated_files or missing_files)`
  - [x] 3.6 Set `agent_file_missing = bool(missing_files)`
  - [x] 3.7 Generate descriptive message (e.g., "2 agent files outdated, 1 missing")
  - [x] 3.8 Keep manifest-not-found and corrupt-manifest skip logic unchanged

- [x] **Task 4: Rewrite execute_migration()** (AC: #3, #4)
  - [x] 4.1 Use `render_all()` to get all template contents
  - [x] 4.2 For each rendered file: compare with local, write only if different or missing
  - [x] 4.3 Track `files_replaced` and `files_created` lists
  - [x] 4.4 NO backup logic — remove all `.bak` code
  - [x] 4.5 Ensure agent directory exists before writing (use `AGENT_DIR`)
  - [x] 4.6 Keep manifest validation guard unchanged

- [x] **Task 5: Remove Legacy Constants** (AC: #4)
  - [x] 5.1 Remove `AGENT_FILE_PATH` constant from `agent_migration_service.py`
  - [x] 5.2 Remove `AGENT_BACKUP_SUFFIX` constant
  - [x] 5.3 Import `AGENT_DIR` from `nest.core.paths` instead

- [x] **Task 6: Update CLI Migration Flow** (AC: #6)
  - [x] 6.1 Update `_handle_agent_migration()` in `update_cmd.py`
  - [x] 6.2 When `migration_needed`, display file-level detail using `outdated_files` and `missing_files`
  - [x] 6.3 Show "Replace" for outdated files and "Create" for missing files
  - [x] 6.4 Single `Confirm.ask()` prompt for the batch
  - [x] 6.5 Update success message to show count (e.g., "4 agent files updated")
  - [x] 6.6 Update "up to date" message to "All agent files are up to date"
  - [x] 6.7 Update "keeping existing" message to "Keeping existing agent files"

- [x] **Task 7: Update MockAgentWriter** (AC: prerequisite)
  - [x] 7.1 Update `render_all()` in `tests/conftest.py` to return all 4 file mappings (currently returns only coordinator)
  - [x] 7.2 This is needed so migration tests can properly test multi-file comparison

- [x] **Task 8: Rewrite Unit Tests** (AC: all)
  - [x] 8.1 Rewrite `tests/services/test_agent_migration_service.py` completely
  - [x] 8.2 Remove all `.bak` backup-related tests (AGENT_BACKUP_SUFFIX no longer exists)
  - [x] 8.3 Remove import of `AGENT_FILE_PATH` and `AGENT_BACKUP_SUFFIX` (deleted constants)
  - [x] 8.4 Test: all 4 files current → `migration_needed=False`, message "All agent files are up to date"
  - [x] 8.5 Test: 1 file outdated → `migration_needed=True`, `outdated_files=["nest.agent.md"]`
  - [x] 8.6 Test: 2 files missing → `migration_needed=True`, `missing_files=[...]`
  - [x] 8.7 Test: legacy scenario (only coordinator exists with old content, 3 missing) → correct lists
  - [x] 8.8 Test: no agent files at all → `agent_file_missing=True`, all 4 in `missing_files`
  - [x] 8.9 Test: no manifest → `skipped=True`
  - [x] 8.10 Test: corrupt manifest → `skipped=True`
  - [x] 8.11 Test: `execute_migration()` only writes changed/missing files
  - [x] 8.12 Test: `execute_migration()` returns correct `files_replaced` and `files_created` lists
  - [x] 8.13 Test: `execute_migration()` creates directory if missing
  - [x] 8.14 Test: `execute_migration()` filesystem error returns `success=False`
  - [x] 8.15 Test: no `.bak` files created anywhere

- [x] **Task 9: Update CLI Tests** (AC: #6)
  - [x] 9.1 Update `tests/cli/test_update_cmd.py` migration tests
  - [x] 9.2 Test: file-level detail shown in prompt (Replace/Create labels)
  - [x] 9.3 Test: batch confirmation prompt
  - [x] 9.4 Test: success message shows file count
  - [x] 9.5 Test: up-to-date message updated
  - [x] 9.6 Test: decline message updated
  - [x] 9.7 Ensure `AgentMigrationCheckResult` construction uses new fields

- [x] **Task 10: Run CI Validation**
  - [x] 10.1 `ruff check` passes
  - [x] 10.2 `pyright` passes with 0 errors
  - [x] 10.3 All existing tests pass (no regressions)

## Dev Notes

### Task 1 & 2: Model Changes (src/nest/core/models.py)

**AgentMigrationCheckResult (line 288) — add two new list fields:**

```python
class AgentMigrationCheckResult(BaseModel):
    """Result of checking whether agent template needs migration."""
    migration_needed: bool
    agent_file_missing: bool = False   # True if ANY file is missing
    skipped: bool = False
    message: str
    outdated_files: list[str] = Field(default_factory=list)  # NEW
    missing_files: list[str] = Field(default_factory=list)    # NEW
```

The new fields default to empty lists, so all existing constructors that don't supply them will continue to work (backward compat with CLI test fixtures that construct `AgentMigrationCheckResult` without the new fields).

**AgentMigrationResult (line 304) — replace backed_up with file tracking:**

```python
class AgentMigrationResult(BaseModel):
    """Result of executing agent template migration."""
    success: bool
    files_replaced: list[str] = Field(default_factory=list)   # NEW
    files_created: list[str] = Field(default_factory=list)     # NEW
    error: str | None = None
    # Remove: backed_up: bool = False
```

**BREAKING CHANGE:** Removing `backed_up` will break:
- `update_cmd.py:_handle_agent_migration()` checks `migration_result.backed_up` → update this in Task 6
- `test_update_cmd.py` constructs `AgentMigrationResult(success=True, backed_up=True)` → update in Task 9
- `test_agent_migration_service.py` asserts on `result.backed_up` → rewritten in Task 8

### Task 3: Rewrite check_migration_needed() (src/nest/services/agent_migration_service.py)

**Current logic** (single file): reads `AGENT_FILE_PATH`, calls `render()`, compares one file.

**New logic** (multi-file):

```python
from nest.core.paths import AGENT_DIR

def check_migration_needed(self, project_dir: Path) -> AgentMigrationCheckResult:
    # Keep existing manifest guard (lines 55-73) unchanged
    if not self._manifest.exists(project_dir):
        return AgentMigrationCheckResult(
            migration_needed=False, skipped=True,
            message="Not a Nest project — skipping agent check",
        )
    try:
        self._manifest.load(project_dir)
    except (ManifestError, FileNotFoundError):
        return AgentMigrationCheckResult(
            migration_needed=False, skipped=True,
            message="Manifest is corrupt — skipping agent check",
        )

    # NEW: Multi-file comparison
    rendered = self._agent_writer.render_all()
    agent_dir = project_dir / AGENT_DIR
    outdated: list[str] = []
    missing: list[str] = []

    for filename, expected_content in rendered.items():
        local_path = agent_dir / filename
        if not self._filesystem.exists(local_path):
            missing.append(filename)
        elif self._filesystem.read_text(local_path) != expected_content:
            outdated.append(filename)

    if not outdated and not missing:
        return AgentMigrationCheckResult(
            migration_needed=False,
            message="All agent files are up to date",
        )

    # Build descriptive message
    parts: list[str] = []
    if outdated:
        parts.append(f"{len(outdated)} outdated")
    if missing:
        parts.append(f"{len(missing)} missing")
    message = f"Agent files need updating ({', '.join(parts)})"

    return AgentMigrationCheckResult(
        migration_needed=True,
        agent_file_missing=bool(missing),
        message=message,
        outdated_files=outdated,
        missing_files=missing,
    )
```

### Task 4: Rewrite execute_migration() (src/nest/services/agent_migration_service.py)

**Current logic:** backs up existing file to `.bak`, calls `self._agent_writer.generate(agent_path)`.

**New logic:**

```python
def execute_migration(self, project_dir: Path) -> AgentMigrationResult:
    # Keep manifest validation guard unchanged
    if not self._manifest.exists(project_dir):
        return AgentMigrationResult(
            success=False,
            error="Failed to load manifest: manifest not found",
        )
    try:
        self._manifest.load(project_dir)
    except (ManifestError, FileNotFoundError) as exc:
        return AgentMigrationResult(
            success=False,
            error=f"Failed to load manifest: {exc}",
        )

    agent_dir = project_dir / AGENT_DIR
    rendered = self._agent_writer.render_all()
    files_replaced: list[str] = []
    files_created: list[str] = []

    try:
        # Ensure directory exists
        if not self._filesystem.exists(agent_dir):
            self._filesystem.create_directory(agent_dir)

        for filename, expected_content in rendered.items():
            local_path = agent_dir / filename
            if self._filesystem.exists(local_path):
                local_content = self._filesystem.read_text(local_path)
                if local_content == expected_content:
                    continue  # Up to date, skip
                self._filesystem.write_text(local_path, expected_content)
                files_replaced.append(filename)
            else:
                self._filesystem.write_text(local_path, expected_content)
                files_created.append(filename)

        return AgentMigrationResult(
            success=True,
            files_replaced=files_replaced,
            files_created=files_created,
        )
    except OSError as exc:
        return AgentMigrationResult(
            success=False,
            files_replaced=files_replaced,
            files_created=files_created,
            error=str(exc),
        )
```

**CRITICAL:** `FileSystemProtocol` already has `create_directory(path: Path)` — confirmed in the protocol. `MockFileSystem` in `conftest.py` also implements `create_directory`. Safe to use.

### Task 5: Remove Legacy Constants

Delete from `src/nest/services/agent_migration_service.py`:
```python
AGENT_FILE_PATH = Path(".github") / "agents" / "nest.agent.md"  # DELETE
AGENT_BACKUP_SUFFIX = ".bak"  # DELETE
```

Add import:
```python
from nest.core.paths import AGENT_DIR
```

**Note:** `AGENT_FILE_PATH` is also imported by `tests/services/test_agent_migration_service.py` (line 11) — the test file will be completely rewritten in Task 8, so this import goes away.

### Task 6: Update CLI _handle_agent_migration() (src/nest/cli/update_cmd.py)

**Current code (lines 161-199):**

```python
def _handle_agent_migration(
    migration_service: AgentMigrationService,
    project_dir: Path,
    console: Console,
) -> None:
    migration_check = migration_service.check_migration_needed(project_dir)
    if migration_check.skipped:
        return
    if not migration_check.migration_needed:
        success("Agent file is up to date")
        return
    if migration_check.agent_file_missing:
        confirm_msg = "Agent file is missing. Create it?"
    else:
        confirm_msg = "Agent template has changed. Update?"
    if Confirm.ask(confirm_msg, default=False, console=console):
        migration_result = migration_service.execute_migration(project_dir)
        if migration_result.success:
            if migration_result.backed_up:
                success("Agent file updated (backup: nest.agent.md.bak)")
            else:
                success("Agent file created")
        else:
            warning(f"Agent file update failed: {migration_result.error}")
    else:
        info("Keeping existing agent file. Run nest doctor to update later.")
```

**New code:**

```python
def _handle_agent_migration(
    migration_service: AgentMigrationService,
    project_dir: Path,
    console: Console,
) -> None:
    migration_check = migration_service.check_migration_needed(project_dir)

    if migration_check.skipped:
        return

    if not migration_check.migration_needed:
        success("All agent files are up to date")
        return

    # Display file-level detail
    console.print()
    console.print("  Agent files need updating:")
    for f in migration_check.outdated_files:
        console.print(f"    Replace  {f}")
    for f in migration_check.missing_files:
        console.print(f"    Create   {f}")
    console.print()

    if Confirm.ask("Update agent files?", default=False, console=console):
        migration_result = migration_service.execute_migration(project_dir)
        if migration_result.success:
            total = len(migration_result.files_replaced) + len(migration_result.files_created)
            success(f"{total} agent files updated")
        else:
            warning(f"Agent file update failed: {migration_result.error}")
    else:
        info("Keeping existing agent files. Run nest doctor to update later.")
```

### Task 7: MockAgentWriter Update (tests/conftest.py)

The `render_all()` mock currently returns only `{"nest.agent.md": self.template_content}`. Update to return all 4 files:

```python
def render_all(self) -> dict[str, str]:
    return {
        "nest.agent.md": self.template_content,
        "nest-master-researcher.agent.md": self.template_content,
        "nest-master-synthesizer.agent.md": self.template_content,
        "nest-master-planner.agent.md": self.template_content,
    }
```

Using `self.template_content` (default `"rendered-template"`) for all 4 files is sufficient for migration comparison tests. The mock doesn't need unique content per file because migration tests control what `MockFileSystem.file_contents` returns.

### Task 8: Test Strategy (tests/services/test_agent_migration_service.py)

The test file must be **completely rewritten**. The current tests import `AGENT_FILE_PATH` and `AGENT_BACKUP_SUFFIX` which will be deleted. Key test scenarios:

**check_migration_needed() tests:**

| Test | outdated_files | missing_files | migration_needed | agent_file_missing |
|------|---------------|---------------|------------------|--------------------|
| All current | [] | [] | False | False |
| 1 outdated | ["nest.agent.md"] | [] | True | False |
| 3 missing | [] | [r, s, p] | True | True |
| Legacy (1 outdated + 3 missing) | ["nest.agent.md"] | [r, s, p] | True | True |
| All missing | [] | [all 4] | True | True |
| No manifest | - | - | skipped | - |
| Corrupt manifest | - | - | skipped | - |

**execute_migration() tests:**

| Test | Setup | Expected |
|------|-------|----------|
| Selective write | 2 outdated, 2 current | Only 2 written, `files_replaced=2` |
| Mixed replace+create | 1 outdated, 1 missing | `files_replaced=1`, `files_created=1` |
| All missing | None exist | `files_created=4` |
| Filesystem error | OSError on write | `success=False`, partial lists preserved |
| Manifest missing | No manifest | `success=False` |
| Dir creation | Agent dir missing | Creates dir, then writes |

**Test helpers setup pattern:**

```python
from nest.core.paths import AGENT_DIR, AGENT_FILES

PROJECT_DIR = Path("/project")
AGENT_DIR_PATH = PROJECT_DIR / AGENT_DIR

def _populate_all_agent_files(fs: MockFileSystem, writer: MockAgentWriter) -> None:
    """Set all 4 agent files to match rendered templates (up-to-date state)."""
    rendered = writer.render_all()
    for filename, content in rendered.items():
        path = AGENT_DIR_PATH / filename
        fs.existing_paths.add(path)
        fs.file_contents[path] = content
```

### Task 9: CLI Test Updates (tests/cli/test_update_cmd.py)

Update these test classes:
- `TestAgentMigrationPrompt.test_migration_prompt_shown_when_needed` — construct `AgentMigrationCheckResult` with `outdated_files=["nest.agent.md"]`, remove `backed_up=True` from result, update success assertion from "Agent file updated" to "agent files updated"
- `TestAgentMigrationPrompt.test_migration_declined_shows_info` — add `outdated_files=["nest.agent.md"]`, update assertion from "Keeping existing agent file" to "Keeping existing agent files"
- `TestAgentMigrationPrompt.test_migration_up_to_date_no_prompt` — update assertion from "Agent file is up to date" to "All agent files are up to date"
- `TestAgentMigrationFailure.test_migration_failure_shows_warning` — add `outdated_files=["nest.agent.md"]` to check result, remove `backed_up` from `AgentMigrationResult`
- Consider adding a new test for file-level display output (verify "Replace" and "Create" labels appear)

### Interaction with Doctor Path

After this story:
- `nest update` → `AgentMigrationService.check_migration_needed()` + `execute_migration()` (file-level comparison, selective writes)
- `nest doctor --fix` → `DoctorService.regenerate_agent_file()` → `generate_all()` (blunt overwrite of all 4 files)

Both paths are valid. Doctor does a full regeneration (simpler, fixes everything). Update does selective regeneration (smarter, only touches changed files).

### Clean .github/agents/ Directory

AC4 requires no leftover files. Since the migration only writes files from the `render_all()` dict (which covers exactly the 4 agent files) and never creates `.bak` files, this is automatically satisfied. No deletion of stale files is needed because the filename set is fixed.

### Project Structure Notes

All changes are within existing module boundaries:
- `src/nest/core/models.py` — modify `AgentMigrationCheckResult` and `AgentMigrationResult` (existing file)
- `src/nest/services/agent_migration_service.py` — rewrite check and execute methods, remove legacy constants (existing file)
- `src/nest/cli/update_cmd.py` — update `_handle_agent_migration()` (existing file)
- `tests/conftest.py` — update `MockAgentWriter.render_all()` (existing file)
- `tests/services/test_agent_migration_service.py` — complete rewrite (existing file)
- `tests/cli/test_update_cmd.py` — update migration test assertions (existing file)

No new modules, no new directories, no new dependencies.

### Key Constants (from Story 10.1 in src/nest/core/paths.py)

```python
AGENT_DIR = Path(".github") / "agents"
AGENT_FILES = [
    "nest.agent.md",
    "nest-master-researcher.agent.md",
    "nest-master-synthesizer.agent.md",
    "nest-master-planner.agent.md",
]
TEMPLATE_TO_AGENT_FILE = {
    "coordinator.md.jinja": "nest.agent.md",
    "researcher.md.jinja": "nest-master-researcher.agent.md",
    "synthesizer.md.jinja": "nest-master-synthesizer.agent.md",
    "planner.md.jinja": "nest-master-planner.agent.md",
}
```

### Previous Story Intelligence

**From Story 10.1:**
- `render_all()` returns `dict[str, str]` mapping agent filenames to rendered content
- `TEMPLATE_TO_AGENT_FILE` maps template names to output filenames
- `MockAgentWriter` already has `render_all()` and `generate_all()` stubs
- Templates are static markdown (no Jinja variables since project name removal in 8.1)

**From Story 10.2:**
- `generate_all(output_dir: Path)` writes all 4 files to the directory
- `AGENT_DIR` and `AGENT_FILES` are shared constants in `nest.core.paths`
- `ProjectChecker.missing_agent_files()` returns list of missing filenames
- Doctor uses `generate_all()` for blunt overwrite; migration service needs selective writes

### References

- [Source: epics.md#Epic 10] — FR43, Story 10.3 acceptance criteria
- [Source: project-context.md] — Protocol-based DI, testing rules, naming conventions, error handling
- [Source: 10-1-multi-agent-template-bundle.md] — `render_all()`/`generate_all()` API, constants, MockAgentWriter
- [Source: 10-2-init-doctor-multi-agent-integration.md] — `generate_all()` usage, `missing_agent_files()`, doctor path
- `src/nest/services/agent_migration_service.py` — current single-file migration to rewrite
- `src/nest/core/models.py:288-318` — `AgentMigrationCheckResult` and `AgentMigrationResult` to modify
- `src/nest/cli/update_cmd.py:161-199` — `_handle_agent_migration()` to update for file-level display
- `src/nest/core/paths.py:26-38` — `AGENT_DIR`, `AGENT_FILES`, `TEMPLATE_TO_AGENT_FILE` constants
- `src/nest/adapters/protocols.py` — `AgentWriterProtocol` with `render_all()` method
- `tests/conftest.py:90-113` — `MockAgentWriter` with `render_all()` returning only coordinator (needs update)
- `tests/services/test_agent_migration_service.py` — current tests to rewrite (remove backup logic)
- `tests/cli/test_update_cmd.py:427-530` — CLI migration tests to update assertions

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None needed — all tasks implemented cleanly without debugging issues.

### Completion Notes List

- Tasks 1-2: Added `outdated_files`/`missing_files` to `AgentMigrationCheckResult`, replaced `backed_up` with `files_replaced`/`files_created` in `AgentMigrationResult`. Used `Field(default_factory=list)` for backward compat.
- Tasks 3-4: Rewrote `check_migration_needed()` and `execute_migration()` for multi-file comparison using `render_all()` and `AGENT_DIR`. Selective writes only for changed/missing files.
- Task 5: Removed `AGENT_FILE_PATH` and `AGENT_BACKUP_SUFFIX` constants, replaced with `AGENT_DIR` import from `nest.core.paths`.
- Task 6: Updated CLI `_handle_agent_migration()` with file-level Replace/Create display, batch confirmation, count-based success message.
- Task 7: Updated `MockAgentWriter.render_all()` to return all 4 agent file mappings.
- Task 8: Complete rewrite of migration service tests — 16 tests covering all ACs (8 check, 8 execute).
- Task 9: Updated 5 CLI migration tests + added new `test_file_level_detail_shown` test.
- Task 10: ruff 0 issues, pyright 0 errors, 445 unit/integration tests pass. 8 pre-existing E2E failures (AI/doctor tests requiring external LLM).

### File List

- `src/nest/core/models.py` — Updated `AgentMigrationCheckResult` and `AgentMigrationResult` models
- `src/nest/services/agent_migration_service.py` — Rewrote for multi-file migration, removed legacy constants, added OSError handling to check
- `src/nest/cli/update_cmd.py` — Updated `_handle_agent_migration()` for file-level display
- `tests/conftest.py` — Updated `MockAgentWriter.render_all()` to return all 4 files
- `tests/services/test_agent_migration_service.py` — Complete rewrite with 17 multi-file tests (added content verification + OSError test)
- `tests/cli/test_update_cmd.py` — Updated migration prompt/failure/missing tests + new file-level detail test

### Senior Developer Review (AI)

**Reviewer:** Jóhann — 2026-03-26
**Model:** Claude Opus 4.6
**Verdict:** APPROVED with fixes applied

**Review Summary:**
- All 8 ACs verified implemented and tested
- All 10 tasks verified complete (all [x] legitimate)
- 914 unit/integration tests pass, 0 failures
- ruff: 0 issues, pyright: 0 errors

**Issues Found & Fixed:**
1. **M1 (FIXED):** Added content verification assertions to `test_selective_write_only_changed_files` and `test_mixed_replace_and_create` — now assert `fs.written_files[path] == rendered[name]`
2. **M3 (FIXED):** Added `try/except OSError` around file comparison loop in `check_migration_needed()` — returns `skipped=True` with descriptive message on filesystem errors. Added new test `test_filesystem_error_returns_skipped`.
3. **M2 (DEFERRED):** "0 agent files updated" edge case — race between check and execute is virtually impossible in CLI. Not worth adding complexity for.

**Issues Noted (not fixed):**
- L1: Stale AC comments in `update_cmd.py` (`# AC9`, `# AC8`, `# AC14`) — pre-existing from story 4-5, not a regression
- L2: MockFileSystem write/exists inconsistency — doesn't affect any current tests

### Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-03-26 | Dev Agent (Claude Opus 4.6) | Initial implementation — all tasks complete |
| 2026-03-26 | Code Review (Claude Opus 4.6) | Fixed: content verification in tests, OSError handling in check_migration_needed, added 1 new test (914 total) |

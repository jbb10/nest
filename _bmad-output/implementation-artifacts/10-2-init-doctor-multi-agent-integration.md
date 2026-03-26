# Story 10.2: Init & Doctor Multi-Agent Integration

Status: complete

## Story

As a **user running `nest init` or `nest doctor --fix`**,
I want **all four agent files (coordinator + 3 subagents) to be created and validated**,
So that **my project is set up with the full multi-agent architecture from day one, and doctor can detect and fix missing subagent files**.

## Acceptance Criteria

### AC1: Init Creates All Four Agent Files

**Given** the user runs `nest init`
**When** project scaffolding completes
**Then** `.github/agents/` contains exactly:
- `nest.agent.md` (coordinator)
- `nest-master-researcher.agent.md`
- `nest-master-synthesizer.agent.md`
- `nest-master-planner.agent.md`

### AC2: Init CLI Output Lists Agent Files

**Given** init completes successfully
**When** the success output is displayed
**Then** it mentions the agent files created (e.g., "Created 4 agent files in .github/agents/")

### AC3: ProjectChecker Validates All Agent Files

**Given** a Nest project directory
**When** `ProjectChecker.agent_file_exists()` is called
**Then** it returns `True` only if ALL four agent files exist
**And** returns `False` if any are missing

### AC4: ProjectChecker Reports Missing Files

**Given** a Nest project with only `nest.agent.md` present (legacy state)
**When** doctor validation runs
**Then** it identifies which specific agent files are missing
**And** provides actionable output (e.g., "Missing: nest-master-researcher.agent.md, nest-master-synthesizer.agent.md, nest-master-planner.agent.md")

### AC5: Doctor Fix Regenerates All Agent Files

**Given** `nest doctor --fix` detects missing or outdated agent files
**When** remediation runs
**Then** all four agent files are written via `generate_all()`, overwriting any existing content
**And** no `.bak` backup files are created (clean upgrade, no leftovers in the agents directory)
**And** the user sees a clean `.github/agents/` with exactly 4 files

## Tasks / Subtasks

- [x] **Task 1: Update InitService** (AC: #1, #2)
  - [x] 1.1 Replace single `agent_writer.generate()` call with `agent_writer.generate_all()`
  - [x] 1.2 Pass `AGENT_DIR` constant for the output directory
  - [x] 1.3 Update status message from "Generating agent file" to "Generating agent files"

- [x] **Task 2: Update ProjectChecker** (AC: #3, #4)
  - [x] 2.1 Import `AGENT_FILES` and `AGENT_DIR` from `nest.core.paths`
  - [x] 2.2 Remove `AGENT_FILE_PATH` constant (replaced by shared constants)
  - [x] 2.3 Update `agent_file_exists()` to check ALL 4 files — return `True` only if all exist
  - [x] 2.4 Add `missing_agent_files()` method returning list of missing filenames
  - [x] 2.5 Update `ProjectCheckerProtocol` with new `missing_agent_files()` signature

- [x] **Task 3: Update DoctorService** (AC: #4, #5)
  - [x] 3.1 Update `validate_project()` — use `missing_agent_files()` for detailed suggestions
  - [x] 3.2 Update `regenerate_agent_file()` to use `generate_all()` instead of single `generate()`
  - [x] 3.3 Update success message to reflect multi-file regeneration

- [x] **Task 4: Update Doctor CLI Display** (AC: #4)
  - [x] 4.1 Update `doctor_cmd.py` — update "Agent file missing" issue text to show count/detail
  - [x] 4.2 Update `doctor_display.py` — show per-file status or missing file count

- [x] **Task 5: Write Unit Tests** (AC: all)
  - [x] 5.1 Update `tests/services/test_init_service.py` — verify `generate_all()` called (not `generate()`)
  - [x] 5.2 Update `tests/adapters/test_project_checker.py` — test all-present, partial, none scenarios + `missing_agent_files()`
  - [x] 5.3 Update `tests/services/test_doctor_service.py` — agent remediation uses `generate_all()`
  - [x] 5.4 Update integration tests for init flow if needed

- [x] **Task 6: Run CI Validation**
  - [x] 6.1 Lint passes (`ruff check`)
  - [x] 6.2 Typecheck passes (`pyright`)
  - [x] 6.3 All existing tests pass

## Dev Notes

### Task 1: InitService Changes (src/nest/services/init_service.py)

**Current code (lines 105-108):**
```python
status_start("Generating agent file")
agent_path = target_dir / ".github" / "agents" / "nest.agent.md"
self._agent_writer.generate(agent_path)
status_done()
```

**Required change:**
```python
from nest.core.paths import AGENT_DIR

status_start("Generating agent files")
agent_dir = target_dir / AGENT_DIR
self._agent_writer.generate_all(agent_dir)
status_done()
```

The `generate_all()` method (implemented in Story 10.1) already handles directory creation and writing all 4 files. The `.github/agents` directory is already in `INIT_DIRECTORIES` so it gets created before this point.

**Import update:** Add `AGENT_DIR` to the existing import from `nest.core.paths`.

**No changes to other parts of `execute()`** — the directory creation loop already covers `.github/agents`.

### Task 2: ProjectChecker Changes (src/nest/adapters/project_checker.py)

**Current state:** Uses local `AGENT_FILE_PATH = ".github/agents/nest.agent.md"` string constant to check a single file.

**Required changes:**

1. **Remove** `AGENT_FILE_PATH` constant.
2. **Import** `AGENT_DIR` and `AGENT_FILES` from `nest.core.paths`.
3. **Update** `agent_file_exists()`:
```python
def agent_file_exists(self, project_dir: Path) -> bool:
    """Check if all agent files exist."""
    agent_dir = project_dir / AGENT_DIR
    return all((agent_dir / f).exists() for f in AGENT_FILES)
```

4. **Add** `missing_agent_files()`:
```python
def missing_agent_files(self, project_dir: Path) -> list[str]:
    """Return list of missing agent filenames."""
    agent_dir = project_dir / AGENT_DIR
    return [f for f in AGENT_FILES if not (agent_dir / f).exists()]
```

**Protocol update** (`src/nest/adapters/protocols.py`, `ProjectCheckerProtocol` at line 390):
Add the new method signature:
```python
def missing_agent_files(self, project_dir: Path) -> list[str]:
    """Return list of missing agent filenames.

    Args:
        project_dir: Path to the project root directory.

    Returns:
        List of agent filenames that are missing. Empty list if all present.
    """
    ...
```

### Task 3: DoctorService Changes (src/nest/services/doctor_service.py)

**3.1: Update `validate_project()` (around line 403):**

Current:
```python
agent_present = self._project_checker.agent_file_exists(project_dir)
if not agent_present:
    suggestions.append("Run `nest init` to regenerate agent file")
```

New — provide detailed missing file info:
```python
agent_present = self._project_checker.agent_file_exists(project_dir)
if not agent_present:
    missing = self._project_checker.missing_agent_files(project_dir)
    missing_names = ", ".join(missing)
    suggestions.append(f"Missing agent files: {missing_names}")
```

**3.2: Update `regenerate_agent_file()` (around line 583):**

Current:
```python
output_path = project_dir / ".github" / "agents" / "nest.agent.md"
self._agent_writer.generate(output_path)
```

New:
```python
from nest.core.paths import AGENT_DIR

agent_dir = project_dir / AGENT_DIR
self._agent_writer.generate_all(agent_dir)
```

Update the success message:
```python
message=f"Agent files regenerated at {AGENT_DIR}",
```

**3.3:** The issue key in `RemediationResult` stays `"missing_agent_file"` for backward compatibility with any consumers.

### Task 4: Doctor Display Changes

**`src/nest/cli/doctor_cmd.py` (line 101):**
Current: `issues.append("Agent file missing")`
New: `issues.append("Agent files missing")` (plural — since now multi-file)

**`src/nest/ui/doctor_display.py` (lines 135-141):**
Current shows "Agent file: present/missing". Update to show count:
```python
if status.agent_file_present:
    agent_line = "Agent files: all present [green]✓[/green]"
else:
    agent_line = "Agent files: incomplete [red]✗[/red]"
```

The detailed missing file names are already captured in `suggestions` and will be displayed as child nodes of the agent line.

### Legacy Project Handling

Users who initialized before multi-agent support will have only `nest.agent.md`. After this story:
- `agent_file_exists()` returns `False` (only 1 of 4 files present)
- `missing_agent_files()` returns the 3 missing subagent filenames
- `nest doctor --fix` calls `generate_all()` which overwrites `nest.agent.md` with the new coordinator content AND creates the 3 subagent files
- The existing `nest.agent.md` content (old single-agent) is replaced with the coordinator template — this is the desired behavior per AC5

Full legacy-to-multi-agent content migration (comparing old content vs new) is handled in Story 10.3 (migration service).

### MockAgentWriter Update (tests/conftest.py)

The existing `MockAgentWriter` (line 90) already has `render_all()` and `generate_all()` stubs from Story 10.1. However, `generate_all()` only records the directory path. For more thorough testing, consider checking `generated_all_dirs` was called instead of `generated_agents`.

### _is_nest_project Check (doctor_cmd.py line 131)

The `_is_nest_project()` function calls `project_checker.agent_file_exists()`. After the update, this returns `True` only if ALL 4 files exist. For project detection purposes, a partial agent state (legacy project with 1 file) should still be detected. **However**, the function uses `or` across multiple checks (manifest, legacy layout, agent files, source folder, context folder), so even if `agent_file_exists()` returns `False` for a legacy project, the manifest or other markers will catch it. No change needed here.

### Existing Callers of agent_file_exists()

| Caller | File | Impact |
|--------|------|--------|
| `DoctorService.validate_project()` | `doctor_service.py:403` | Uses bool → works as-is (False triggers fix) |
| `_is_nest_project()` | `doctor_cmd.py:131` | False for legacy → OK, other markers catch it |
| `test_project_checker.py` | Tests | Need update for multi-file behavior |

### Project Structure Notes

All changes are within existing module boundaries:
- `src/nest/services/init_service.py` — update `execute()` to use `generate_all()` (existing file)
- `src/nest/adapters/project_checker.py` — update `agent_file_exists()`, add `missing_agent_files()` (existing file)
- `src/nest/adapters/protocols.py` — add `missing_agent_files()` to `ProjectCheckerProtocol` (existing file)
- `src/nest/services/doctor_service.py` — update `validate_project()` and `regenerate_agent_file()` (existing file)
- `src/nest/cli/doctor_cmd.py` — update issue text (existing file)
- `src/nest/ui/doctor_display.py` — update display labels (existing file)
- `tests/services/test_init_service.py` — update assertions (existing file)
- `tests/adapters/test_project_checker.py` — add multi-file test scenarios (existing file)
- `tests/services/test_doctor_service.py` — update agent remediation tests (existing file)

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
```

### References

- [Source: architecture.md] — AgentWriter protocol, ProjectChecker, DoctorService, Jinja templates
- [Source: project-context.md] — Protocol-based DI, testing rules, naming conventions
- [Source: epics.md#Epic 10] — FR42, multi-agent init and validation
- [Source: 10-1-multi-agent-template-bundle.md] — Story 10.1 completion notes, `render_all()`/`generate_all()` API
- `src/nest/services/init_service.py:105-108` — Current single `generate()` call to update
- `src/nest/adapters/project_checker.py:1-120` — Current single-file checker to update
- `src/nest/adapters/protocols.py:390-478` — `ProjectCheckerProtocol` to extend
- `src/nest/services/doctor_service.py:583-620` — `regenerate_agent_file()` to update
- `src/nest/services/doctor_service.py:403-405` — `validate_project()` agent check to update
- `src/nest/cli/doctor_cmd.py:101` — Doctor CLI agent issue text
- `src/nest/ui/doctor_display.py:135-141` — Doctor display agent status
- `src/nest/core/paths.py:26-38` — `AGENT_DIR`, `AGENT_FILES` constants (from 10.1)
- `tests/conftest.py:90-113` — `MockAgentWriter` with `generate_all()` stub
- `tests/services/test_init_service.py` — Init tests to update
- `tests/adapters/test_project_checker.py` — Checker tests to update
- `tests/services/test_doctor_service.py:796` — Doctor agent remediation test to update

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None — clean implementation, no debug issues.

### Completion Notes List

- Task 1: Replaced `generate()` with `generate_all()` in `InitService.execute()`, imported `AGENT_DIR`, updated status message to plural.
- Task 2: Removed `AGENT_FILE_PATH` constant from `ProjectChecker`, imported `AGENT_DIR`/`AGENT_FILES` from `nest.core.paths`. Updated `agent_file_exists()` to check all 4 files. Added `missing_agent_files()` method. Updated `ProjectCheckerProtocol` with new signature.
- Task 3: Updated `DoctorService.validate_project()` to use `missing_agent_files()` for detailed suggestion text. Updated `regenerate_agent_file()` to call `generate_all()` with `AGENT_DIR`.
- Task 4: Updated `doctor_cmd.py` issue text to "Agent files missing" (plural). Updated `doctor_display.py` to show "Agent files: all present" / "Agent files: incomplete".
- Task 5: Updated all test files — init service tests verify `generate_all()`, project checker tests cover all-present/partial/none/missing_agent_files scenarios, doctor service tests verify `generate_all` called and suggestion text, doctor cmd/display tests updated for new labels.
- Task 6: ruff check passes, pyright 0 errors, 909 unit/integration tests pass. Pre-existing e2e AI enrichment test failure unrelated to this story.

### File List

- src/nest/services/init_service.py
- src/nest/adapters/project_checker.py
- src/nest/adapters/protocols.py
- src/nest/services/doctor_service.py
- src/nest/cli/doctor_cmd.py
- src/nest/ui/doctor_display.py
- tests/services/test_init_service.py
- tests/adapters/test_project_checker.py
- tests/services/test_doctor_service.py
- tests/cli/test_doctor_cmd.py
- tests/ui/test_doctor_display.py
- tests/conftest.py
- tests/integration/test_init_flow.py

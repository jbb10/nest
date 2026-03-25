# Story 8.1: Remove Project Name Concept

Status: review

## Story

As a **developer initialising a Nest project**,
I want **`nest init` to require no arguments**,
so that **I can run `nest init` from any folder and get going immediately without having to name anything**.

## Business Context

Nest is a folder-oriented tool — documents live in `_nest_sources/`, outputs land in `_nest_context/`. The "project name" concept is a human label that was threaded through the system at init time but never tied to any meaningful operation:

- `nest sync` already ignores the stored name and derives what it needs from the folder itself.
- The manifest stores `project_name` but nothing queries it at runtime for processing logic.
- The VS Code agent description and index header used the stored name as cosmetic text only.

Requiring a name at `nest init` adds friction with no payoff. This story removes the concept entirely, from the CLI all the way down to the data model, and replaces cosmetic uses with neutral static text (`"Nest Project"` for status display, folder-agnostic wording in the agent template).

This is a **leaf refactor** — no behaviour the user can observe changes except: (1) `nest init` takes zero arguments, and (2) display text is generic rather than project-named. All processing is unaffected.

---

## Acceptance Criteria

### AC1: `nest init` takes no arguments

**Given** any directory
**When** `nest init` is run with no positional argument
**Then** the project is initialised successfully (exit code 0)
**And** the success output reads exactly: `Nest project initialized!`
**And** the "Next steps" block is shown unchanged

### AC2: No positional argument is accepted

**Given** `nest init some-name` is run
**When** Typer parses the command
**Then** it exits with a Typer/Click "Got unexpected extra argument" error (exit code 2)
**And** no project is initialised

> *Rationale: accepting the arg silently and ignoring it would be confusing. Hard-failing keeps the interface honest.*

### AC3: `--dir` flag still works

**Given** `nest init --dir /some/path` is run
**When** the command executes
**Then** the project is initialised in `/some/path` (exit code 0)

### AC4: Manifest has no `project_name` field

**Given** a project is initialised with `nest init`
**When** `.nest/manifest.json` is inspected
**Then** it does NOT contain a `project_name` key

### AC5: Agent file contains no project name

**Given** a project is initialised
**When** `.github/agents/nest.agent.md` is inspected
**Then** the `description:` frontmatter reads: `Expert analyst for documents in this project folder`
**And** the body refers to "documents in this project folder" rather than any named project

### AC6: Master index header is generic

**Given** `nest sync` has been run
**When** `.nest/00_MASTER_INDEX.md` is inspected
**Then** the first line reads: `# Nest Project Index`
**And** no project name appears in the header

### AC7: `nest status` displays "Nest Project" as the root label

**Given** a valid Nest project
**When** `nest status` is run
**Then** the tree root reads: `📁 Nest Project`

### AC8: `nest doctor --fix` silent remediation does not reference a project name

**Given** a corrupt or missing manifest
**When** `nest doctor --fix` rebuilds the manifest
**Then** the manifest is rebuilt without a `project_name` field
**And** no prompt for a project name appears

### AC9: Old manifests with `project_name` load without error

**Given** an existing `manifest.json` that contains `"project_name": "Nike"`
**When** any `nest` command loads the manifest
**Then** the extra field is silently ignored (Pydantic default behaviour)
**And** the next manifest write will omit the field

### AC10: All existing tests pass (suite stays green)

**Given** the above changes are applied
**When** the full test suite is run (`uv run pytest`)
**Then** all tests pass (no regressions)

---

## Affected Files

### Production code (12 files)

| File | Change |
|------|--------|
| `src/nest/cli/init_cmd.py` | Remove `project_name` arg; update success message; remove "Project name required" error branch |
| `src/nest/services/init_service.py` | Remove `project_name` param from `execute()`; remove name validation; remove name from `manifest.create()` and `agent_writer.generate()` calls |
| `src/nest/adapters/manifest.py` | Remove `project_name` param from `create()` |
| `src/nest/core/models.py` | Remove `project_name: str` field from `Manifest` |
| `src/nest/agents/vscode_writer.py` | Remove `project_name` param from `render()` and `generate()` |
| `src/nest/agents/templates/vscode.md.jinja` | Replace `{{ project_name }}` with folder-agnostic text (see below) |
| `src/nest/services/index_service.py` | Remove `project_name` param from `generate_content()`; change header to `# Nest Project Index` |
| `src/nest/services/sync_service.py` | Remove `project_name` arg from `generate_content()` call |
| `src/nest/services/status_service.py` | Remove `project_name` from `StatusReport` dataclass; stop reading from manifest |
| `src/nest/ui/status_display.py` | Change tree root from `📁 Project: {name}` to `📁 Nest Project` |
| `src/nest/services/doctor_service.py` | Remove `project_name` from `rebuild_manifest()` and `regenerate_agent_file()`; delete `_get_project_name()`; remove name prompt from `remediate_issues_interactive()` |
| `src/nest/services/agent_migration_service.py` | Remove `project_name` reads from manifest; call `render()`/`generate()` with no name arg |

### Test files (~ 6 files, mechanical updates)

| File | Change |
|------|--------|
| `tests/cli/test_init_cmd.py` | Remove `"Nike"` arg from CLI invocations; update success message assertion |
| `tests/services/test_init_service.py` | Remove `project_name` from `execute()` calls; delete whitespace/empty name tests |
| `tests/services/test_agent_migration_service.py` | Remove `project_name` from `Manifest(...)` construction; remove "renders with project name" test |
| `tests/services/test_orphan_service.py` | Remove `project_name=` kwarg from all `Manifest(...)` instantiations |
| `tests/services/test_status_service.py` | Remove `project_name` from `StatusReport` assertions |
| `tests/agents/test_vscode_writer.py` | Remove `project_name` from `render()`/`generate()` calls; update snapshot assertions |

---

## Tasks / Subtasks

### Task 1: Data model — strip `project_name` from `Manifest` (AC4, AC9)

- [x] 1.1: In `src/nest/core/models.py`, remove the `project_name: str` field from the `Manifest` class.
  - Pydantic V2 ignores unknown keys on load by default — old manifests round-trip safely.
  - Update the docstring to remove mention of `project_name`.

### Task 2: Adapter — remove `project_name` from manifest creation (AC4)

- [x] 2.1: In `src/nest/adapters/manifest.py`, remove `project_name: str` param from `create()`.
- [x] 2.2: Remove `project_name=project_name` from the `Manifest(...)` constructor call inside `create()`.
- [x] 2.3: Update the method docstring accordingly.

### Task 3: Agent writer — remove `project_name` from writer and template (AC5)

- [x] 3.1: In `src/nest/agents/templates/vscode.md.jinja`, replace **both** occurrences of `{{ project_name }}`:
  - `description: Expert analyst for {{ project_name }} project documents`
    → `description: Expert analyst for documents in this project folder`
  - `You are an expert document analyst specialized in the {{ project_name }} project.`
    → `You are an expert document analyst for the documents in this project folder.`
- [x] 3.2: In `src/nest/agents/vscode_writer.py`, remove `project_name: str` param from `render()` and `generate()`.
- [x] 3.3: Remove `project_name=project_name` from the `template.render(...)` call in `render()`.
- [x] 3.4: Update docstrings for both methods.

### Task 4: Index service — remove `project_name` from generation (AC6)

- [x] 4.1: In `src/nest/services/index_service.py`, remove `project_name: str` param from `generate_content()`.
- [x] 4.2: Change the header line:
  - From: `f"# Nest Project Index: {project_name}"`
  - To: `"# Nest Project Index"`
- [x] 4.3: Update the docstring.

### Task 5: Sync service — stop passing `project_name` to index (AC6)

- [x] 5.1: In `src/nest/services/sync_service.py`, remove the `project_name = self._project_root.name` line.
- [x] 5.2: Remove `project_name` from the `generate_content(...)` call.

### Task 6: Status service and display — use static label (AC7)

- [x] 6.1: In `src/nest/services/status_service.py`, remove `project_name: str` from the `StatusReport` dataclass.
- [x] 6.2: In `StatusService.get_status()`, remove `project_name=manifest.project_name` from the `StatusReport(...)` constructor.
- [x] 6.3: In `src/nest/ui/status_display.py`, change the tree root:
  - From: `Tree(f"📁 Project: [bold]{report.project_name}[/bold]")`
  - To: `Tree("📁 [bold]Nest Project[/bold]")`
- [x] 6.4: Remove the `from nest.services.status_service import StatusReport` import update if `project_name` was referenced there (it isn't directly, but verify).

### Task 7: Doctor service — remove project name entirely (AC8)

- [x] 7.1: Remove the `project_name: str` parameter from `rebuild_manifest()`.
- [x] 7.2: Remove `project_name=project_name` from the `Manifest(...)` call inside `rebuild_manifest()`.
- [x] 7.3: Remove the `project_name: str` parameter from `regenerate_agent_file()`.
- [x] 7.4: Update the `agent_writer.generate(project_name, output_path)` call to `agent_writer.generate(output_path)`.
- [x] 7.5: Delete the entire `_get_project_name()` method.
- [x] 7.6: In `remediate_issues_auto()`, remove both `project_name = self._get_project_name(project_dir)` lines.
- [x] 7.7: In `remediate_issues_interactive()`:
  - Remove the `project_name = self._get_project_name(project_dir)` line.
  - Delete the entire `if needs_name and project_name == "Nest Project" and input_callback:` block.
  - Change `f"Rebuild manifest for '{project_name}'?"` → `"Rebuild manifest?"`.
  - Remove `project_name` from `rebuild_manifest(...)` and `regenerate_agent_file(...)` calls.

### Task 8: Agent migration service — remove project name (AC5)

- [x] 8.1: In `src/nest/services/agent_migration_service.py`, find both `project_name = manifest_data.project_name` lines.
- [x] 8.2: Delete those lines and update the calls to `render()` and `generate()` to omit the `project_name` argument.

### Task 9: Init service — remove project name from execute() (AC1, AC4, AC5)

- [x] 9.1: In `src/nest/services/init_service.py`, remove `project_name: str` from `execute()` signature.
- [x] 9.2: Remove the `if not project_name or not project_name.strip():` validation block.
- [x] 9.3: Update `self._manifest.create(target_dir, project_name.strip())` → `self._manifest.create(target_dir)`.
- [x] 9.4: Update `self._agent_writer.generate(project_name.strip(), agent_path)` → `self._agent_writer.generate(agent_path)`.
- [x] 9.5: Update the method docstring to remove `project_name` param documentation.

### Task 10: CLI init command — remove argument (AC1, AC2, AC3)

- [x] 10.1: In `src/nest/cli/init_cmd.py`, remove the `project_name` function parameter and its `Annotated[str, ...]` declaration.
- [x] 10.2: Update the function docstring — remove the `"Nike"` example.
- [x] 10.3: Update `service.execute(project_name, resolved_dir)` → `service.execute(resolved_dir)`.
- [x] 10.4: Change the success message:
  - From: `success(f'Project "{project_name}" initialized!')`
  - To: `success("Nest project initialized!")`
- [x] 10.5: Remove the `elif "Project name required" in error_msg:` branch from the `NestError` handler.

### Task 11: Update tests (AC10)

- [x] 11.1: `tests/cli/test_init_cmd.py`
  - Change all `runner.invoke(app, ["init", "Nike", ...])` → `runner.invoke(app, ["init", ...])`
  - Change success assertion to `"Nest project initialized!"` (no name)
  - Remove (or repurpose as AC2) any test for missing-name error — replace with a test that `init some-name` exits with code 2
- [x] 11.2: `tests/services/test_init_service.py`
  - Change all `service.execute("Nike", target_dir)` → `service.execute(target_dir)`
  - Delete `test_init_service_rejects_empty_project_name` and `test_init_service_rejects_whitespace_only_project_name`
  - Fix assertions that compare `project_name == "Nike"` — the agent writer now receives only `output_path`, so update `MockAgentWriter` if it captures args differently
- [x] 11.3: `tests/services/test_agent_migration_service.py`
  - Remove `project_name="TestProject"` / `project_name="Nike"` from all `Manifest(...)` calls
  - In `test_renders_template_with_project_name_from_manifest` — rename/repurpose test: verify the rendered template contains the new static text instead of a project name
  - Update `test_loads_project_name_from_manifest` similarly (name no longer loaded)
- [x] 11.4: `tests/services/test_orphan_service.py`
  - Remove `project_name="test"` kwarg from all `Manifest(...)` instantiations (6 occurrences)
- [x] 11.5: `tests/services/test_status_service.py`
  - Remove any `project_name` assertions from `StatusReport` — the field no longer exists
- [x] 11.6: `tests/agents/test_vscode_writer.py`
  - Update `render()` / `generate()` calls — drop `project_name` arg
  - Update snapshot/string assertions to expect the new static template text

---

## Dev Notes

### Pydantic backward compatibility (AC9)

Pydantic V2's default model configuration ignores unknown fields on `model_validate()` / `parse_raw()`. An existing `manifest.json` containing `"project_name": "Nike"` will parse into the new `Manifest` without error — the extra key is simply discarded. No migration script is needed.

Verify this holds with:
```python
Manifest.model_validate({"nest_version": "1.0.0", "project_name": "Nike", "files": {}})
# → Manifest(nest_version='1.0.0', last_sync=None, files={})
```
If the project uses `model_config = ConfigDict(extra="forbid")` on `Manifest`, that setting must be removed or changed to `extra="ignore"` — check `models.py` before assuming.

### `MockAgentWriter` in conftest — likely needs signature update

The test conftest defines `MockAgentWriter` which records calls to `generate()`. Currently it probably stores `(project_name, output_path)` tuples. After this story it should store only `(output_path,)`. Check `tests/conftest.py` and update accordingly — this ripples into any test that unpacks the recorded tuple.

### Doctor interactive mode — `input_callback` path

The `input_callback` arg to `remediate_issues_interactive()` existed purely to collect the project name from the user. Once the project name is gone, that parameter becomes dead code. Consider whether to remove it from the method signature entirely (cleaner) or leave it as a no-op (safer for hypothetical future use). Recommend: **remove it**, since it is only called with `input_callback` in tests that mock it for the name prompt — once those tests are deleted, nothing calls it.

### Template wording — full diff for `vscode.md.jinja`

Change only lines that reference `{{ project_name }}`:

```diff
-description: Expert analyst for {{ project_name }} project documents
+description: Expert analyst for documents in this project folder
```

```diff
-You are an expert document analyst specialized in the {{ project_name }} project. Your role is to help users understand, search, and extract insights from project documents.
+You are an expert document analyst for the documents in this project folder. Your role is to help users understand, search, and extract insights from project documents.
```

No other lines in the template change.

### Agent migration — template comparison still works

`AgentMigrationService.check_migration_needed()` compares `rendered != local_content` to decide if the agent file is outdated. After this change, `render()` produces deterministic output (no variable interpolation), so the comparison still works correctly. Any existing project that runs `nest update` or `nest doctor --fix` will regenerate the agent file with the new static wording — that is the intended behaviour.

### Recommended task order

Tasks 1–3 must land before 8 and 9 (writer/manifest signatures drive service signatures).
Tasks 4–5 are independent of each other.
Task 10 (CLI) should be last in production code — ensures everything it delegates to is already updated.
Task 11 (tests) can be done after all production changes, then run the full suite once.

---

## Dev Agent Record

**Agent:** Amelia (Dev)
**Status:** Complete → review

### Implementation Notes

- All 14 production files updated to remove `project_name` concept (including `manifest_service.py` which was not in the original Affected Files list but also called `create()` with project_name)
- `model_config = ConfigDict(extra="ignore")` added to `Manifest` for AC9 backward compatibility — old YAML/JSON with `project_name` field loads silently without error
- `input_callback` removed from `remediate_issues_interactive()` entirely (no longer needed)
- `_get_project_name()` private method deleted from `DoctorService`
- `TestGetProjectName` class deleted from `test_doctor_service.py` (3 tests for removed method)
- `test_interactive_asks_project_name_once` replaced with `test_interactive_confirm_callback_controls_all_fixes`
- Final result: **847 unit tests passing, 0 failures**

### Files Changed

- `src/nest/core/models.py`
- `src/nest/adapters/manifest.py`
- `src/nest/adapters/protocols.py`
- `src/nest/agents/templates/vscode.md.jinja`
- `src/nest/agents/vscode_writer.py`
- `src/nest/services/index_service.py`
- `src/nest/services/sync_service.py`
- `src/nest/services/status_service.py`
- `src/nest/ui/status_display.py`
- `src/nest/services/doctor_service.py`
- `src/nest/services/agent_migration_service.py`
- `src/nest/services/init_service.py`
- `src/nest/services/manifest_service.py`
- `src/nest/cli/init_cmd.py`
- `tests/conftest.py`
- `tests/cli/test_init_cmd.py`
- `tests/cli/test_status_cmd.py`
- `tests/services/test_init_service.py`
- `tests/services/test_agent_migration_service.py`
- `tests/services/test_orphan_service.py`
- `tests/services/test_status_service.py`
- `tests/services/test_index_service.py`
- `tests/services/test_manifest_service.py`
- `tests/services/test_doctor_service.py`
- `tests/agents/test_vscode_writer.py`
- `tests/ui/test_status_display.py`
- `tests/adapters/test_manifest.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

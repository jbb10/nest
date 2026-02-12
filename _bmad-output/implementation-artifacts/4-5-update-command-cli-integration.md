# Story 4.5: Update Command CLI Integration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user running `nest update`**,
I want **the update process to be clear, interactive, and safe with rich terminal feedback**,
So that **I'm confident in updating my tool and know exactly what happened**.

## Business Context

This is the **FIFTH and FINAL** story in Epic 4 (Tool Updates & Maintenance). It is the **CLI integration layer** that wires together all components built in Stories 4.1–4.4 into a cohesive `nest update` command:

- **Story 4.1** (User Config Management) — `UserConfigAdapter` for reading/saving install source and version
- **Story 4.2** (Version Discovery & Comparison) — `GitClientAdapter` for querying remote tags, `core/version.py` for semver logic
- **Story 4.3** (Interactive Version Selection) — `UpdateService` for orchestrating version check, validation, and `uv tool install` execution
- **Story 4.4** (Agent Template Migration Check) — `AgentMigrationService` for checking and executing agent template migrations after update

**This story creates:**
1. `cli/update_cmd.py` — The `nest update` command with Rich UI, user prompts, and error handling
2. `tests/cli/test_update_cmd.py` — Unit tests for CLI layer
3. Registration in `cli/main.py` — Adds `update` command to the Typer app

**Functional Requirements Covered:** FR15 (self-update via uv — CLI integration), FR16 (agent template migration — user prompt), FR17 (version selection display — Rich UI)

**Architecture References:**
- [Source: architecture.md § `nest update` Command Behavior] — Full display format, input options, 6-step flow
- [Source: architecture.md § Project Structure] — `cli/update_cmd.py`
- [Source: architecture.md § PRD Command to Module Mapping] — `nest update` → `update_cmd.py` → `UpdateService` → `GitClient`, `UserConfig`
- [Source: architecture.md § Dependency Injection] — Manual constructor injection, composition root in CLI
- [Source: architecture.md § CLI Output Patterns] — Rich console, What → Why → Action errors
- [Source: epics.md § Story 4.5] — Acceptance criteria

## Acceptance Criteria

### AC1: Composition Root — Service Wiring

**Given** `nest update` command runs
**When** `update_command()` creates services
**Then** CLI injects real adapters following the composition root pattern:
- `UpdateService(git_client=GitClientAdapter(), user_config=UserConfigAdapter(), subprocess_runner=SubprocessRunnerAdapter())`
- `AgentMigrationService(agent_writer=VSCodeAgentWriter(filesystem), filesystem=FileSystemAdapter(), manifest=ManifestAdapter())`

### AC2: Version Display with Rich Output

**Given** `nest update` runs and versions are discovered
**When** the version list is displayed
**Then** Rich console output shows:
```
  Current version: 0.1.3
  Latest version:  0.2.0

  Available versions:
    • 0.2.0 (latest)
    • 0.1.3 (installed)
    • 0.1.2
    • 0.1.1
    • 0.1.0

  Update to 0.2.0? [Y/n/version]:
```

### AC3: Update with Rich Spinner

**Given** user confirms update (enters `Y` or presses Enter or enters a specific version)
**When** `uv tool install` runs
**Then** Rich spinner shows: `"Installing version X.Y.Z..."`
**And** on success: `"✓ Updated to version X.Y.Z"`
**And** shows changelog link: `"What's new: https://github.com/jbjornsson/nest/blob/main/CHANGELOG.md"`

### AC4: Update Failure Error Display

**Given** update fails (uv error)
**When** error is caught
**Then** error message follows What → Why → Action format:
```
✗ Update failed
  Reason: uv tool install returned exit code 1
  Action: Check `uv` is working: `uv --version`
```

### AC5: User Cancellation

**Given** user enters `n` when prompted
**When** cancellation is processed
**Then** message shows: `"Update cancelled"`
**And** no update is performed, exit code 0

### AC6: Missing User Config — Prompt for Source URL

**Given** user config is missing (`UserConfigAdapter.load()` returns `None`)
**When** `nest update` runs
**Then** a default config is created automatically using `create_default_config()`
**And** the update proceeds with the default install source
**And** the config is saved for future use

### AC7: Agent Template Migration Prompt (Post-Update)

**Given** update completes successfully
**When** `AgentMigrationService.check_migration_needed()` returns `migration_needed=True`
**Then** prompt shows: `"Agent template has changed. Update? [y/N]"`
**And** if user confirms → `execute_migration()` is called, shows `"✓ Agent file updated (backup: nest.agent.md.bak)"`
**And** if user declines → shows `"Keeping existing agent file. Run nest doctor to update later."`

### AC8: Agent Template Up-to-Date (No Prompt)

**Given** update completes successfully
**When** `AgentMigrationService.check_migration_needed()` returns `migration_needed=False`
**Then** shows `"✓ Agent file is up to date"`
**And** no prompt is shown

### AC9: Agent Template Migration Skipped (Not a Nest Project)

**Given** update completes successfully but current directory is not a Nest project
**When** `AgentMigrationService.check_migration_needed()` returns `skipped=True`
**Then** agent migration section is silently skipped (no output)

### AC10: `--check` Flag — Version Check Only

**Given** `nest update --check` is run
**When** version discovery completes
**Then** only the version comparison is displayed (no update prompt)
**And** exit code is 0 if already up-to-date
**And** exit code is 1 if an update is available

### AC11: Already Up-to-Date

**Given** current version equals latest version
**When** `check_for_updates()` returns `update_available=False`
**Then** shows: `"✓ Already up to date (version X.Y.Z)"`
**And** exit code 0

### AC12: No Versions Found

**Given** remote has no version tags
**When** version discovery returns empty
**Then** shows: `"No releases found. You may be on a development version."`
**And** exit code 0

### AC13: Network Error During Version Discovery

**Given** `GitClientAdapter.list_tags()` raises `ConfigError`
**When** error is caught
**Then** error message shows:
```
✗ Cannot check for updates
  Reason: Cannot reach update server. Check your internet connection.
  Action: Verify your network connection and try again
```

### AC14: Agent Migration Failure Handling

**Given** `execute_migration()` returns `success=False`
**When** the error result is received
**Then** shows warning: `"⚠ Agent file update failed: {error}"`
**And** the overall update is still considered successful (agent migration is non-critical)

### AC15: `--dir` Flag for Project Directory

**Given** `nest update --dir /path/to/project`
**When** agent migration check runs
**Then** it uses the provided directory instead of `Path.cwd()` for checking the agent file

## Tasks / Subtasks

- [x] **Task 1: Create `update_cmd.py` — Composition Root & Command** (AC: #1, #2, #3, #4, #5, #6, #10, #11, #12, #13, #15)
  - [x] 1.1 Create `src/nest/cli/update_cmd.py`
  - [x] 1.2 Implement `create_update_service() -> UpdateService` composition root
  - [x] 1.3 Implement `create_migration_service() -> AgentMigrationService` composition root
  - [x] 1.4 Implement `_ensure_config(user_config: UserConfigAdapter) -> UserConfig` — loads or creates default config
  - [x] 1.5 Implement `_display_versions(check_result: UpdateCheckResult, console: Console)` — Rich version list display
  - [x] 1.6 Implement `_prompt_for_version(check_result: UpdateCheckResult, console: Console) -> str | None` — user input handling (Y/n/version)
  - [x] 1.7 Implement `_run_update(service: UpdateService, version: str, check_result: UpdateCheckResult, console: Console) -> UpdateResult` — spinner + uv execution
  - [x] 1.8 Implement `_handle_agent_migration(migration_service: AgentMigrationService, project_dir: Path, console: Console)` — post-update agent check
  - [x] 1.9 Implement `update_command(check: bool, target_dir: Path | None)` — main Typer command function
  - [x] 1.10 Add `--check` flag (AC10) and `--dir` / `-d` flag (AC15)

- [x] **Task 2: Register Update Command in `main.py`** (AC: #1)
  - [x] 2.1 Add import of `update_command` from `nest.cli.update_cmd`
  - [x] 2.2 Add `app.command(name="update")(update_command)` registration

- [x] **Task 3: Write Unit Tests for `update_cmd.py`** (AC: #1–#15)
  - [x] 3.1 Create `tests/cli/test_update_cmd.py`
  - [x] 3.2 Test `_ensure_config` creates default when `load()` returns None
  - [x] 3.3 Test `_ensure_config` returns existing config when present
  - [x] 3.4 Test `_display_versions` renders correct Rich output
  - [x] 3.5 Test `update_command` with `--check` flag — up-to-date exits 0
  - [x] 3.6 Test `update_command` with `--check` flag — update available exits 1
  - [x] 3.7 Test `update_command` already up-to-date shows success message
  - [x] 3.8 Test `update_command` network error shows What → Why → Action
  - [x] 3.9 Test `update_command` no versions found shows info message
  - [x] 3.10 Test successful update displays spinner and success message
  - [x] 3.11 Test update failure shows error with exit code
  - [x] 3.12 Test user cancellation exits cleanly
  - [x] 3.13 Test agent migration prompt shown when needed (post-update)
  - [x] 3.14 Test agent migration skipped silently when not a Nest project
  - [x] 3.15 Test agent migration failure shows warning but doesn't fail overall
  - [x] 3.16 Test `--dir` flag passes correct path to migration service
  - [x] 3.17 Test composition root creates correct service instances

- [x] **Task 4: Run CI Validation**
  - [x] 4.1 Lint passes (`ruff check` — 0 new issues)
  - [x] 4.2 Typecheck passes (`pyright` — 0 errors)
  - [x] 4.3 All tests pass (existing 555 + new 26 = 581)

## Dev Notes

### Architecture Patterns to Follow

**Layer Placement:**
- `cli/update_cmd.py` → **CLI layer** — composition root, user interaction, Rich display, Typer command
- No new services, adapters, or core modules — everything is already built in Stories 4.1–4.4

**Composition Root Pattern** (same as `init_cmd.py`, `doctor_cmd.py`):
```python
# cli/update_cmd.py — Composition root for update workflow

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.git_client import GitClientAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.adapters.subprocess_runner import SubprocessRunnerAdapter
from nest.adapters.user_config import UserConfigAdapter, create_default_config
from nest.agents.vscode_writer import VSCodeAgentWriter
from nest.services.agent_migration_service import AgentMigrationService
from nest.services.update_service import UpdateService


def create_update_service() -> tuple[UpdateService, UserConfigAdapter]:
    """Composition root for update service.

    Returns:
        Tuple of (UpdateService, UserConfigAdapter) — adapter returned
        separately because CLI needs it for config ensure/save.
    """
    git_client = GitClientAdapter()
    user_config = UserConfigAdapter()
    subprocess_runner = SubprocessRunnerAdapter()
    service = UpdateService(
        git_client=git_client,
        user_config=user_config,
        subprocess_runner=subprocess_runner,
    )
    return service, user_config


def create_migration_service() -> AgentMigrationService:
    """Composition root for agent migration service.

    Returns:
        Configured AgentMigrationService.
    """
    filesystem = FileSystemAdapter()
    return AgentMigrationService(
        agent_writer=VSCodeAgentWriter(filesystem=filesystem),
        filesystem=filesystem,
        manifest=ManifestAdapter(),
    )
```

### Command Entry Point Design

```python
def update_command(
    check: Annotated[
        bool,
        typer.Option("--check", help="Only check for updates without installing"),
    ] = False,
    target_dir: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help="Project directory for agent migration check"),
    ] = None,
) -> None:
    """Check for and install Nest updates.

    Queries available versions, displays comparison, and optionally
    installs a selected version via uv.

    Examples:
        nest update
        nest update --check
        nest update --dir /path/to/project
    """
```

### Update Flow (Step-by-Step)

1. **Ensure config exists** — Load via `UserConfigAdapter.load()`. If `None`, call `create_default_config()` and `save()`. This handles the "first run" case where user hasn't run any nest command yet.

2. **Check for updates** — Call `UpdateService.check_for_updates()`. Handle `ConfigError` (network failure) with What → Why → Action display.

3. **Handle edge cases:**
   - No versions found → info message, exit 0
   - Already up-to-date → success message, exit 0
   - `--check` flag → display versions only, exit 0 (up-to-date) or exit 1 (update available)

4. **Display versions** — Rich formatted version list with `(latest)` and `(installed)` annotations.

5. **Prompt user** — `"Update to X.Y.Z? [Y/n/version]:"` using `rich.prompt.Prompt.ask()`.
   - `Y` or empty → update to latest
   - `n` → cancel, exit 0
   - Specific version → validate and update to that version

6. **Execute update** — Rich spinner during `uv tool install`, then display success/failure.

7. **Agent migration check** — Only after successful update. Call `AgentMigrationService.check_migration_needed()` with the project directory. If migration needed, prompt user. If skipped (not a Nest project), silently skip.

### Rich Output Patterns

**Version display** (use `console.print()` with markup):
```python
console.print()
console.print(f"  Current version: [bold]{check_result.current_version}[/bold]")
console.print(f"  Latest version:  [bold]{check_result.latest_version}[/bold]")
console.print()
console.print("  Available versions:")
for version, annotation in check_result.annotated_versions:
    if "(installed)" in annotation:
        console.print(f"    [green]•[/green] {version} [dim]{annotation}[/dim]")
    elif "(latest)" in annotation:
        console.print(f"    [cyan]•[/cyan] {version} [dim]{annotation}[/dim]")
    else:
        console.print(f"    • {version}")
```

**Spinner during install** (use `console.status()`):
```python
with console.status(f"Installing version {version}..."):
    result = service.execute_update(version, available_versions, source)
```

**Success message:**
```python
success(f"Updated to version {result.version}")
console.print()
console.print(
    "  [dim]What's new: https://github.com/jbjornsson/nest/blob/main/CHANGELOG.md[/dim]"
)
```

### User Input Handling

Use `rich.prompt.Prompt.ask()` for consistent terminal interaction:
```python
from rich.prompt import Confirm, Prompt

# Version selection prompt
response = Prompt.ask(
    f"\n  Update to {latest}? [Y/n/version]",
    default="Y",
    console=console,
)

# Parse response
if response.lower() == "n":
    info("Update cancelled")
    return
elif response.upper() == "Y" or response == "":
    target_version = latest
else:
    target_version = response  # Specific version
```

For agent migration:
```python
if migration_check.migration_needed:
    if migration_check.agent_file_missing:
        confirm_msg = "Agent file is missing. Create it?"
    else:
        confirm_msg = "Agent template has changed. Update?"
    if Confirm.ask(confirm_msg, default=False):
        result = migration_service.execute_migration(project_dir)
        # ... display result
    else:
        info("Keeping existing agent file. Run nest doctor to update later.")
```

### Error Handling Strategy

All errors in the CLI layer are caught and displayed — no exceptions leak to the user:

```python
try:
    check_result = service.check_for_updates()
except ConfigError as e:
    error("Cannot check for updates")
    console.print(f"  [dim]Reason: {e}[/dim]")
    console.print("  [dim]Action: Verify your network connection and try again[/dim]")
    raise typer.Exit(1) from None
```

Agent migration failures are **non-critical** — they show a warning but don't fail the overall update:
```python
if not migration_result.success:
    warning(f"Agent file update failed: {migration_result.error}")
```

### Testing Strategy

**Unit tests for CLI command** — Mock services via `unittest.mock.patch`:

```python
from unittest.mock import MagicMock, patch

from nest.cli.update_cmd import update_command
from nest.core.models import UpdateCheckResult, UpdateResult


@patch("nest.cli.update_cmd.create_update_service")
@patch("nest.cli.update_cmd.create_migration_service")
def test_update_check_flag_up_to_date(mock_migration, mock_update):
    """--check flag with up-to-date version exits 0."""
    mock_service = MagicMock()
    mock_config = MagicMock()
    mock_config.load.return_value = _make_config()
    mock_service.check_for_updates.return_value = UpdateCheckResult(
        current_version="1.0.0",
        latest_version="1.0.0",
        annotated_versions=[("1.0.0", "(installed) (latest)")],
        update_available=False,
        source="git+https://github.com/jbjornsson/nest",
    )
    mock_update.return_value = (mock_service, mock_config)
    # ... invoke and assert
```

**Key test patterns from existing CLI tests:**
- Import helpers from `nest.ui.messages` to verify output
- Use `typer.testing.CliRunner` for invoking commands via Typer's test runner
- Mock at the composition root boundary (mock `create_update_service`, `create_migration_service`)
- Test Rich output by capturing console output via `StringIO` or by testing the logic functions directly

### Project Structure Notes

- `cli/update_cmd.py` completes the CLI layer for all 5 commands (`init`, `sync`, `status`, `doctor`, `update`)
- The architecture specifies this file location in multiple places
- Agent migration prompt logic lives in the CLI layer (not the service) because it involves user interaction
- The `--check` flag enables scripting/CI use cases (e.g., `nest update --check || echo "update available"`)

### Existing Patterns to Reuse

| Pattern | Source | How to Reuse |
|---------|--------|-------------|
| Composition root | `cli/init_cmd.py`, `cli/doctor_cmd.py` | Same `create_X_service()` pattern |
| Error display | `cli/init_cmd.py` | What → Why → Action format |
| Rich console | `ui/messages.py` | `success()`, `error()`, `warning()`, `info()`, `get_console()` |
| Typer command | `cli/doctor_cmd.py` | `typer.Option` for `--check`, `--dir` flags |
| Service mocking | `tests/cli/test_doctor_cmd.py` | `@patch` on composition root functions |
| Exit codes | `cli/doctor_cmd.py` | `raise typer.Exit(code=1)` for failure |
| User prompts | `cli/doctor_cmd.py` | `rich.prompt.Confirm.ask()`, `Prompt.ask()` |
| Typed args | `cli/init_cmd.py` | `Annotated[..., typer.Option(...)]` syntax |

### Config Ensure Strategy (AC6)

Instead of prompting the user for a source URL (which adds complexity), create a default config using the existing `create_default_config()` factory from `adapters/user_config.py`. This uses the default GitHub source and current installed version. The user config was designed in Story 4.1 to be auto-created on first use.

```python
def _ensure_config(user_config: UserConfigAdapter) -> UserConfig:
    """Ensure user config exists, creating default if needed.

    Args:
        user_config: User config adapter.

    Returns:
        The loaded or newly created UserConfig.
    """
    config = user_config.load()
    if config is not None:
        return config

    config = create_default_config()
    user_config.save(config)
    info("Created default configuration")
    return config
```

### Files to Create

| File | Purpose |
|------|---------|
| `src/nest/cli/update_cmd.py` | `update_command` — Typer command with composition root, Rich UI, prompts |
| `tests/cli/test_update_cmd.py` | Unit tests for update CLI command |

### Files to Modify

| File | Change |
|------|--------|
| `src/nest/cli/main.py` | Import `update_command`, register `app.command(name="update")` |

### Files NOT to Touch

- `services/update_service.py` — Already complete from Story 4.3
- `services/agent_migration_service.py` — Already complete from Story 4.4
- `adapters/user_config.py` — Already complete from Story 4.1
- `adapters/git_client.py` — Already complete from Story 4.2
- `adapters/subprocess_runner.py` — Already complete from Story 4.3
- `core/models.py` — All result models already exist
- `core/version.py` — Already complete from Story 4.2
- `adapters/protocols.py` — All protocols already defined
- `agents/vscode_writer.py` — Already has `render()` from Story 4.4
- `ui/messages.py` — Existing helpers are sufficient
- `conftest.py` — No new shared fixtures needed (mocking at CLI boundary)

### Edge Cases to Handle

1. **Terminal not interactive** — `Prompt.ask()` / `Confirm.ask()` may fail in non-TTY environments. The `--check` flag provides a non-interactive path. For `nest update` without `--check` in non-TTY, use sensible defaults or abort with guidance.
2. **Version with `v` prefix in user input** — Users might type `v1.2.3` instead of `1.2.3`. Strip `v` prefix before validating against available list.
3. **Config save failure** — If saving the default config fails, the update can still proceed (config persistence is best-effort on first run).
4. **Agent migration after failed update** — Migration check should only run after `UpdateResult.success=True`.
5. **Empty annotated_versions** — Guard against empty list before displaying versions.

### Dependency Notes

- **No new pip/uv dependencies required** — all functionality uses existing Typer, Rich, Pydantic
- All adapters and services are already implemented and tested
- `rich.prompt.Prompt` and `rich.prompt.Confirm` are part of the Rich library (already a dependency)

### Previous Story Intelligence

**Story 4.4 Learnings:**
- 555 tests baseline — maintain this + add new
- `AgentMigrationService` handles all edge cases internally (missing manifest → skipped, missing agent file → create, filesystem error → error result)
- `AgentMigrationCheckResult.skipped` means silently skip in CLI — no output needed
- `MockAgentWriter` in `conftest.py` already has `render()` support
- `MockManifest` already supports returning a manifest from `load()`

**Story 4.3 Learnings:**
- `UpdateService.check_for_updates()` raises `ConfigError` when no config — CLI must handle this
- `UpdateService.execute_update()` returns `UpdateResult` — never raises on individual failures
- `validate_version()` is called internally by `execute_update()` — no need to validate separately in CLI
- `SubprocessRunnerAdapter` handles `CalledProcessError` and `TimeoutExpired` — service catches and wraps

**Story 4.1 Learnings:**
- `UserConfigAdapter.load()` returns `None` if file missing — not an error
- `create_default_config()` creates config with current `__version__` and default GitHub source
- `UserConfigAdapter.save()` auto-creates `~/.config/nest/` directory

**doctor_cmd.py Patterns:**
- Uses `@patch` for isolating service creation
- Uses `rich.prompt.Confirm.ask()` for interactive prompts
- Handles both interactive and non-interactive modes
- Returns different exit codes based on outcome

### Git Workflow

```bash
git checkout main && git pull origin main
git checkout -b feat/4-5-update-command-cli-integration
# ... implement ...
# Run CI: uv run ruff check src/ tests/ && uv run pyright src/ && uv run pytest --timeout=30
```

### References

- [Source: architecture.md § `nest update` Command Behavior] — Full display format, input options, 6-step flow
- [Source: architecture.md § Project Structure] — `cli/update_cmd.py` placement
- [Source: architecture.md § PRD Command to Module Mapping] — `nest update` → `update_cmd.py` → `UpdateService` → `GitClient`, `UserConfig`
- [Source: architecture.md § CLI Output Patterns] — Rich console, What → Why → Action error format
- [Source: architecture.md § Dependency Injection] — Manual constructor injection, composition root
- [Source: epics.md § Story 4.5] — Acceptance criteria for update CLI integration
- [Source: prd.md § Command: `nest update`] — User-facing options: `--check`, version display
- [Source: project-context.md § CLI Output Patterns] — `success()`, `error()`, `warning()`, `info()` helpers
- [Source: project-context.md § Error Handling] — What → Why → Action format, result types
- [Source: project-context.md § Testing Rules] — Test naming, AAA pattern, mock patterns
- [Source: project-context.md § Python Language Rules] — Modern 3.10+ syntax, absolute imports
- [Source: 4-4-agent-template-migration-check.md] — AgentMigrationService API, result models
- [Source: 4-3-interactive-version-selection.md] — UpdateService API, result models, subprocess patterns
- [Source: 4-2-version-discovery-and-comparison.md] — GitClientAdapter, version module, ConfigError
- [Source: 4-1-user-config-management.md] — UserConfigAdapter, create_default_config(), config path
- [Source: cli/init_cmd.py] — Composition root pattern, error handling
- [Source: cli/doctor_cmd.py] — Prompt patterns, fix mode, interactive/non-interactive handling
- [Source: cli/main.py] — Command registration pattern
- [Source: ui/messages.py] — success(), error(), warning(), info(), get_console()

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None — clean implementation.

### Completion Notes List

- All 15 acceptance criteria covered by 26 unit tests
- `typer.Exit` raises `click.exceptions.Exit` (not `SystemExit`) when called directly — tests use `pytest.raises(ClickExit)` pattern
- `success()`/`error()`/`warning()`/`info()` write to module-level console from `ui/messages.py` — tests use `capsys` fixture to capture stdout
- Console parameter in helper functions is for Rich-specific output (prompts, spinners, version display)
- No new dependencies required — all uses existing Typer, Rich, Pydantic
- 581 total tests (555 existing + 26 new), all passing
- Lint: 0 errors (ruff check)
- Typecheck: 0 errors (pyright)

### File List

| File | Action |
|------|--------|
| `src/nest/cli/update_cmd.py` | Created — update command with composition root, Rich UI, prompts |
| `src/nest/cli/main.py` | Modified — registered `update` command |
| `tests/cli/test_update_cmd.py` | Created — 26 unit tests covering AC1–AC15 |

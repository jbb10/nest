# Story 4.3: Interactive Version Selection

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user running `nest update`**,
I want **to choose which version to install from available versions**,
So that **I can upgrade to the latest version or downgrade to a specific version as needed**.

## Business Context

This is the **THIRD** story in Epic 4 (Tool Updates & Maintenance). It builds directly on:
- **Story 4.1** (User Config Management) — reads `source` and `installed_version` from `UserConfig`, updates config after successful install
- **Story 4.2** (Version Discovery & Comparison) — consumes `GitClientAdapter.list_tags()`, `sort_versions()`, `compare_versions()` from `core/version.py`

**Downstream Dependencies:**
- **Story 4.4:** Agent Template Migration Check — runs after version update completes
- **Story 4.5:** Update Command CLI Integration — wires `UpdateService` into `cli/update_cmd.py` with Rich UI

**This story creates two new components:**
1. `services/update_service.py` — `UpdateService` orchestrating version selection, uv install execution, and config update
2. `adapters/protocols.py` — `SubprocessRunnerProtocol` for testable subprocess execution (wrapping `uv tool install`)

**Functional Requirements Covered:** FR15 (self-update via uv), FR17 (version selection — upgrade or downgrade)

**Architecture References:**
- [Source: architecture.md § `nest update` Command Behavior] — 6-step flow, display format, input options
- [Source: architecture.md § Project Structure] — `services/update_service.py`
- [Source: architecture.md § PRD Command to Module Mapping] — `UpdateService` uses `GitClient`, `UserConfig`
- [Source: architecture.md § Protocol Boundaries] — `GitClientProtocol`, `UserConfigProtocol`
- [Source: architecture.md § Dependency Injection] — Manual constructor injection

## Acceptance Criteria

### AC1: Version Display and User Prompt

**Given** `UpdateService.check_for_updates()` is called with a valid `UserConfig`
**When** available versions are retrieved and sorted
**Then** the service returns an `UpdateCheckResult` dataclass containing:
- `current_version: str` — from config
- `latest_version: str | None` — newest available (or None if no versions)
- `annotated_versions: list[tuple[str, str]]` — from `compare_versions()`
- `update_available: bool` — True if latest > current
- `source: str` — git remote URL from config

### AC2: Update to Latest Version

**Given** user confirms update (enters `Y` or empty string for latest)
**When** `UpdateService.execute_update(version)` is called
**Then** it runs `uv tool install --force <source>@v<version>` via subprocess
**And** on success, updates `UserConfig` with new `installed_version` and `installed_at`
**And** saves the updated config via `UserConfigProtocol.save()`
**And** returns an `UpdateResult` with `success=True`, `version=<version>`

### AC3: Cancel Update

**Given** user enters `n`
**When** the cancellation is processed
**Then** no subprocess is executed
**And** no config changes are made
**And** the result indicates cancellation

### AC4: Install Specific Version

**Given** user enters a specific version string (e.g., `1.3.1`)
**When** the version is validated against available versions
**Then** `uv tool install --force <source>@v1.3.1` executes
**And** config is updated on success

### AC5: Invalid Version Rejection

**Given** user enters a version not in the available list (e.g., `1.9.9`)
**When** validation runs
**Then** error is returned with message: `"Version 1.9.9 not found. Available: 1.4.0, 1.3.1, ..."`
**And** no subprocess is executed

### AC6: Subprocess Execution via Protocol

**Given** `SubprocessRunnerProtocol` is defined
**When** `UpdateService` needs to run `uv tool install`
**Then** it calls the protocol's `run()` method (not `subprocess.run` directly)
**And** the default implementation (`SubprocessRunnerAdapter`) wraps `subprocess.run`
**And** tests can inject a mock runner for full isolation

### AC7: Subprocess Failure Handling

**Given** `uv tool install` fails (non-zero exit code)
**When** the error is caught
**Then** `UpdateResult` has `success=False` and `error` contains:
  `"Update failed: uv tool install returned exit code {code}"`
**And** the user config is NOT updated (preserves previous version)

### AC8: Already Up-to-Date

**Given** current version equals latest version
**When** `check_for_updates()` runs
**Then** `update_available` is `False`
**And** `latest_version` matches `current_version`

### AC9: No Config Available

**Given** `UserConfigProtocol.load()` returns `None` (no config file)
**When** `check_for_updates()` is called
**Then** a `ConfigError` is raised with message: `"No user config found. Run any nest command first to create config."`

### AC10: No Versions Available

**Given** `GitClientProtocol.list_tags()` returns an empty list
**When** version discovery completes
**Then** `UpdateCheckResult` has `latest_version=None`, `update_available=False`, empty `annotated_versions`

## Tasks / Subtasks

- [x] **Task 1: Add `SubprocessRunnerProtocol` and `SubprocessRunnerAdapter`** (AC: #6)
  - [x] 1.1 Add `SubprocessRunnerProtocol` to `src/nest/adapters/protocols.py` with `@runtime_checkable`
  - [x] 1.2 Method: `run(args: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]`
  - [x] 1.3 Create `SubprocessRunnerAdapter` class in `src/nest/adapters/subprocess_runner.py`
  - [x] 1.4 Implementation wraps `subprocess.run` with `capture_output=True, text=True, check=True`
  - [x] 1.5 Default timeout: 120 seconds (uv install can be slow on first run)

- [x] **Task 2: Add Result Models** (AC: #1, #2, #3, #7, #8, #10)
  - [x] 2.1 Add `UpdateCheckResult` dataclass to `src/nest/core/models.py`:
    - `current_version: str`
    - `latest_version: str | None`
    - `annotated_versions: list[tuple[str, str]]`
    - `update_available: bool`
    - `source: str`
  - [x] 2.2 Add `UpdateResult` dataclass to `src/nest/core/models.py`:
    - `success: bool`
    - `version: str`
    - `previous_version: str`
    - `error: str | None = None`

- [x] **Task 3: Implement `UpdateService`** (AC: #1-#5, #7-#10)
  - [x] 3.1 Create `src/nest/services/update_service.py`
  - [x] 3.2 Constructor accepts: `git_client: GitClientProtocol`, `user_config: UserConfigProtocol`, `subprocess_runner: SubprocessRunnerProtocol`
  - [x] 3.3 Implement `check_for_updates() -> UpdateCheckResult`:
    - Load config via `user_config.load()` — raise `ConfigError` if None
    - Query tags via `git_client.list_tags(config.install.source)`
    - Sort/filter via `sort_versions(tags)`
    - Compare via `compare_versions(current, available)`
    - Determine if update available via `is_newer(latest, current)`
    - Return `UpdateCheckResult`
  - [x] 3.4 Implement `execute_update(version: str, available_versions: list[str], source: str) -> UpdateResult`:
    - Validate version is in `available_versions` — return error result if not
    - Build command: `["uv", "tool", "install", "--force", f"{source}@v{version}"]`
    - Strip `git+` prefix is NOT needed here (uv accepts `git+` prefix)
    - Run via `subprocess_runner.run(cmd, timeout=120)`
    - On success: load config, update `installed_version` and `installed_at`, save
    - On `CalledProcessError`: return `UpdateResult(success=False, error=...)`
    - On `TimeoutExpired`: return `UpdateResult(success=False, error="Update timed out...")`
  - [x] 3.5 Implement `validate_version(version: str, available: list[str]) -> str | None`:
    - Returns `None` if version is valid (in available list)
    - Returns error message string if version not found

- [x] **Task 4: Write Unit Tests for `SubprocessRunnerAdapter`** (AC: #6)
  - [x] 4.1 Create `tests/adapters/test_subprocess_runner.py`
  - [x] 4.2 Test protocol satisfaction: `isinstance(SubprocessRunnerAdapter(), SubprocessRunnerProtocol)`
  - [x] 4.3 Test `run()` passes args through to `subprocess.run` (mock subprocess)
  - [x] 4.4 Test `run()` propagates `CalledProcessError` from subprocess
  - [x] 4.5 Test `run()` propagates `TimeoutExpired` from subprocess
  - [x] 4.6 Test default timeout is 120 seconds

- [x] **Task 5: Write Unit Tests for `UpdateService`** (AC: #1-#5, #7-#10)
  - [x] 5.1 Create `tests/services/test_update_service.py`
  - [x] 5.2 Test `check_for_updates` returns correct `UpdateCheckResult` with annotated versions
  - [x] 5.3 Test `check_for_updates` with current already latest → `update_available=False`
  - [x] 5.4 Test `check_for_updates` raises `ConfigError` when no config
  - [x] 5.5 Test `check_for_updates` with no tags → empty versions, `update_available=False`
  - [x] 5.6 Test `execute_update` runs correct `uv` command string
  - [x] 5.7 Test `execute_update` updates config on success
  - [x] 5.8 Test `execute_update` does NOT update config on failure
  - [x] 5.9 Test `execute_update` returns error on subprocess failure with exit code
  - [x] 5.10 Test `execute_update` returns error on timeout
  - [x] 5.11 Test `validate_version` accepts valid version in list
  - [x] 5.12 Test `validate_version` rejects version not in list with descriptive error
  - [x] 5.13 Test `execute_update` rejects invalid version before running subprocess
  - [x] 5.14 Test `check_for_updates` uses correct source URL from config
  - [x] 5.15 Test `execute_update` preserves `git+` prefix in uv command (uv accepts it)

- [x] **Task 6: Run CI Validation**
  - [x] 6.1 Lint passes (`ruff check` — 0 new issues)
  - [x] 6.2 Typecheck passes (`pyright` — 0 errors)
  - [x] 6.3 All tests pass (existing + new — 538 total)

## Dev Notes

### Architecture Patterns to Follow

**Layer Placement:**
- `services/update_service.py` → **Services layer** — orchestrates the update workflow, depends on protocols only
- `adapters/subprocess_runner.py` → **Adapters layer** — wraps `subprocess.run` for testability
- `adapters/protocols.py` → Add `SubprocessRunnerProtocol` alongside existing protocols
- `core/models.py` → Add `UpdateCheckResult` and `UpdateResult` models

**Composition Root:** `UpdateService` will be instantiated in `cli/update_cmd.py` (Story 4.5). For this story, no CLI wiring is needed — the service and adapter are standalone and fully testable.

**Protocol-Based DI Pattern (follow existing patterns exactly):**
```python
# adapters/protocols.py — Add to existing file
@runtime_checkable
class SubprocessRunnerProtocol(Protocol):
    def run(
        self,
        args: list[str],
        *,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]: ...
```

### Why SubprocessRunnerProtocol?

The architecture mandates protocol-based DI for all external dependencies. `uv tool install` is a subprocess call — an external dependency that MUST be injectable for testing. Without this protocol:
- Tests would need to mock `subprocess.run` globally (fragile)
- No way to verify the exact command string being built
- Integration boundaries unclear

This follows the same pattern as `GitClientAdapter` wrapping `subprocess.run` for `git ls-remote`, but is more general-purpose and can be reused for future subprocess needs.

### UpdateService Design

```python
# services/update_service.py

from datetime import datetime, timezone

from nest.adapters.protocols import (
    GitClientProtocol,
    SubprocessRunnerProtocol,
    UserConfigProtocol,
)
from nest.core.exceptions import ConfigError
from nest.core.models import UpdateCheckResult, UpdateResult
from nest.core.version import compare_versions, is_newer, sort_versions

UV_INSTALL_TIMEOUT = 120  # seconds — uv install can be slow


class UpdateService:
    """Service for orchestrating Nest version updates.

    Handles version discovery, user version selection validation,
    uv-based installation, and config persistence.
    """

    def __init__(
        self,
        git_client: GitClientProtocol,
        user_config: UserConfigProtocol,
        subprocess_runner: SubprocessRunnerProtocol,
    ) -> None: ...

    def check_for_updates(self) -> UpdateCheckResult:
        """Query available versions and compare to installed.

        Returns:
            UpdateCheckResult with version comparison data.

        Raises:
            ConfigError: If no user config exists.
            ConfigError: If git remote query fails.
        """
        ...

    def execute_update(
        self,
        version: str,
        available_versions: list[str],
        source: str,
    ) -> UpdateResult:
        """Install a specific version via uv.

        Args:
            version: Target version string (without v prefix).
            available_versions: List of valid version strings.
            source: Git remote URL (e.g., "git+https://...").

        Returns:
            UpdateResult indicating success or failure.
        """
        ...

    def validate_version(
        self,
        version: str,
        available: list[str],
    ) -> str | None:
        """Check if version exists in available list.

        Args:
            version: Version string to validate.
            available: List of available version strings.

        Returns:
            None if valid, error message string if invalid.
        """
        ...
```

### Result Model Design

```python
# core/models.py — Add alongside existing models

class UpdateCheckResult(BaseModel):
    """Result of checking for available updates.

    Attributes:
        current_version: Currently installed version string.
        latest_version: Newest available version (None if no versions found).
        annotated_versions: List of (version, annotation) tuples for display.
        update_available: True if a newer version exists.
        source: Git remote URL from user config.
    """

    current_version: str
    latest_version: str | None
    annotated_versions: list[tuple[str, str]]
    update_available: bool
    source: str


class UpdateResult(BaseModel):
    """Result of executing a version update.

    Attributes:
        success: Whether the update completed successfully.
        version: The version that was installed (or attempted).
        previous_version: The version before the update.
        error: Error message if update failed.
    """

    success: bool
    version: str
    previous_version: str
    error: str | None = None
```

### SubprocessRunnerAdapter Design

```python
# adapters/subprocess_runner.py

import subprocess


UV_DEFAULT_TIMEOUT = 120  # seconds


class SubprocessRunnerAdapter:
    """Adapter wrapping subprocess.run for testable command execution.

    Used by UpdateService to execute `uv tool install` commands.
    Injectable via SubprocessRunnerProtocol for testing.
    """

    def __init__(self, *, default_timeout: int = UV_DEFAULT_TIMEOUT) -> None:
        self._default_timeout = default_timeout

    def run(
        self,
        args: list[str],
        *,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a command via subprocess.

        Args:
            args: Command and arguments list.
            timeout: Timeout in seconds. Uses default if None.

        Returns:
            CompletedProcess result.

        Raises:
            subprocess.CalledProcessError: If command returns non-zero.
            subprocess.TimeoutExpired: If command exceeds timeout.
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        return subprocess.run(  # noqa: S603
            args,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            check=True,
        )
```

### uv Command Construction

The `uv tool install` command requires the full source URL with the version tag:
```
uv tool install --force git+https://github.com/jbb10/nest@v1.4.0
```

**Key details:**
- `--force` is REQUIRED — reinstalls even if the same version is already installed (needed for version switching)
- The `git+` prefix is preserved (uv accepts it, unlike `git ls-remote`)
- The version is prefixed with `v` to match git tags (e.g., `@v1.4.0`)
- The source URL comes directly from `UserConfig.install.source`

```python
def _build_install_command(source: str, version: str) -> list[str]:
    """Build the uv tool install command."""
    return ["uv", "tool", "install", "--force", f"{source}@v{version}"]
```

### Error Handling Pattern

Follow existing patterns from Story 4.1 and 4.2:

```python
# No config → ConfigError
config = self._user_config.load()
if config is None:
    raise ConfigError(
        "No user config found. Run any nest command first to create config."
    )

# Subprocess failure → UpdateResult with error (NOT exception)
try:
    self._subprocess_runner.run(cmd)
except subprocess.CalledProcessError as err:
    return UpdateResult(
        success=False,
        version=version,
        previous_version=current_version,
        error=f"Update failed: uv tool install returned exit code {err.returncode}",
    )
except subprocess.TimeoutExpired:
    return UpdateResult(
        success=False,
        version=version,
        previous_version=current_version,
        error=f"Update timed out after {UV_INSTALL_TIMEOUT} seconds",
    )
```

**Why return `UpdateResult` instead of raising?** The update failure is a user-recoverable scenario. The CLI layer (Story 4.5) will inspect the result and display appropriate Rich output. Exceptions should only be used for truly unexpected/unrecoverable situations (like missing config).

### Config Update After Successful Install

```python
# After successful uv install:
config = self._user_config.load()
if config is not None:
    updated = config.model_copy(
        update={
            "install": config.install.model_copy(
                update={
                    "installed_version": version,
                    "installed_at": datetime.now(tz=timezone.utc),
                }
            )
        }
    )
    self._user_config.save(updated)
```

### Testing Strategy

**Unit tests for `UpdateService`** — Mock all three protocols:
```python
# tests/services/test_update_service.py

class MockGitClient:
    def __init__(self, tags: list[str] | None = None) -> None:
        self.tags = tags or []

    def list_tags(self, remote_url: str) -> list[str]:
        return self.tags


class MockUserConfig:
    def __init__(self, config: UserConfig | None = None) -> None:
        self.config = config
        self.saved: UserConfig | None = None

    def load(self) -> UserConfig | None:
        return self.config

    def save(self, config: UserConfig) -> None:
        self.saved = config

    def config_path(self) -> Path:
        return Path("/mock/.config/nest/config.toml")


class MockSubprocessRunner:
    def __init__(
        self,
        *,
        raise_error: Exception | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self._raise_error = raise_error

    def run(
        self,
        args: list[str],
        *,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if self._raise_error:
            raise self._raise_error
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
```

**Unit tests for `SubprocessRunnerAdapter`** — Mock `subprocess.run`:
```python
# tests/adapters/test_subprocess_runner.py

from unittest.mock import patch, MagicMock

@patch("nest.adapters.subprocess_runner.subprocess.run")
def test_run_passes_args(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0)
    adapter = SubprocessRunnerAdapter()
    adapter.run(["uv", "tool", "install", "--force", "pkg@v1.0.0"])
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["uv", "tool", "install", "--force", "pkg@v1.0.0"]
```

### Existing Patterns to Reuse

| Pattern | Source | How to Reuse |
|---------|--------|-------------|
| Protocol definition | `adapters/protocols.py` | Follow `GitClientProtocol` format with `@runtime_checkable` |
| Service constructor | `services/init_service.py` | Protocol-only constructor params |
| Error raising | `core/exceptions.py` | Use existing `ConfigError` class |
| Result types | `core/models.py` | Use `BaseModel` for results, follow `SyncResult` pattern |
| Core pure functions | `core/version.py` | Reuse `sort_versions`, `compare_versions`, `is_newer` directly |
| Test mocks | `tests/services/test_init_service.py` | Follow same mock class patterns |
| Timeout pattern | `adapters/git_client.py` | `GIT_TIMEOUT_SECONDS` pattern, constructor-injectable timeout |

### Files to Create

| File | Purpose |
|------|---------|
| `src/nest/services/update_service.py` | `UpdateService` — orchestrates version check + update execution |
| `src/nest/adapters/subprocess_runner.py` | `SubprocessRunnerAdapter` — wraps `subprocess.run` for testability |
| `tests/services/test_update_service.py` | Unit tests for `UpdateService` |
| `tests/adapters/test_subprocess_runner.py` | Unit tests for `SubprocessRunnerAdapter` |

### Files to Modify

| File | Change |
|------|--------|
| `src/nest/adapters/protocols.py` | Add `SubprocessRunnerProtocol` |
| `src/nest/core/models.py` | Add `UpdateCheckResult`, `UpdateResult` |

### Files NOT to Touch

- `cli/update_cmd.py` — CLI wiring happens in Story 4.5
- `cli/main.py` — No command registration yet (Story 4.5)
- `ui/messages.py` — No new UI messages needed (display logic is Story 4.5)
- `ui/progress.py` — No progress bars needed (spinner/display is Story 4.5)
- `core/version.py` — Reuse existing functions, no modifications needed
- `adapters/git_client.py` — Already complete from Story 4.2
- `adapters/user_config.py` — Already complete from Story 4.1

### Project Structure Notes

- `services/update_service.py` is specified in architecture.md § Project Structure as `update_service.py — Update workflow orchestration`
- `SubprocessRunnerAdapter` is a new adapter not in the original architecture, but follows the protocol-based DI mandate: every external dependency must be injectable
- Architecture's PRD Command to Module Mapping confirms: `nest update` → `update_cmd.py` → `UpdateService` → `GitClient, UserConfig`
- This story adds `SubprocessRunner` as a third adapter dependency (not in original mapping, but architecturally sound — `subprocess.run` is an external dependency per DI rules)
- No `__init__.py` creation needed — both `tests/services/` and `tests/adapters/` directories already exist

### Dependency Notes

- **No new pip/uv dependencies required** — `subprocess` is Python stdlib
- `uv` must be on PATH — same assumption as `git` in Story 4.2 (documented in architecture constraints)
- Pydantic `BaseModel` already imported in `core/models.py`

### Version String Conventions (from Story 4.2)

- Config stores versions **without** `v` prefix: `"0.1.3"`
- Git tags include `v` prefix: `"v0.1.3"`
- `sort_versions()` returns without prefix (matching config format)
- `compare_versions()` accepts without prefix
- uv install command uses WITH prefix: `@v0.1.3`
- The `validate_version()` method works with stripped (no `v`) versions since that's what `sort_versions()` returns

### Previous Story Intelligence

**Story 4.2 Learnings:**
- `core/version.py` functions (`sort_versions`, `compare_versions`, `is_newer`) are all pure — safe to import and use directly
- `GitClientAdapter` has constructor-injectable `timeout` — follow same pattern for `SubprocessRunnerAdapter`
- `_clean_url()` uses `str.removeprefix("git+")` — but for uv commands, the `git+` prefix MUST be preserved
- Test structure uses class-based grouping by AC — follow same pattern
- All existing tests (514) pass — maintain this baseline
- `sort_versions()` deduplicates and returns without `v` prefix
- `compare_versions()` handles edge case where current is also latest: `"(installed) (latest)"`

**Story 4.1 Learnings:**
- `UserConfigAdapter.load()` returns `None` when file missing (not an error) — check in `check_for_updates`
- `UserConfig.install.source` contains the `git+` prefixed URL
- `config.model_copy(update=...)` for immutable updates (Pydantic v2 pattern)
- `_serialize_toml()` is used internally by adapter — no need to touch for this story

### Git Workflow

```bash
git checkout main && git pull origin main
git checkout -b feat/4-3-interactive-version-selection
# ... implement ...
# Run CI: uv run ruff check src/ tests/ && uv run pyright src/ && uv run pytest --timeout=30
```

### References

- [Source: architecture.md § `nest update` Command Behavior] — 6-step update flow, display format, Y/n/version input
- [Source: architecture.md § Project Structure] — `services/update_service.py` location
- [Source: architecture.md § PRD Command to Module Mapping] — `UpdateService` uses `GitClient`, `UserConfig`
- [Source: architecture.md § Protocol Boundaries] — Protocol-based DI mandate
- [Source: architecture.md § Dependency Injection] — Manual constructor injection, composition root in CLI
- [Source: architecture.md § Error Handling] — `ConfigError`, result types for recoverable errors
- [Source: epics.md § Story 4.3] — Acceptance criteria, display format, user input options
- [Source: epics.md § Story 4.4] — Downstream dependency (agent template migration after update)
- [Source: epics.md § Story 4.5] — Downstream dependency (CLI integration wires UpdateService)
- [Source: project-context.md § Architecture & DI] — Protocol-based DI rules
- [Source: project-context.md § Error Handling] — Custom exception hierarchy, result types
- [Source: project-context.md § Testing Rules] — Test naming, AAA pattern, mock patterns
- [Source: project-context.md § Python Language Rules] — Modern 3.10+ syntax, type hints
- [Source: 4-1-user-config-management.md] — UserConfig model, adapter patterns, TOML handling
- [Source: 4-2-version-discovery-and-comparison.md] — Version module, GitClientAdapter, protocol patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None — clean implementation, no blockers.

### Completion Notes List

- All 6 tasks completed in order per story spec
- 24 new tests (7 adapter + 17 service) — all pass
- Full suite: 538 passed, 0 failed
- `ruff check` — 0 new issues (1 pre-existing E501 in test_docling_processor.py)
- `pyright` — 0 errors on all new/changed files
- Followed existing patterns: protocol-based DI, BaseModel results, ConfigError for unrecoverable, UpdateResult for recoverable
- `git+` prefix preserved in uv command per story spec
- Non-semver tags handled via `sort_versions()` filtering

### File List

**Created:**
- `src/nest/adapters/subprocess_runner.py` — SubprocessRunnerAdapter wrapping subprocess.run
- `src/nest/services/update_service.py` — UpdateService orchestrating version check + update execution
- `tests/adapters/test_subprocess_runner.py` — 7 tests covering AC6
- `tests/services/test_update_service.py` — 17 tests covering AC1-AC5, AC7-AC10

**Modified:**
- `src/nest/adapters/protocols.py` — Added SubprocessRunnerProtocol + subprocess import
- `src/nest/core/models.py` — Added UpdateCheckResult, UpdateResult models

# Story 3.2: Environment Validation

Status: done
Branch: feat/3-2-environment-validation

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want **to verify my environment is correctly configured**,
so that **I can troubleshoot issues before they cause sync failures**.

## Business Context

This is the second story in Epic 3 (Project Visibility & Health). The `nest doctor` command helps users validate their development environment before encountering runtime failures during document processing.

**Environment validation catches issues early:**
1. **Python version** - Docling requires Python 3.10+
2. **uv availability** - Required for installation and updates
3. **Nest version** - Users know if update is available

This story provides the foundation for the complete `nest doctor` command. Stories 3.3-3.5 will build upon this by adding ML model validation, project state validation, and remediation capabilities.

**Functional Requirements Covered:** FR19 (partial - environment validation only)

## Acceptance Criteria

### AC1: Python Version Validation

**Given** I run `nest doctor`
**When** environment validation runs
**Then** output shows Python version with pass/fail indicator:
```
🩺 Nest Doctor

   Environment:
   ├─ Python:         3.11.4 ✓
```

**Given** Python version is below 3.10
**When** validation runs
**Then** warning shows: `Python: 3.9.1 ✗ (requires 3.10+)`

### AC2: uv Installation Check

**Given** uv is installed and in PATH
**When** validation runs
**Then** output shows: `uv: 0.4.12 ✓`

**Given** uv is not installed or not in PATH
**When** validation runs
**Then** warning shows: `uv: not found ✗`
**And** suggestion displays: "Install uv: https://docs.astral.sh/uv/"

### AC3: Nest Version Check

**Given** Nest version is current
**When** validation runs
**Then** output shows: `Nest: 1.0.0 ✓`

**Given** Nest version is outdated compared to latest available
**When** validation runs (if network available)
**Then** info shows: `Nest: 1.0.0 (1.2.0 available)`
**And** suggestion: "Run `nest update` to upgrade"

**Note:** Latest version check should be non-blocking - if network unavailable or query fails, just show current version without comparison.

### AC4: Rich Formatted Output

**Given** `nest doctor` runs
**When** validation displays
**Then** Rich-formatted output uses:
- ✓ green for passing checks
- ✗ red for failures
- ⚠ yellow for warnings
- Hierarchical tree structure (├─, └─)

### AC5: Doctor Command Works Outside Project

**Given** `nest doctor` runs outside a Nest project (no `.nest_manifest.json`)
**When** command executes
**Then** environment checks still run successfully
**And** output shows environment validation
**And** note indicates: "Run in a Nest project for full diagnostics"

## E2E Testing Requirements

- [x] Existing E2E tests cover this story's functionality: No - doctor command is new
- [x] New E2E tests required: Yes - add E2E tests for doctor environment validation
- [x] E2E test execution required for story completion: Yes

**New E2E Tests Needed:**
1. `test_doctor_shows_environment_status()` - Doctor validates Python/uv/Nest versions
2. `test_doctor_works_outside_project()` - Doctor runs successfully without manifest
3. `test_doctor_handles_missing_uv_gracefully()` - Shows helpful error if uv missing

**Note:** Testing Python version validation may require mocking `sys.version_info` as CI always runs on supported versions.

## Tasks / Subtasks

### Task 1: Create DoctorService with Environment Validation (AC: 1, 2, 3)
- [x] 1.1: Create `src/nest/services/doctor_service.py`
  - Create `EnvironmentReport` dataclass with Python/uv/Nest status fields
  - Implement `check_environment()` method
- [x] 1.2: Implement Python version check
  - Use `sys.version_info` to get current version
  - Compare against minimum required (3, 10, 0)
  - Return status and version string
- [x] 1.3: Implement uv installation check
  - Use `shutil.which("uv")` to check if in PATH
  - If found, execute `uv --version` subprocess to get version
  - Handle subprocess errors gracefully
- [x] 1.4: Implement Nest version check
  - Get current version from `nest.__version__`
  - Optionally query latest version (non-blocking, network-safe)
  - Compare versions and generate status message

### Task 2: Create Doctor CLI Command (AC: 4, 5)
- [x] 2.1: Create `src/nest/cli/doctor_cmd.py`
  - Register `doctor` command with Typer app
  - Implement composition root (inject dependencies)
  - Command should work both inside and outside Nest projects
- [x] 2.2: Add `doctor` command to `cli/main.py` app registration

### Task 3: Implement Rich Output Formatting (AC: 4)
- [x] 3.1: Create `src/nest/ui/doctor_display.py` for Rich formatting
  - Tree-structured output with Rich Tree or Panel
  - Color-coded status indicators (✓ green, ✗ red, ⚠ yellow)
  - Hierarchical display: "Environment:" → sub-items
- [x] 3.2: Format version strings with pass/fail status
  - Python: "3.11.4 ✓" or "3.9.1 ✗ (requires 3.10+)"
  - uv: "0.4.12 ✓" or "not found ✗"
  - Nest: "1.0.0 ✓" or "1.0.0 (1.2.0 available)"
- [x] 3.3: Add helpful messages/suggestions for failures
  - uv: "Install uv: https://docs.astral.sh/uv/"
  - Python: "Upgrade Python to 3.10 or higher"
  - Nest: "Run `nest update` to upgrade"

### Task 4: Add Unit Tests (AC: all)
- [x] 4.1: Create `tests/services/test_doctor_service.py`
  - Test Python version check (supported/unsupported)
  - Test uv installation check (found/not found)
  - Test Nest version check with/without update available
- [x] 4.2: Create `tests/cli/test_doctor_cmd.py`
  - Test successful doctor command execution
  - Test doctor works outside project (no manifest)
- [x] 4.3: Create `tests/ui/test_doctor_display.py`
  - Test output formatting for various states
  - Test color-coded status indicators

### Task 5: Add E2E Tests (AC: all)
- [x] 5.1: Create `tests/e2e/test_doctor_e2e.py`
- [x] 5.2: Add `test_doctor_shows_environment_status()`
- [x] 5.3: Add `test_doctor_works_outside_project()`
- [x] 5.4: Add `test_doctor_handles_missing_uv_gracefully()` (may need PATH manipulation)

### Task 6: Run Full Test Suite
- [x] 6.1: Run `pytest -m "not e2e"` - all unit/integration tests pass
- [x] 6.2: Run `pytest -m "e2e"` - all E2E tests pass
- [x] 6.3: Run `ruff check` - no linting errors
- [x] 6.4: Run `pyright` - no type errors

## Dev Notes

### Architecture Compliance

**Layer Structure:**
- `cli/doctor_cmd.py` → Argument parsing, composition root
- `services/doctor_service.py` → Environment validation orchestration
- `ui/doctor_display.py` → Rich formatted output

**No External Adapters Needed (Yet):**
This story uses only stdlib for environment checks:
- `sys.version_info` for Python version
- `shutil.which()` for uv detection
- `subprocess.run()` for uv version
- `nest.__version__` for current version

Future stories (3.3-3.5) will inject adapters for:
- File system (project validation)
- Docling processor (model validation)
- User config (update checks)

**Composition Root (cli/doctor_cmd.py):**
```python
def create_doctor_service() -> DoctorService:
    return DoctorService()  # No dependencies yet
```

### Data Structures

**EnvironmentReport:**
```python
@dataclass
class EnvironmentStatus:
    """Status for a single environment check."""
    name: str                           # "Python", "uv", "Nest"
    status: Literal["pass", "fail", "warning"]
    current_value: str                  # "3.11.4", "0.4.12", "1.0.0"
    message: str | None = None          # Optional detail message
    suggestion: str | None = None       # Optional remediation

@dataclass
class EnvironmentReport:
    """Complete environment validation report."""
    python: EnvironmentStatus
    uv: EnvironmentStatus
    nest: EnvironmentStatus
    
    @property
    def all_pass(self) -> bool:
        """True if all checks passed (no failures)."""
        return all(
            check.status != "fail"
            for check in [self.python, self.uv, self.nest]
        )
```

### Python Version Check Implementation

```python
import sys
from typing import Literal

def check_python_version() -> EnvironmentStatus:
    """Check if Python version meets minimum requirement."""
    current = sys.version_info
    required = (3, 10, 0)
    
    version_str = f"{current.major}.{current.minor}.{current.micro}"
    
    if current >= required:
        return EnvironmentStatus(
            name="Python",
            status="pass",
            current_value=version_str,
        )
    else:
        return EnvironmentStatus(
            name="Python",
            status="fail",
            current_value=version_str,
            message="requires 3.10+",
            suggestion="Upgrade Python to 3.10 or higher",
        )
```

### uv Installation Check Implementation

```python
import shutil
import subprocess

def check_uv_installation() -> EnvironmentStatus:
    """Check if uv is installed and get version."""
    uv_path = shutil.which("uv")
    
    if not uv_path:
        return EnvironmentStatus(
            name="uv",
            status="fail",
            current_value="not found",
            suggestion="Install uv: https://docs.astral.sh/uv/",
        )
    
    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if result.returncode == 0:
            # Parse version from "uv 0.4.12 (abc123)"
            version = result.stdout.strip().split()[1]
            return EnvironmentStatus(
                name="uv",
                status="pass",
                current_value=version,
            )
        else:
            return EnvironmentStatus(
                name="uv",
                status="warning",
                current_value="found",
                message="could not determine version",
            )
    except (subprocess.TimeoutExpired, Exception):
        return EnvironmentStatus(
            name="uv",
            status="warning",
            current_value="found",
            message="version check failed",
        )
```

### Nest Version Check Implementation

```python
from nest import __version__ as current_version

def check_nest_version() -> EnvironmentStatus:
    """Check Nest version and optionally compare to latest."""
    # For now, just report current version
    # Future: query latest from git tags (non-blocking)
    
    return EnvironmentStatus(
        name="Nest",
        status="pass",
        current_value=current_version,
    )

# Future enhancement (Story 3.3 or later):
def check_nest_version_with_update_check() -> EnvironmentStatus:
    """Check Nest version and compare to latest available."""
    from nest.adapters.git_client import GitClientAdapter
    from nest.adapters.user_config import UserConfigAdapter
    
    config = UserConfigAdapter().load()
    
    if config is None:
        # No config yet, can't check for updates
        return EnvironmentStatus(
            name="Nest",
            status="pass",
            current_value=current_version,
        )
    
    try:
        git_client = GitClientAdapter()
        tags = git_client.list_tags(config.install.source)
        latest = parse_latest_version(tags)
        
        if is_newer(latest, current_version):
            return EnvironmentStatus(
                name="Nest",
                status="warning",
                current_value=current_version,
                message=f"{latest} available",
                suggestion="Run `nest update` to upgrade",
            )
        else:
            return EnvironmentStatus(
                name="Nest",
                status="pass",
                current_value=current_version,
            )
    except Exception:
        # Network error or other issue - not critical
        return EnvironmentStatus(
            name="Nest",
            status="pass",
            current_value=current_version,
        )
```

### Rich Output Format Reference

Expected output format (from epics.md):
```
🩺 Nest Doctor

   Environment:
   ├─ Python:         3.11.4 ✓
   ├─ uv:             0.4.12 ✓
   └─ Nest:           1.0.0 ✓
```

With failures/warnings:
```
🩺 Nest Doctor

   Environment:
   ├─ Python:         3.9.1 ✗ (requires 3.10+)
   │  → Upgrade Python to 3.10 or higher
   ├─ uv:             not found ✗
   │  → Install uv: https://docs.astral.sh/uv/
   └─ Nest:           1.0.0 (1.2.0 available)
      → Run `nest update` to upgrade
```

**Implementation approach:**
- Use Rich `Tree` or `Panel` for hierarchical display
- Use Rich markup for colored icons: `[green]✓[/green]`, `[red]✗[/red]`
- Add sub-items for suggestions with `→` prefix

### Outside Project Behavior

**Key requirement:** Doctor should work OUTSIDE Nest projects.

Unlike `nest status` which requires a project, `nest doctor` validates the development environment which is project-independent.

**Implementation:**
```python
@app.command()
def doctor():
    """Validate development environment and project state.
    
    Checks Python version, uv installation, Nest version, and optionally
    project-specific validations if run inside a Nest project.
    """
    service = create_doctor_service()
    report = service.check_environment()
    
    display_doctor_report(report)
    
    # Check if we're in a project (optional)
    if Path(".nest_manifest.json").exists():
        # Future: add project validation (Stories 3.3-3.4)
        pass
    else:
        console.print("\n[dim]ℹ Run in a Nest project for full diagnostics[/dim]")
```

### Progressive Enhancement for Future Stories

**Story 3.2 (Current):** Environment checks only (Python, uv, Nest)
**Story 3.3:** Add ML model validation
**Story 3.4:** Add project state validation
**Story 3.5:** Add remediation offers

**Design for extension:**
```python
class DoctorService:
    def check_environment(self) -> EnvironmentReport:
        """Check Python, uv, Nest versions."""
        ...
    
    # Future stories will add:
    # def check_ml_models(self) -> ModelReport:
    # def check_project_state(self) -> ProjectReport:
    # def remediate_issues(self, report: FullReport) -> None:
```

### Testing Approach

**Unit Tests:**
- Mock `sys.version_info` to test version comparison logic
- Mock `shutil.which()` to test uv detection
- Mock `subprocess.run()` to test uv version parsing
- Test report dataclass properties

**E2E Tests:**
- Real environment checks (will always pass in CI)
- Test outside project scenario (run in temp dir without manifest)
- Consider: Test missing uv by temporarily modifying PATH (may be fragile)

**Important:** Python and uv will always be available in CI, so tests verify the happy path. Manual testing may be needed for failure scenarios.

### File Impact Summary

| Category | Files | Notes |
|----------|-------|-------|
| New source files | 3 | `doctor_cmd.py`, `doctor_service.py`, `doctor_display.py` |
| Modified source files | 1 | `cli/main.py` (add doctor command) |
| New test files | 4 | `test_doctor_service.py`, `test_doctor_cmd.py`, `test_doctor_display.py`, `test_doctor_e2e.py` |
| **Total new files** | **7** | Small, focused addition |

### Previous Story Learnings

From Story 3.1 (Project Status Display):
- Rich Tree formatting works well for hierarchical display
- Color-coded status indicators improve UX
- Services should return report dataclasses for testability
- Display logic belongs in `ui/` layer, not service

From Story 2.8 (Sync CLI Integration):
- Follow consistent Rich output patterns
- Use `ui/messages.py` helpers for common messages
- Exit code 0 for success, 1 for critical failures
- Non-critical issues (warnings) should not cause exit 1

From Architecture:
- Keep services pure - no subprocess calls in service layer if possible
- Consider moving subprocess operations to adapters for better testing
- **Counterpoint:** For simple stdlib calls like `shutil.which()`, acceptable in service

### Project Structure Notes

Alignment with unified project structure:
- Follows layered architecture: `cli/` → `services/` → `ui/`
- No external adapters needed yet (pure stdlib)
- Future stories will add adapters for model/project validation
- Exit codes: 0 for warnings, 1 only for critical failures

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.2: Environment Validation]
- [Source: _bmad-output/planning-artifacts/architecture.md#Doctor Command]
- [Source: _bmad-output/project-context.md#CLI Output Patterns]
- [Source: _bmad-output/implementation-artifacts/3-1-project-status-display.md] - Pattern reference
- [Source: src/nest/__init__.py] - `__version__` constant
- [Source: src/nest/ui/messages.py] - Rich output helpers

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (via GitHub Copilot in VS Code)

### Debug Log References

N/A - Implementation proceeded without issues

### Completion Notes List

**Implementation Summary:**
- Implemented complete `nest doctor` command for environment validation
- Created DoctorService with Python, uv, and Nest version checks
- Followed red-green-refactor: tests written first, then implementation
- All tests pass: 11 unit tests, 4 CLI tests, 4 UI tests, 4 E2E tests
- Manual testing confirmed: `nest doctor` displays environment status correctly

**Technical Decisions:**
- Used `sys.version_info` tuple indexing (not attributes) for Python 3.10+ compatibility with mocking
- Subprocess timeout of 5 seconds for uv version check to prevent hanging
- Exit code 0 for all cases - doctor is informational, not blocking
- Outside project detection uses `.nest_manifest.json` presence check

**Key Files Created:**
- `src/nest/services/doctor_service.py` - Environment validation service
- `src/nest/cli/doctor_cmd.py` - CLI command integration  
- `src/nest/ui/doctor_display.py` - Rich formatted output
- Complete test coverage across unit, CLI, UI, and E2E layers

**Test Results:**
- All 23 new tests passing
- No regressions in existing test suite
- Ruff linting: ✓ All checks passed
- Pyright type checking: ✓ 0 errors, 0 warnings

**Review Fixes (2026-02-05):**
- Added non-blocking latest-version lookup for Nest with safe fallback
- Hardened uv version parsing for unexpected output
- Updated doctor E2E tests to run CLI and validate output
- Added E2E helper support for env overrides and repo-local CLI execution
- Deferred Docling imports in CLI commands to keep `nest doctor` available without Docling

**Review Fixes Test Results:**
- `pytest tests/services/test_doctor_service.py`
- `pytest tests/e2e/test_doctor_e2e.py -m e2e`

### File List

**New Source Files:**
- src/nest/cli/doctor_cmd.py
- src/nest/services/doctor_service.py
- src/nest/ui/doctor_display.py

**Modified Source Files:**
- src/nest/cli/main.py (added doctor command registration)
- src/nest/services/doctor_service.py (latest version check + uv parsing)
- src/nest/cli/init_cmd.py (lazy Docling import)
- src/nest/cli/sync_cmd.py (lazy Docling import)

**New Test Files:**
- tests/cli/test_doctor_cmd.py (4 tests)
- tests/e2e/test_doctor_e2e.py (4 E2E tests)
- tests/services/test_doctor_service.py (11 tests)
- tests/ui/test_doctor_display.py (4 tests)

**Modified Test Files:**
- tests/e2e/conftest.py (env overrides + repo-local CLI execution)
- tests/e2e/test_doctor_e2e.py (CLI-based E2E assertions)
- tests/services/test_doctor_service.py (update-available + uv parsing tests)

**Total:** 3 new source files, 4 modified source files, 4 new test files, 3 modified test files

# Story 3.5: Issue Remediation

Status: ready-for-dev
Branch: feat/3-5-issue-remediation

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user with detected issues**,
I want **doctor to offer to fix them**,
So that **I don't have to manually troubleshoot**.

## Business Context

This is the fifth story in Epic 3 (Project Visibility & Health). The `nest doctor` command now validates environment (Story 3.2), ML models (Story 3.3), and project state (Story 3.4). This story completes the Epic by adding **interactive remediation** - doctor can now fix detected issues automatically.

**Why Issue Remediation Matters:**
1. **ML models missing** - Users shouldn't manually download; doctor can trigger download
2. **Corrupt manifest** - Doctor can rebuild from processed files instead of requiring manual fix
3. **Missing agent file** - Doctor can regenerate automatically
4. **Missing folders** - Doctor can recreate directory structure
5. **Better UX** - Single command (`nest doctor --fix`) resolves all issues

**Functional Requirements Covered:** FR22 (Doctor: issue remediation)

**Epic Completion:** This story completes Epic 3. All stories (3.1-3.5) will be done.

## Acceptance Criteria

### AC1: Offer ML Model Download

**Given** ML models are missing
**When** doctor completes validation
**Then** prompt offers: "Download missing models? [y/N]"
**And** if Y: triggers model download with progress
**And** download uses existing `DoclingModelDownloader.download_models()` method

### AC2: Offer Manifest Rebuild

**Given** manifest is missing or corrupt
**When** doctor completes validation
**Then** prompt offers: "Rebuild manifest from processed files? [y/N]"
**And** if Y: scans `_nest_context/` and rebuilds manifest
**And** manifest includes all files in `_nest_context/` tracked by Nest
**And** checksums are recomputed for source files in `_nest_sources/`
**And** success message: "Manifest rebuilt successfully"

### AC3: Offer Agent File Regeneration

**Given** agent file is missing
**When** doctor completes validation
**Then** prompt offers: "Regenerate agent file? [y/N]"
**And** if Y: regenerates using AgentWriter with project name from manifest
**And** if manifest is also missing: asks for project name interactively
**And** success message: "Agent file regenerated at .github/agents/nest.agent.md"

### AC4: Offer Folder Recreation

**Given** `_nest_sources/` or `_nest_context/` directories are missing
**When** doctor completes validation
**Then** prompt offers: "Recreate missing folders? [y/N]"
**And** if Y: creates missing folders
**And** success message lists folders created
**And** folders are empty after creation

### AC5: Multiple Issues - Sequential Prompts

**Given** multiple issues are detected (e.g., missing models + missing agent file)
**When** remediation prompts
**Then** each fix is offered separately in order:
   1. ML models (foundational)
   2. Folders (structural)
   3. Manifest (state)
   4. Agent file (last)
**And** user can accept/decline each one independently
**And** progress is shown after each fix attempt

### AC6: Success Case - All Checks Pass

**Given** all checks pass
**When** doctor completes
**Then** output shows: `✓ All systems operational.`
**And** no remediation prompts are shown

### AC7: Non-Interactive Mode with --fix Flag

**Given** `nest doctor --fix` is run
**When** issues are detected
**Then** remediation runs automatically without prompts
**And** results are displayed for each fix attempted
**And** format shows:
```
🔧 Attempting repairs...
   [•] Downloading ML models... ✓
   [•] Rebuilding manifest... ✓
   [•] Regenerating agent file... ✓

   3 issues resolved. Run `nest doctor` to verify.
```

### AC8: Partial Failures Handled Gracefully

**Given** multiple issues detected and auto-fix runs
**When** one fix fails (e.g., network error downloading models)
**Then** error is displayed with reason
**And** remaining fixes are still attempted
**And** final summary shows successes and failures
**And** exit code is 1 if any fix failed

### AC9: Safety - Only Fix Detectable Issues

**Given** doctor runs remediation
**When** processing each fix
**Then** only issues detected in validation are fixed
**And** no destructive operations without confirmation (in interactive mode)
**And** existing files are never overwritten without explicit detection

### AC10: Integration with Existing Doctor Display

**Given** doctor validation completes with issues
**When** display renders
**Then** suggestions from validation reports are shown
**And** remediation prompt appears after full report
**And** format is:
```
🩺 Nest Doctor

   Environment:
   ├─ Python:         3.11.4 ✓
   ├─ uv:             0.4.12 ✓
   └─ Nest:           1.0.0 ✓

   ML Models:
   ├─ Models:         not cached ✗
   └─ Cache path:     ~/.cache/docling/models/
      → Run `nest init` to download models

   ⚠ 1 issue found. Attempt automatic repair? [y/N]:
```

## E2E Testing Requirements

- [x] Existing E2E tests cover this story's functionality: No
- [x] New E2E tests required: Yes - add E2E tests for remediation flows
- [x] E2E test execution required for story completion: Yes

**New E2E Tests Needed:**
1. `test_doctor_fix_recreates_missing_folders()` - Auto-fix recreates `_nest_sources/` and `_nest_context/`
2. `test_doctor_fix_rebuilds_manifest()` - Auto-fix rebuilds manifest from processed files
3. `test_doctor_fix_regenerates_agent_file()` - Auto-fix regenerates missing agent file
4. `test_doctor_fix_handles_multiple_issues()` - Auto-fix resolves multiple issues in sequence
5. `test_doctor_fix_handles_partial_failure()` - Auto-fix continues after one fix fails

**Note:** ML model download test is optional (download is expensive). Mock or skip if needed.

## Tasks / Subtasks

### Task 1: Add Remediation Data Structures (AC: all)
- [ ] 1.1: Add `RemediationResult` dataclass to `doctor_service.py`
  - Fields: `issue: str` (description of issue)
  - Fields: `attempted: bool` (whether fix was attempted)
  - Fields: `success: bool` (whether fix succeeded)
  - Fields: `message: str` (result message for user)
- [ ] 1.2: Add `RemediationReport` dataclass to `doctor_service.py`
  - Fields: `results: list[RemediationResult]`
  - Property: `all_succeeded: bool` (True if all attempted fixes succeeded)
  - Property: `any_attempted: bool` (True if any fix was attempted)

### Task 2: Add Remediation Methods to DoctorService (AC: 1-4, 8)
- [ ] 2.1: Add `rebuild_manifest(project_dir: Path) -> RemediationResult`
  - Scan `_nest_context/` for all `.md` files
  - For each file, check if source exists in `_nest_sources/`
  - Compute SHA-256 checksum for existing sources
  - Build new manifest with current Nest version
  - Write to `.nest_manifest.json`
  - Return success/failure result
- [ ] 2.2: Add `regenerate_agent_file(project_dir: Path, project_name: str) -> RemediationResult`
  - Use `VSCodeAgentWriter` (inject or create)
  - Load project name from manifest if available
  - Write agent file to `.github/agents/nest.agent.md`
  - Create parent directory if needed
  - Return success/failure result
- [ ] 2.3: Add `recreate_folders(project_dir: Path) -> RemediationResult`
  - Check which folders are missing (`_nest_sources/`, `_nest_context/`)
  - Create missing folders
  - Return list of created folders in message
- [ ] 2.4: Add `download_models() -> RemediationResult`
  - If model_checker is None, return failure
  - Call `model_checker.download_models()` if available
  - Handle download errors gracefully
  - Return success/failure result

### Task 3: Add Interactive Remediation Orchestrator (AC: 5, 7, 10)
- [ ] 3.1: Add `remediate_issues_interactive()` method to `DoctorService`
  - Input: validation reports (EnvironmentReport, ModelReport, ProjectReport)
  - Detect all fixable issues in priority order
  - Prompt user for each fix with [y/N]
  - Execute approved fixes
  - Collect results and return RemediationReport
- [ ] 3.2: Add `remediate_issues_auto()` method for --fix flag
  - Input: validation reports
  - Detect all fixable issues
  - Execute all fixes without prompts
  - Collect results and return RemediationReport
  - Rich spinner for each fix attempt

### Task 4: Update Doctor CLI Command (AC: 7, 10)
- [ ] 4.1: Add `--fix` flag to doctor_cmd.py CLI signature
- [ ] 4.2: After validation reports are generated, detect if any issues exist
- [ ] 4.3: If issues exist and not --fix: prompt "Attempt automatic repair? [y/N]"
- [ ] 4.4: If issues exist and --fix: call `remediate_issues_auto()`
- [ ] 4.5: If user accepts prompt: call `remediate_issues_interactive()`
- [ ] 4.6: Display remediation report using new display function

### Task 5: Add Remediation Display Functions (AC: 7, 8, 10)
- [ ] 5.1: Add `display_remediation_report()` to `doctor_display.py`
  - Show spinner/progress during each fix
  - Display success/failure for each fix attempt
  - Use color-coded indicators (✓ green, ✗ red)
  - Show final summary: "X issues resolved"
- [ ] 5.2: Update `display_doctor_report()` to show remediation prompt
  - After all validation reports, check for issues
  - Display formatted prompt if issues exist
  - Return bool indicating if remediation should run

### Task 6: Add Unit Tests (AC: all)
- [ ] 6.1: Add tests to `tests/services/test_doctor_service.py`
  - Test `rebuild_manifest()` with processed files
  - Test `rebuild_manifest()` with empty context folder
  - Test `regenerate_agent_file()` with project name
  - Test `regenerate_agent_file()` without manifest (no project name)
  - Test `recreate_folders()` with missing sources
  - Test `recreate_folders()` with missing context
  - Test `recreate_folders()` with both missing
  - Test `remediate_issues_auto()` with multiple issues
  - Test `remediate_issues_interactive()` prompting logic
- [ ] 6.2: Add tests to `tests/ui/test_doctor_display.py`
  - Test remediation report display
  - Test remediation prompt display

### Task 7: Add E2E Tests (AC: all)
- [ ] 7.1: Add to `tests/e2e/test_doctor_e2e.py`
- [ ] 7.2: Add `test_doctor_fix_recreates_missing_folders()`
  - Init project, delete folders, run `nest doctor --fix`
  - Verify folders are recreated
- [ ] 7.3: Add `test_doctor_fix_rebuilds_manifest()`
  - Init project, sync files, corrupt manifest, run `nest doctor --fix`
  - Verify manifest is valid after fix
- [ ] 7.4: Add `test_doctor_fix_regenerates_agent_file()`
  - Init project, delete agent file, run `nest doctor --fix`
  - Verify agent file exists after fix
- [ ] 7.5: Add `test_doctor_fix_handles_multiple_issues()`
  - Init project, delete agent + folders, run `nest doctor --fix`
  - Verify all issues resolved
- [ ] 7.6: Add `test_doctor_fix_handles_partial_failure()`
  - Create scenario with one fixable + one unfixable issue
  - Verify exit code 1 and partial success message

### Task 8: Update Documentation (AC: 7)
- [ ] 8.1: Update README.md to document `--fix` flag
- [ ] 8.2: Add examples of remediation flows

### Task 9: Run Full Test Suite
- [ ] 9.1: Run `pytest -m "not e2e"` - all unit/integration tests pass
- [ ] 9.2: Run `pytest -m "e2e"` - all E2E tests pass
- [ ] 9.3: Run `./scripts/ci-lint.sh` - passes
- [ ] 9.4: Run `./scripts/ci-typecheck.sh` - passes

## Dev Notes

### Architecture Patterns to Follow

**Dependency Injection:**
```python
class DoctorService:
    def __init__(
        self,
        model_checker: ModelCheckerProtocol | None = None,
        manifest_adapter: ManifestProtocol | None = None,
        agent_writer: AgentWriterProtocol | None = None,
        filesystem: FileSystemProtocol | None = None,
    ):
        # Inject all adapters needed for remediation
```

**Composition Root (doctor_cmd.py):**
```python
def create_doctor_service() -> DoctorService:
    return DoctorService(
        model_checker=DoclingModelDownloader(),
        manifest_adapter=ManifestAdapter(),
        agent_writer=VSCodeAgentWriter(),
        filesystem=FileSystemAdapter(),
    )
```

**Rich Terminal Patterns:**
- Use `console.status()` for spinners during operations
- Use `Tree()` for hierarchical display
- Use `[green]✓[/green]` and `[red]✗[/red]` for status indicators
- Use `Prompt.ask()` for interactive confirmation

### File Structure Requirements

**Files to Modify:**
- `src/nest/services/doctor_service.py` - Add remediation methods
- `src/nest/cli/doctor_cmd.py` - Add --fix flag and remediation logic
- `src/nest/ui/doctor_display.py` - Add remediation display functions

**Files to Create (Tests):**
- None - all test files already exist

**Protocols Already Available:**
- `ModelCheckerProtocol` in `adapters/protocols.py`
- `ManifestProtocol` needed - check if exists or create
- `AgentWriterProtocol` needed - check if exists or create
- `FileSystemProtocol` in `adapters/protocols.py`

### Testing Requirements

**Critical Testing Pattern from Project Context:**
```python
🚨 NEVER run nest init|sync|status|doctor commands directly in the repository
✗ FORBIDDEN: nest init "TestProject"  (pollutes repo with .nest_manifest.json)
✗ FORBIDDEN: nest sync                (creates _nest_context/ artifacts in repo)
✗ FORBIDDEN: nest doctor --fix        (could modify repo state)

✓ CORRECT: pytest tests/services/test_doctor_service.py
✓ CORRECT: pytest tests/e2e/test_doctor_e2e.py -m e2e
✓ CORRECT: pytest -m "not e2e"  (all unit tests)
```

**E2E Test Fixtures:**
All E2E tests must use `temp_project` fixture which creates isolated temporary directory.

### Previous Story Intelligence

**From Story 3.4 (Project State Validation):**
- `ProjectStatus` and `ProjectReport` dataclasses follow established pattern
- `ProjectCheckerProtocol` likely added to protocols.py (verify this)
- Rich Tree display with color-coded indicators already implemented
- Suggestions displayed as child nodes with `→` prefix
- Service returns `None` if checker not injected

**From Story 3.3 (ML Model Validation):**
- `DoclingModelDownloader` implements `ModelCheckerProtocol`
- `download_models()` method exists and shows progress
- Error handling for network failures already implemented

**From Story 3.2 (Environment Validation):**
- Exit code 0 for all cases - doctor is informational
- Display uses Rich for terminal output
- Color scheme: green ✓, red ✗, yellow ⚠

### Git Intelligence Summary

Recent commits show:
- Story 3.2 and 3.3 completed and merged to main
- Story 3.4 created (status: ready-for-dev)
- Conventional commit format enforced: `feat(doctor): description`
- Code review workflow: separate branch → merge to main
- CI scripts run before merge: lint, typecheck, test

### Latest Technical Information

**Python Type Hints (Project uses 3.10+ syntax):**
```python
# ✓ Modern syntax
def method(param: str | None = None) -> list[str]:
    ...

# ✗ Legacy syntax (never use)
from typing import Optional, List
def method(param: Optional[str] = None) -> List[str]:
    ...
```

**Pathlib Usage:**
- All paths use `pathlib.Path`
- Never use string paths
- Use `.exists()`, `.mkdir(parents=True)`, `.read_text()`

**Rich Console Patterns:**
```python
from nest.ui.messages import get_console
console = get_console()

# Spinner
with console.status("Processing..."):
    do_work()

# Prompt
from rich.prompt import Confirm
if Confirm.ask("Continue?"):
    proceed()
```

**Error Handling:**
```python
# Catch specific exceptions
try:
    result = operation()
except ManifestError as e:
    return RemediationResult(
        issue="manifest",
        attempted=True,
        success=False,
        message=f"Failed: {e}",
    )
```

### Project Context Reference

**CRITICAL RULES from project-context.md:**

1. **Python Language Rules:**
   - Naming: `snake_case` for functions/methods, `PascalCase` for classes
   - Imports: Absolute only, never relative
   - Type hints: Modern 3.10+ syntax (`list[]`, `dict[]`, `| None`)
   - Docstrings: Google style for all public functions

2. **Dependency Injection:**
   - All external dependencies injected via protocols
   - Services depend on protocols, not implementations
   - Composition root in CLI layer only
   - Never create adapters inside services

3. **Testing Rules:**
   - Unit tests for all service methods
   - E2E tests for CLI flows
   - Use fixtures for test isolation
   - Mock external dependencies in unit tests
   - Use real dependencies in E2E tests

4. **Error Handling:**
   - Custom exception hierarchy: `NestError` → specific errors
   - Result types for batch operations
   - Two streams: Rich console (user) + logging (file)

5. **Path Handling:**
   - Always use `Path` from `pathlib`
   - Relative paths for manifest portability
   - Absolute paths for operations
   - Cross-platform compatible (use `/` separator)

### Completion Checklist

Before marking story as complete:
- [ ] All AC tested and passing
- [ ] All unit tests pass (`pytest -m "not e2e"`)
- [ ] All E2E tests pass (`pytest -m "e2e"`)
- [ ] Lint passes (`./scripts/ci-lint.sh`)
- [ ] Type check passes (`./scripts/ci-typecheck.sh`)
- [ ] No regressions in existing tests
- [ ] Code follows project style (snake_case, type hints, docstrings)
- [ ] Conventional commit message prepared
- [ ] Sprint status updated

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.5: Issue Remediation]
- [Source: _bmad-output/planning-artifacts/architecture.md#Dependency Injection]
- [Source: _bmad-output/planning-artifacts/architecture.md#Testing Strategy]
- [Source: _bmad-output/project-context.md#Python Language Rules]
- [Source: _bmad-output/project-context.md#Path Handling]
- [Source: _bmad-output/implementation-artifacts/3-4-project-state-validation.md] - Previous story patterns
- [Source: src/nest/services/doctor_service.py] - Existing structure for extension
- [Source: src/nest/adapters/protocols.py] - Protocol definitions
- [Source: src/nest/ui/doctor_display.py] - Display patterns
- [Source: src/nest/adapters/docling_downloader.py] - Model download implementation

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

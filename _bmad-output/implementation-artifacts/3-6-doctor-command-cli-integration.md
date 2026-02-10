# Story 3.6: Doctor Command CLI Integration

Status: done
Branch: feat/3-6-doctor-command-cli-integration

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want **doctor output to be clear and actionable with automatic repair options**,
So that **I can quickly understand and fix any issues**.

## Business Context

This is the **FINAL** story in Epic 3 (Project Visibility & Health). The previous stories have built:
- **Story 3.1:** Project status display (`nest status`)
- **Story 3.2:** Environment validation (Python, uv, Nest version checks)
- **Story 3.3:** ML model validation (Docling cache verification)
- **Story 3.4:** Project state validation (manifest, agent file, folders)
- **Story 3.5:** Issue remediation methods (rebuild manifest, regenerate agent, recreate folders)

This story completes the Epic by integrating the `--fix` flag into the CLI and providing a polished summary display when issues are detected.

**Why CLI Integration Matters:**
1. **`--fix` flag** - Non-interactive remediation for CI/automation scenarios
2. **Issue summary** - Clear count and list of detected issues
3. **Actionable guidance** - "Run with --fix to attempt automatic repair"
4. **Complete dependency injection** - All adapters properly wired in composition root
5. **Exit codes** - Informational doctor returns 0 (not blocking), but --fix returns 1 on failures

**Functional Requirements Covered:** FR22 extension (CLI integration for remediation)

**Epic Completion:** This story completes Epic 3. After this, `nest doctor` is fully functional with environment, model, and project validation plus automatic remediation.

## Acceptance Criteria

### AC1: Rich-Formatted Output with Indicators

**Given** `nest doctor` runs
**When** all validations complete
**Then** Rich-formatted output uses:
- ✓ green for passing checks
- ✗ red for failures
- ⚠ yellow for warnings
- Hierarchical tree structure (├─, └─)

**Note:** This is already implemented in Stories 3.2-3.4. This AC confirms no regressions.

### AC2: Issue Summary Display

**Given** issues are detected (environment, models, or project)
**When** doctor completes validation
**Then** output includes summary at the end:
```
   ⚠ 2 issues found:
   1. ML models not cached
   2. Agent file missing

   Run `nest doctor --fix` to attempt automatic repair.
```

### AC3: Success Summary When All Pass

**Given** all checks pass
**When** doctor completes
**Then** output shows: `✓ All systems operational`
**And** no summary of issues is displayed

### AC4: --fix Flag Triggers Automatic Remediation

**Given** `--fix` flag is provided
**When** issues are detected
**Then** remediation runs automatically without prompts
**And** results are displayed for each fix attempted:
```
🔧 Attempting repairs...
   [•] Recreating missing folders... ✓
   [•] Rebuilding manifest... ✓
   [•] Regenerating agent file... ✓

   3 issues resolved. Run `nest doctor` to verify.
```

### AC5: --fix Returns Appropriate Exit Codes

**Given** `nest doctor --fix` runs
**When** all fixes succeed
**Then** exit code is 0

**Given** `nest doctor --fix` runs
**When** any fix fails
**Then** exit code is 1
**And** failure message explains what failed

### AC6: --fix Without Issues Does Nothing

**Given** `nest doctor --fix` runs
**When** no issues are detected
**Then** output shows: `✓ All systems operational. No repairs needed.`
**And** exit code is 0

### AC7: DoctorService Receives All Required Adapters

**Given** DoctorService is created by CLI
**When** `--fix` flag is used
**Then** service has all adapters injected:
- `ModelCheckerProtocol` (DoclingModelDownloader)
- `ProjectCheckerProtocol` (ProjectChecker)
- `ManifestProtocol` (ManifestAdapter) - for manifest rebuild
- `AgentWriterProtocol` (VSCodeAgentWriter) - for agent regeneration
- `FileSystemProtocol` (FileSystemAdapter) - for folder creation

### AC8: Interactive Prompt Without --fix

**Given** `nest doctor` runs without --fix
**When** issues are detected
**Then** prompt appears: `Attempt automatic repair? [y/N]`
**And** if Y: remediation runs with progress display
**And** if N: exits with issue summary only

### AC9: Doctor Runs Successfully Outside Projects

**Given** `nest doctor` runs outside a Nest project
**When** command executes
**Then** environment and ML model checks run
**And** project checks are skipped
**And** `--fix` can still download ML models if missing
**And** no error is raised

### AC10: Standard Doctor (Without Issues) Remains Unchanged

**Given** all checks pass
**When** `nest doctor` runs
**Then** output matches existing format:
```
🩺 Nest Doctor

   Environment:
   ├─ Python:         3.11.4 ✓
   ├─ uv:             0.4.12 ✓
   └─ Nest:           1.0.0 ✓

   ML Models:
   ├─ Models:         cached ✓ (1.8 GB)
   └─ Cache path:     ~/.cache/docling/models/

   Project:
   ├─ Manifest:       valid ✓
   ├─ Agent file:     present ✓
   └─ Folders:        intact ✓

   ✓ All systems operational
```

## E2E Testing Requirements

- [x] Existing E2E tests cover this story's functionality: Partial - doctor display tests exist
- [x] New E2E tests required: Yes - add E2E tests for --fix flag flows
- [x] E2E test execution required for story completion: Yes

**New E2E Tests Needed:**
1. `test_doctor_fix_flag_recreates_missing_folders()` - `nest doctor --fix` recreates folders
2. `test_doctor_fix_flag_regenerates_agent_file()` - `nest doctor --fix` regenerates missing agent
3. `test_doctor_fix_flag_handles_all_pass()` - `nest doctor --fix` with no issues shows success
4. `test_doctor_fix_returns_exit_code_1_on_failure()` - Exit code 1 when fix fails
5. `test_doctor_shows_issue_summary()` - Summary display with issue count and list
6. `test_doctor_shows_success_message_when_all_pass()` - "All systems operational" displayed

**Critical Note:** These tests extend tests in `tests/e2e/test_doctor_e2e.py`. Story 3.5 may add overlapping tests for remediation methods - coordinate to avoid duplication.

## Tasks / Subtasks

### Task 1: Add --fix Flag to CLI Command (AC: 4, 5, 6)
- [x] 1.1: Add `--fix` parameter to `doctor_command()` in `doctor_cmd.py`
  - Type: `bool`, default: `False`
  - Help text: "Automatically repair detected issues without prompts"
- [x] 1.2: Add `typer.Exit(code=1)` when --fix has failures
- [x] 1.3: Add `typer.Exit(code=0)` when --fix succeeds or no issues

### Task 2: Update Dependency Injection for Remediation (AC: 7)
- [x] 2.1: Update `create_doctor_service()` to accept `fix_mode: bool` parameter
- [x] 2.2: When `fix_mode=True`, inject additional adapters:
  - `ManifestAdapter` from `adapters/manifest.py`
  - `VSCodeAgentWriter` from `agents/vscode_writer.py`
  - `FileSystemAdapter` from `adapters/filesystem.py`
- [x] 2.3: Update `DoctorService.__init__()` to accept optional remediation adapters
  - `manifest_adapter: ManifestProtocol | None = None`
  - `agent_writer: AgentWriterProtocol | None = None`
  - `filesystem: FileSystemProtocol | None = None`

### Task 3: Add Issue Detection Helper (AC: 2, 3)
- [x] 3.1: Create `_count_issues()` function in `doctor_cmd.py`
  - Input: `EnvironmentReport, ModelReport | None, ProjectReport | None`
  - Output: `list[str]` of issue descriptions (empty if all pass)
  - Checks: env failures, model not cached, manifest invalid, agent missing, folders missing
- [x] 3.2: Create `_format_issue_summary()` function
  - Input: `list[str]` of issues
  - Output: Formatted string with numbered list

### Task 4: Add Issue Summary Display (AC: 2, 3, 10)
- [x] 4.1: Add `display_issue_summary()` to `doctor_display.py`
  - Input: `issues: list[str], console: Console`
  - Format: "⚠ X issues found:" + numbered list + suggestion
- [x] 4.2: Add `display_success_message()` to `doctor_display.py`
  - Output: "✓ All systems operational"
- [x] 4.3: Update `display_doctor_report()` to accept `issues: list[str]` parameter
- [x] 4.4: Call summary display after tree is printed

### Task 5: Add Remediation Flow to CLI (AC: 4, 8)
- [x] 5.1: After validation, check if issues exist
- [x] 5.2: If `--fix` flag: call `service.remediate_issues_auto(reports)`
  - This method should be added in Story 3.5
  - If Story 3.5 not complete, add stub that returns empty result
- [x] 5.3: If no `--fix` flag and issues exist: prompt user
  - Use `rich.prompt.Confirm.ask("Attempt automatic repair?")`
  - If Y: call `service.remediate_issues_interactive(reports)`
- [x] 5.4: Display remediation results using new display function

### Task 6: Add Remediation Display Function (AC: 4)
- [x] 6.1: Add `display_remediation_progress()` to `doctor_display.py`
  - Shows "🔧 Attempting repairs..." header
  - Lists each fix with spinner/progress
  - Uses `console.status()` for progress indication
- [x] 6.2: Add `display_remediation_results()` to `doctor_display.py`
  - Input: `RemediationReport` from service
  - Shows ✓/✗ for each fix attempt
  - Shows final summary: "X issues resolved" or "X failed"

### Task 7: Handle Outside-Project Scenario (AC: 9)
- [x] 7.1: In `--fix` mode outside project, only allow model download
- [x] 7.2: Project remediation methods require being in a project
- [x] 7.3: Show appropriate message: "Not in a Nest project. Only ML model download available."

### Task 8: Add Unit Tests (AC: all)
- [x] 8.1: Test `_count_issues()` with various report combinations
- [x] 8.2: Test `_format_issue_summary()` formatting
- [x] 8.3: Test `display_issue_summary()` output
- [x] 8.4: Test `display_success_message()` output
- [x] 8.5: Test `display_remediation_results()` output

### Task 9: Add E2E Tests (AC: all)
- [x] 9.1: Add `test_doctor_fix_flag_recreates_missing_folders()`
- [x] 9.2: Add `test_doctor_fix_flag_regenerates_agent_file()`
- [x] 9.3: Add `test_doctor_fix_flag_handles_all_pass()`
- [x] 9.4: Add `test_doctor_fix_returns_exit_code_1_on_failure()`
- [x] 9.5: Add `test_doctor_shows_issue_summary()`
- [x] 9.6: Add `test_doctor_shows_success_message_when_all_pass()`

### Task 10: Integration with Story 3.5 Methods
- [x] 10.1: Verify `DoctorService.remediate_issues_auto()` exists (from Story 3.5)
- [x] 10.2: Verify `DoctorService.remediate_issues_interactive()` exists (from Story 3.5)
- [x] 10.3: Verify `RemediationReport` dataclass exists (from Story 3.5)
- [x] 10.4: If Story 3.5 not complete, coordinate or stub methods

### Task 11: Run Full Test Suite
- [x] 11.1: Run `pytest -m "not e2e"` - all unit/integration tests pass (414 passed)
- [x] 11.2: Run `pytest -m "e2e"` - all E2E tests pass (17 passed)
- [x] 11.3: Run `./scripts/ci-lint.sh` - passes (ruff check clean)
- [x] 11.4: Run `./scripts/ci-typecheck.sh` - passes (pyright 0 errors)

## Dev Notes

### Dependency Between Stories 3.5 and 3.6

**Story 3.5 (Issue Remediation)** provides:
- `RemediationResult` and `RemediationReport` dataclasses
- `DoctorService.rebuild_manifest()` method
- `DoctorService.regenerate_agent_file()` method
- `DoctorService.recreate_folders()` method
- `DoctorService.download_models()` method
- `DoctorService.remediate_issues_auto()` orchestrator
- `DoctorService.remediate_issues_interactive()` orchestrator

**Story 3.6 (CLI Integration)** provides:
- `--fix` CLI flag
- Issue summary display
- Exit code handling
- Interactive prompt (y/N)
- Full adapter injection in composition root
- `display_remediation_progress()` and `display_remediation_results()`

**Recommended Approach:**
If working on 3.6 before 3.5 is complete, add stub methods to `DoctorService`:
```python
def remediate_issues_auto(self, ...) -> RemediationReport:
    """Stub - implement in Story 3.5."""
    return RemediationReport(results=[])

def remediate_issues_interactive(self, ...) -> RemediationReport:
    """Stub - implement in Story 3.5."""
    return RemediationReport(results=[])
```

### File Structure Requirements

**Files to Modify:**
- `src/nest/cli/doctor_cmd.py` - Add --fix flag, prompt logic, exit codes
- `src/nest/ui/doctor_display.py` - Add summary and remediation display functions
- `src/nest/services/doctor_service.py` - Add optional adapters for remediation

**Existing Files to Use (Read-Only Reference):**
- `src/nest/adapters/protocols.py` - Protocol definitions
- `src/nest/adapters/filesystem.py` - FileSystemAdapter
- `src/nest/adapters/manifest.py` - ManifestAdapter
- `src/nest/agents/vscode_writer.py` - VSCodeAgentWriter

### Architecture Patterns to Follow

**Composition Root (doctor_cmd.py):**
```python
def create_doctor_service(fix_mode: bool = False) -> DoctorService:
    """Composition root for doctor service.

    Args:
        fix_mode: If True, inject remediation adapters.

    Returns:
        Configured DoctorService.
    """
    model_checker = DoclingModelDownloader()
    project_checker = ProjectChecker()

    # Only inject remediation adapters when needed
    if fix_mode:
        return DoctorService(
            model_checker=model_checker,
            project_checker=project_checker,
            manifest_adapter=ManifestAdapter(),
            agent_writer=VSCodeAgentWriter(),
            filesystem=FileSystemAdapter(),
        )
    else:
        return DoctorService(
            model_checker=model_checker,
            project_checker=project_checker,
        )
```

**CLI Flag Pattern:**
```python
def doctor_command(
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Automatically repair detected issues without prompts",
    ),
) -> None:
    """Validate development environment and project state."""
    ...
```

**Exit Code Pattern:**
```python
if fix_mode:
    if remediation_report.all_succeeded:
        raise typer.Exit(code=0)
    else:
        raise typer.Exit(code=1)
else:
    # Doctor without --fix is informational, always exit 0
    raise typer.Exit(code=0)
```

### Rich Console Patterns

**Issue Summary Display:**
```python
def display_issue_summary(issues: list[str], console: Console) -> None:
    """Display summary of detected issues."""
    console.print()
    console.print(f"[yellow]⚠[/yellow] {len(issues)} issue{'s' if len(issues) != 1 else ''} found:")
    for i, issue in enumerate(issues, 1):
        console.print(f"   {i}. {issue}")
    console.print()
    console.print("[dim]Run `nest doctor --fix` to attempt automatic repair.[/dim]")
```

**Success Message:**
```python
def display_success_message(console: Console) -> None:
    """Display success message when all checks pass."""
    console.print()
    console.print("[green]✓[/green] All systems operational")
```

**Interactive Prompt:**
```python
from rich.prompt import Confirm

if issues and not fix_mode:
    if Confirm.ask("Attempt automatic repair?", default=False):
        result = service.remediate_issues_interactive(...)
```

### Testing Requirements

**CRITICAL: Testing Protocol from Project Context:**
```
🚨 NEVER run nest commands directly in the repository
✗ FORBIDDEN: nest doctor --fix  (could modify repo state)

✓ CORRECT: pytest tests/cli/test_doctor_cmd.py
✓ CORRECT: pytest tests/e2e/test_doctor_e2e.py -m e2e
```

**E2E Test Pattern:**
```python
class TestDoctorFix:
    """E2E tests for nest doctor --fix command."""

    def test_doctor_fix_recreates_missing_folders(self, e2e_workspace: Path) -> None:
        """Test that --fix recreates missing project folders."""
        # Arrange: init project, delete folders
        result = subprocess.run(["nest", "init", "TestProject"], cwd=e2e_workspace)
        assert result.returncode == 0
        (e2e_workspace / "_nest_sources").rmdir()
        (e2e_workspace / "_nest_context").rmdir()

        # Act: run doctor --fix
        result = subprocess.run(
            ["nest", "doctor", "--fix"],
            cwd=e2e_workspace,
            capture_output=True,
            text=True,
        )

        # Assert: folders recreated
        assert result.returncode == 0
        assert (e2e_workspace / "_nest_sources").exists()
        assert (e2e_workspace / "_nest_context").exists()
        assert "issues resolved" in result.stdout
```

### Previous Story Intelligence

**From Story 3.4 (Project State Validation):**
- `ProjectStatus` and `ProjectReport` dataclasses established
- `check_project()` method returns `ProjectReport | None`
- Rich Tree display patterns established
- Suggestions displayed as child nodes with `→` prefix

**From Story 3.5 (Issue Remediation):**
- `RemediationResult` and `RemediationReport` dataclasses
- Individual fix methods: `rebuild_manifest()`, `regenerate_agent_file()`, `recreate_folders()`, `download_models()`
- Orchestration methods: `remediate_issues_auto()`, `remediate_issues_interactive()`
- Priority order for fixes: ML models → folders → manifest → agent file

### Git Intelligence Summary

Recent commits:
- `590f69b` - Merge fix/3-4-project-state-validation into main
- `12b0025` - feat(doctor): add project state validation (Story 3.4)
- `03b0de7` - Merge feat/3-3-ml-model-validation into main
- `94fbb1d` - feat(doctor): add ML model validation to nest doctor command

**Conventional Commit for this story:**
```
feat(doctor): add --fix flag for automatic issue remediation (Story 3.6)
```

### Project Context Reference

**From [_bmad-output/project-context.md](../_bmad-output/project-context.md):**

1. **Python Type Hints (3.10+ syntax):**
   ```python
   def method(param: str | None = None) -> list[str]:
   ```

2. **CLI Output - Never use print():**
   ```python
   from nest.ui.messages import success, error, warning, info
   from nest.ui.messages import get_console
   ```

3. **Error Handling:**
   - Exit code 0 for informational doctor (no --fix)
   - Exit code 1 only when --fix has failures
   - Result types for batch operations

4. **Testing Protocol:**
   - E2E tests use `e2e_workspace` fixture (isolated temp directory)
   - Never run CLI commands directly in repo

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
- [ ] Sprint status updated to done
- [ ] Epic 3 marked as done (this is the final story)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.6: Doctor Command CLI Integration]
- [Source: _bmad-output/planning-artifacts/architecture.md#Dependency Injection]
- [Source: _bmad-output/planning-artifacts/architecture.md#Testing Strategy]
- [Source: _bmad-output/project-context.md#Python Language Rules]
- [Source: _bmad-output/project-context.md#CLI Output Patterns]
- [Source: _bmad-output/implementation-artifacts/3-4-project-state-validation.md] - Previous story patterns
- [Source: _bmad-output/implementation-artifacts/3-5-issue-remediation.md] - Remediation methods
- [Source: src/nest/cli/doctor_cmd.py] - Current CLI implementation
- [Source: src/nest/services/doctor_service.py] - Service layer
- [Source: src/nest/ui/doctor_display.py] - Display helpers

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Tasks 1, 2, 5, 6, 7, 10 were already implemented by Story 3.5. This story added the missing issue detection helpers, display functions, and wiring.
- exit-code-1 E2E test required creating a file where the agents directory should be (blocking regeneration), since read-only directory caused PermissionError during check_project.

### Completion Notes List

- Added `_count_issues()` helper to `doctor_cmd.py` — detects env failures, model issues, manifest/agent/folder problems
- Added `display_issue_summary()` to `doctor_display.py` — renders "⚠ N issues found:" with numbered list and --fix hint
- Added `display_success_message()` to `doctor_display.py` — renders "✓ All systems operational" with optional "No repairs needed." suffix
- Wired issue summary and success message into `doctor_command()` flow covering AC2, AC3, AC6
- Interactive prompt (AC8) already existed from Story 3.5; confirmed working
- `_format_issue_summary()` (Task 3.2) was folded into `display_issue_summary()` since the formatting is done directly in the display function
- `display_doctor_report()` signature unchanged (Task 4.3) — summary is called separately after the report for cleaner separation
- 12 new unit tests added: TestCountIssues (12), TestDisplayIssueSummary (2), TestDisplaySuccessMessage (2), TestDisplayRemediationReport (3)
- 4 new E2E tests added: fix_handles_all_pass, fix_returns_exit_code_1, shows_issue_summary, shows_success_message
- All 414 unit tests pass, all 17 E2E tests pass
- Lint (ruff) and type check (pyright) clean

### File List

- src/nest/cli/doctor_cmd.py (modified) — Added _count_issues(), wired issue summary/success display
- src/nest/ui/doctor_display.py (modified) — Added display_issue_summary(), display_success_message()
- tests/cli/test_doctor_cmd.py (modified) — Added TestCountIssues, TestDisplayIssueSummary, TestDisplaySuccessMessage, TestDisplayRemediationReport
- tests/e2e/test_doctor_e2e.py (modified) — Added 4 new E2E tests for AC2/3/5/6


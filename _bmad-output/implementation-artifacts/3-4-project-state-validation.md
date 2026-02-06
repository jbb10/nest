# Story 3.4: Project State Validation

Status: ready-for-dev
Branch: feat/3-4-project-state-validation

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want **to verify my project structure is intact**,
so that **I know sync and agent will work correctly**.

## Business Context

This is the fourth story in Epic 3 (Project Visibility & Health). The `nest doctor` command now includes environment validation (Story 3.2) and ML model validation (Story 3.3). This story extends it with project state validation to help users verify their Nest project is properly configured before running `nest sync`.

**Why Project State Validation Matters:**
1. **Manifest integrity** - Corrupt or missing manifest will cause sync failures
2. **Agent file presence** - Missing agent file means Copilot won't have project context
3. **Folder structure** - Missing source/output folders will cause sync failures
4. **Version compatibility** - Manifest version may require migration

**Functional Requirements Covered:** FR21 (Doctor: project state validation)

## Acceptance Criteria

### AC1: Display Project Validation Section

**Given** I run `nest doctor` in a Nest project
**When** project validation runs
**Then** output shows:
```
   Project:
   ├─ Manifest:       valid ✓
   ├─ Agent file:     present ✓
   └─ Folders:        intact ✓
```

### AC2: Detect Missing Manifest

**Given** `.nest_manifest.json` is missing
**When** validation runs
**Then** error shows: `Manifest: missing ✗`
**And** suggestion shows: `→ Run 'nest init' to create project`

### AC3: Detect Corrupt Manifest

**Given** manifest JSON is corrupt or invalid
**When** validation runs
**Then** error shows: `Manifest: invalid JSON ✗` or `Manifest: invalid structure ✗`
**And** suggestion shows: `→ Run 'nest doctor --fix' to rebuild (Story 3.5)`

### AC4: Detect Missing Agent File

**Given** `.github/agents/nest.agent.md` is missing
**When** validation runs
**Then** warning shows: `Agent file: missing ✗`
**And** suggestion shows: `→ Run 'nest init' to regenerate`

### AC5: Detect Missing Folders

**Given** `_nest_sources/` or `_nest_context/` directories are missing
**When** validation runs
**Then** warning shows: `Folders: _nest_sources/ missing ✗` or `Folders: _nest_context/ missing ✗`
**And** suggestion shows: `→ Run 'nest init' to recreate`

### AC6: Detect Manifest Version Mismatch

**Given** manifest version doesn't match current Nest version
**When** validation runs
**Then** info shows: `Manifest: v0.9.0 (migration available)`
**And** suggestion shows: `→ Run 'nest update' to migrate`

### AC7: Project Validation Only Runs In Project

**Given** `nest doctor` runs outside a Nest project
**When** command executes
**Then** environment checks run
**And** ML model checks run
**And** project validation is SKIPPED
**And** note indicates: "Run in a Nest project for full diagnostics"

### AC8: Integrate with Existing Doctor Output

**Given** `nest doctor` runs in a Nest project
**When** all validations complete
**Then** output shows Environment → ML Models → Project sections:
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
```

## E2E Testing Requirements

- [x] Existing E2E tests cover this story's functionality: Partial - doctor tests exist but not for project validation
- [x] New E2E tests required: Yes - add E2E tests for project validation display
- [x] E2E test execution required for story completion: Yes

**New E2E Tests Needed:**
1. `test_doctor_shows_project_section_in_project()` - Doctor displays Project section when in Nest project
2. `test_doctor_skips_project_section_outside_project()` - Doctor skips Project section outside Nest project
3. `test_doctor_detects_missing_manifest()` - Doctor shows manifest missing error
4. `test_doctor_detects_missing_agent_file()` - Doctor shows agent file warning

**Note:** Testing corrupt manifest and missing folders requires careful fixture setup in E2E tests.

## Tasks / Subtasks

### Task 1: Create Project Validation Data Structures (AC: all)
- [ ] 1.1: Create `ProjectStatus` dataclass in `doctor_service.py`
  - Fields: `manifest_status: Literal["valid", "missing", "invalid_json", "invalid_structure", "version_mismatch"]`
  - Fields: `manifest_version: str | None`
  - Fields: `agent_file_present: bool`
  - Fields: `folders_status: Literal["intact", "sources_missing", "context_missing", "both_missing"]`
  - Fields: `suggestions: list[str]` for remediation hints
- [ ] 1.2: Create `ProjectReport` dataclass in `doctor_service.py`
  - Fields: `status: ProjectStatus`
  - Property: `all_pass` for quick status check
  - Property: `has_warnings` for warnings-only status

### Task 2: Add Project Validation Protocol (AC: all)
- [ ] 2.1: Add `ProjectCheckerProtocol` to `adapters/protocols.py`
  - Method: `manifest_exists(project_dir: Path) -> bool`
  - Method: `load_manifest(project_dir: Path) -> Manifest` (can raise ManifestError)
  - Method: `agent_file_exists(project_dir: Path) -> bool`
  - Method: `source_folder_exists(project_dir: Path) -> bool`
  - Method: `context_folder_exists(project_dir: Path) -> bool`

### Task 3: Create ProjectChecker Adapter (AC: all)
- [ ] 3.1: Create `ProjectChecker` class in `adapters/project_checker.py`
  - Inject `ManifestAdapter` and `FileSystemAdapter` (or use directly)
  - Implement all protocol methods
  - Handle `ManifestError` exceptions gracefully
- [ ] 3.2: Add folder path constants (use existing from sync_cmd if available)
  - `_nest_sources/` for source documents
  - `_nest_context/` for processed output
  - `.github/agents/nest.agent.md` for agent file

### Task 4: Extend DoctorService with Project Validation (AC: all)
- [ ] 4.1: Add optional `project_checker: ProjectCheckerProtocol | None` to `__init__`
- [ ] 4.2: Add `check_project(project_dir: Path) -> ProjectReport | None` method
  - Return None if project_checker is None
  - Check manifest existence and validity
  - Check agent file presence
  - Check folder structure
  - Compare manifest version with current Nest version
  - Build appropriate suggestions list

### Task 5: Update Doctor CLI Command (AC: 7, 8)
- [ ] 5.1: Update `doctor_cmd.py` to inject `ProjectChecker`
- [ ] 5.2: Detect if running in Nest project (check manifest exists)
- [ ] 5.3: Call `check_project(Path.cwd())` only if in project
- [ ] 5.4: Pass `ProjectReport` to display function

### Task 6: Extend Doctor Display for Project Output (AC: all)
- [ ] 6.1: Add `display_project_report()` function to `doctor_display.py`
  - Rich Tree format matching environment and model sections
  - Color-coded status indicators (✓ green, ✗ red, ⚠ yellow)
  - Suggestions displayed with → prefix
- [ ] 6.2: Update `display_doctor_report()` to accept optional `ProjectReport`
- [ ] 6.3: Handle all manifest states with appropriate messaging

### Task 7: Add Unit Tests (AC: all)
- [ ] 7.1: Add tests to `tests/services/test_doctor_service.py`
  - Test `check_project()` with valid project
  - Test `check_project()` with missing manifest
  - Test `check_project()` with corrupt manifest
  - Test `check_project()` with missing agent file
  - Test `check_project()` with missing folders
  - Test `check_project()` with version mismatch
- [ ] 7.2: Add tests to `tests/adapters/test_project_checker.py`
  - Test all protocol methods with various states
- [ ] 7.3: Add tests to `tests/ui/test_doctor_display.py`
  - Test project report display for all states
  - Test suggestion formatting

### Task 8: Add E2E Tests (AC: all)
- [ ] 8.1: Add to `tests/e2e/test_doctor_e2e.py`
- [ ] 8.2: Add `test_doctor_shows_project_section_in_project()`
- [ ] 8.3: Add `test_doctor_skips_project_section_outside_project()`
- [ ] 8.4: Add `test_doctor_detects_missing_manifest()`
- [ ] 8.5: Add `test_doctor_detects_missing_agent_file()`

### Task 9: Run Full Test Suite
- [ ] 9.1: Run `pytest -m "not e2e"` - all unit/integration tests pass
- [ ] 9.2: Run `pytest -m "e2e"` - all E2E tests pass
- [ ] 9.3: Run `ruff check` - no linting errors
- [ ] 9.4: Run `pyright` - no type errors

## Dev Notes

### Architecture Compliance

**Layer Structure:**
- `cli/doctor_cmd.py` → Composition root, injects `ProjectChecker`
- `services/doctor_service.py` → Orchestrates project validation via protocol
- `adapters/project_checker.py` → Implements project validation methods
- `adapters/protocols.py` → Defines `ProjectCheckerProtocol`
- `ui/doctor_display.py` → Rich formatted output

**Protocol-Based DI:**
The service should depend on a protocol, not the concrete `ProjectChecker`:

```python
@runtime_checkable
class ProjectCheckerProtocol(Protocol):
    """Protocol for project state validation."""
    
    def manifest_exists(self, project_dir: Path) -> bool: ...
    def load_manifest(self, project_dir: Path) -> Manifest: ...
    def agent_file_exists(self, project_dir: Path) -> bool: ...
    def source_folder_exists(self, project_dir: Path) -> bool: ...
    def context_folder_exists(self, project_dir: Path) -> bool: ...
```

**Composition Root (cli/doctor_cmd.py):**
```python
def create_doctor_service() -> DoctorService:
    return DoctorService(
        model_checker=DoclingModelDownloader(),
        project_checker=ProjectChecker(),  # New injection
    )
```

### Data Structures

**ProjectStatus:**
```python
@dataclass
class ProjectStatus:
    """Status for project state validation."""
    manifest_status: Literal["valid", "missing", "invalid_json", "invalid_structure", "version_mismatch"]
    manifest_version: str | None  # Version from manifest if readable
    current_version: str  # Current Nest version for comparison
    agent_file_present: bool
    folders_status: Literal["intact", "sources_missing", "context_missing", "both_missing"]
    suggestions: list[str]  # Remediation hints
```

**ProjectReport:**
```python
@dataclass
class ProjectReport:
    """Complete project state validation report."""
    status: ProjectStatus
    
    @property
    def all_pass(self) -> bool:
        """True if manifest valid, agent present, folders intact."""
        return (
            self.status.manifest_status == "valid"
            and self.status.agent_file_present
            and self.status.folders_status == "intact"
        )
    
    @property
    def has_warnings(self) -> bool:
        """True if only warnings (no errors)."""
        # Missing agent file is a warning, not error
        # Version mismatch is info, not error
        return (
            self.status.manifest_status in ("valid", "version_mismatch")
            and self.status.folders_status == "intact"
        )
```

### DoctorService Extension

```python
class DoctorService:
    """Validates development environment and project state."""
    
    def __init__(
        self,
        model_checker: ModelCheckerProtocol | None = None,
        project_checker: ProjectCheckerProtocol | None = None,
    ) -> None:
        """Initialize doctor service.
        
        Args:
            model_checker: Optional model checker for ML validation.
            project_checker: Optional project checker for project validation.
        """
        self._model_checker = model_checker
        self._project_checker = project_checker
    
    def check_project(self, project_dir: Path) -> ProjectReport | None:
        """Check project state.
        
        Args:
            project_dir: Path to project root directory.
        
        Returns:
            ProjectReport if project checker is configured, None otherwise.
        """
        if self._project_checker is None:
            return None
        
        suggestions: list[str] = []
        
        # Check manifest
        if not self._project_checker.manifest_exists(project_dir):
            manifest_status = "missing"
            manifest_version = None
            suggestions.append("Run `nest init` to create project")
        else:
            try:
                manifest = self._project_checker.load_manifest(project_dir)
                manifest_version = manifest.nest_version
                
                # Check version compatibility
                if manifest_version != nest.__version__:
                    manifest_status = "version_mismatch"
                    suggestions.append("Run `nest update` to migrate")
                else:
                    manifest_status = "valid"
            except ManifestError as e:
                if "invalid JSON" in str(e):
                    manifest_status = "invalid_json"
                else:
                    manifest_status = "invalid_structure"
                manifest_version = None
                suggestions.append("Run `nest doctor --fix` to rebuild")
        
        # Check agent file
        agent_present = self._project_checker.agent_file_exists(project_dir)
        if not agent_present:
            suggestions.append("Run `nest init` to regenerate agent file")
        
        # Check folders
        sources_exist = self._project_checker.source_folder_exists(project_dir)
        context_exist = self._project_checker.context_folder_exists(project_dir)
        
        if sources_exist and context_exist:
            folders_status = "intact"
        elif not sources_exist and not context_exist:
            folders_status = "both_missing"
            suggestions.append("Run `nest init` to recreate folders")
        elif not sources_exist:
            folders_status = "sources_missing"
            suggestions.append("Run `nest init` to recreate _nest_sources/")
        else:
            folders_status = "context_missing"
            suggestions.append("Run `nest init` to recreate _nest_context/")
        
        return ProjectReport(
            status=ProjectStatus(
                manifest_status=manifest_status,
                manifest_version=manifest_version,
                current_version=nest.__version__,
                agent_file_present=agent_present,
                folders_status=folders_status,
                suggestions=suggestions,
            )
        )
```

### ProjectChecker Adapter

```python
"""Project state checker adapter."""

from pathlib import Path

from nest.adapters.manifest import ManifestAdapter
from nest.core.models import Manifest

# Folder names (consistent with sync_cmd.py)
SOURCE_FOLDER = "_nest_sources"
CONTEXT_FOLDER = "_nest_context"
AGENT_FILE_PATH = ".github/agents/nest.agent.md"


class ProjectChecker:
    """Adapter for project state validation.
    
    Implements ProjectCheckerProtocol.
    """
    
    def __init__(self) -> None:
        """Initialize project checker."""
        self._manifest_adapter = ManifestAdapter()
    
    def manifest_exists(self, project_dir: Path) -> bool:
        """Check if manifest exists."""
        return self._manifest_adapter.exists(project_dir)
    
    def load_manifest(self, project_dir: Path) -> Manifest:
        """Load manifest (may raise ManifestError)."""
        return self._manifest_adapter.load(project_dir)
    
    def agent_file_exists(self, project_dir: Path) -> bool:
        """Check if agent file exists."""
        return (project_dir / AGENT_FILE_PATH).exists()
    
    def source_folder_exists(self, project_dir: Path) -> bool:
        """Check if source folder exists."""
        return (project_dir / SOURCE_FOLDER).is_dir()
    
    def context_folder_exists(self, project_dir: Path) -> bool:
        """Check if context folder exists."""
        return (project_dir / CONTEXT_FOLDER).is_dir()
```

### Rich Output Format

Expected output format (all valid):
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
```

Expected output format (issues found):
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
   ├─ Manifest:       invalid JSON ✗
   │  → Run `nest doctor --fix` to rebuild
   ├─ Agent file:     missing ✗
   │  → Run `nest init` to regenerate
   └─ Folders:        _nest_sources/ missing ✗
      → Run `nest init` to recreate
```

Expected output format (version mismatch):
```
   Project:
   ├─ Manifest:       v0.9.0 ⚠ (migration available)
   │  → Run `nest update` to migrate
   ├─ Agent file:     present ✓
   └─ Folders:        intact ✓
```

### Display Function

```python
def display_project_report(report: ProjectReport, tree: Tree) -> None:
    """Render a ProjectReport to the tree.
    
    Args:
        report: Project validation report.
        tree: Rich tree to add project section to.
    """
    project = tree.add("Project")
    status = report.status
    
    # Manifest status line
    if status.manifest_status == "valid":
        manifest_line = "Manifest: valid [green]✓[/green]"
    elif status.manifest_status == "missing":
        manifest_line = "Manifest: missing [red]✗[/red]"
    elif status.manifest_status == "invalid_json":
        manifest_line = "Manifest: invalid JSON [red]✗[/red]"
    elif status.manifest_status == "invalid_structure":
        manifest_line = "Manifest: invalid structure [red]✗[/red]"
    else:  # version_mismatch
        manifest_line = f"Manifest: v{status.manifest_version} [yellow]⚠[/yellow] [dim](migration available)[/dim]"
    
    manifest_node = project.add(manifest_line)
    
    # Agent file status
    if status.agent_file_present:
        agent_line = "Agent file: present [green]✓[/green]"
    else:
        agent_line = "Agent file: missing [red]✗[/red]"
    
    agent_node = project.add(agent_line)
    
    # Folders status
    if status.folders_status == "intact":
        folders_line = "Folders: intact [green]✓[/green]"
    elif status.folders_status == "sources_missing":
        folders_line = "Folders: _nest_sources/ missing [red]✗[/red]"
    elif status.folders_status == "context_missing":
        folders_line = "Folders: _nest_context/ missing [red]✗[/red]"
    else:  # both_missing
        folders_line = "Folders: both missing [red]✗[/red]"
    
    folders_node = project.add(folders_line)
    
    # Add suggestions to appropriate nodes
    # (Suggestions should be associated with the relevant node)
    for suggestion in status.suggestions:
        if "manifest" in suggestion.lower() or "migrate" in suggestion.lower():
            manifest_node.add(f"→ {suggestion}")
        elif "agent" in suggestion.lower():
            agent_node.add(f"→ {suggestion}")
        elif "folder" in suggestion.lower() or "recreate" in suggestion.lower():
            folders_node.add(f"→ {suggestion}")
```

### Testing Approach

**Unit Tests (mocked):**
- Mock `ProjectChecker` via protocol
- Test all manifest states: valid, missing, invalid_json, invalid_structure, version_mismatch
- Test agent file presence/absence
- Test folder states: intact, sources_missing, context_missing, both_missing
- Test display formatting for all states

**E2E Tests (real filesystem):**
- Create temp project with `nest init` fixture
- Verify Project section appears in output
- Delete manifest and verify error display
- Delete agent file and verify warning display

**Mock Example:**
```python
class MockProjectChecker:
    def __init__(
        self,
        manifest_exists: bool = True,
        manifest_valid: bool = True,
        manifest_version: str = "1.0.0",
        agent_exists: bool = True,
        sources_exist: bool = True,
        context_exist: bool = True,
    ):
        self._manifest_exists = manifest_exists
        self._manifest_valid = manifest_valid
        self._manifest_version = manifest_version
        self._agent_exists = agent_exists
        self._sources_exist = sources_exist
        self._context_exist = context_exist
    
    def manifest_exists(self, project_dir: Path) -> bool:
        return self._manifest_exists
    
    def load_manifest(self, project_dir: Path) -> Manifest:
        if not self._manifest_valid:
            raise ManifestError("Invalid JSON")
        return Manifest(
            nest_version=self._manifest_version,
            project_name="Test",
            last_sync=None,
            files={},
        )
    
    def agent_file_exists(self, project_dir: Path) -> bool:
        return self._agent_exists
    
    def source_folder_exists(self, project_dir: Path) -> bool:
        return self._sources_exist
    
    def context_folder_exists(self, project_dir: Path) -> bool:
        return self._context_exist
```

### Project Structure Notes

**Files to Modify:**
- `src/nest/services/doctor_service.py` - Add ProjectStatus, ProjectReport, check_project()
- `src/nest/adapters/protocols.py` - Add ProjectCheckerProtocol
- `src/nest/cli/doctor_cmd.py` - Inject project checker, call check_project()
- `src/nest/ui/doctor_display.py` - Add display_project_report(), update main display

**Files to Create:**
- `src/nest/adapters/project_checker.py` - ProjectChecker implementation

**Test Files to Modify:**
- `tests/services/test_doctor_service.py` - Add project validation tests
- `tests/ui/test_doctor_display.py` - Add project display tests
- `tests/e2e/test_doctor_e2e.py` - Add project validation E2E tests

**Test Files to Create:**
- `tests/adapters/test_project_checker.py` - ProjectChecker unit tests

### CRITICAL: Dev Agent Testing Protocol

```
🚨 NEVER run nest init|sync|status|doctor commands directly in the repository
✗ FORBIDDEN: nest init "TestProject"  (pollutes repo with .nest_manifest.json)
✗ FORBIDDEN: nest sync                (creates _nest_context/ artifacts in repo)
✗ FORBIDDEN: nest doctor              (could create files if --fix used)

✓ CORRECT: pytest tests/services/test_doctor_service.py
✓ CORRECT: pytest tests/e2e/test_doctor_e2e.py -m e2e
✓ CORRECT: pytest -m "not e2e"  (all unit tests)
```

### Previous Story Learnings

From Story 3.3 (ML Model Validation):
- `ModelStatus` and `ModelReport` dataclasses follow established pattern
- `ModelCheckerProtocol` added to protocols.py with `@runtime_checkable`
- Display uses Rich Tree with color-coded indicators
- Suggestions displayed as child nodes with `→` prefix
- Service method returns `None` if checker not injected

From Story 3.2 (Environment Validation):
- DoctorService uses dataclasses for reports (EnvironmentStatus, EnvironmentReport)
- doctor_display.py uses Rich Tree for hierarchical output
- Color-coded indicators: `[green]✓[/green]`, `[red]✗[/red]`, `[yellow]⚠[/yellow]`
- Exit code 0 for all cases - doctor is informational

From Architecture:
- Protocol-based DI for testability
- Services depend on protocols, not implementations
- Composition root in CLI layer
- ManifestAdapter already exists and handles JSON validation

### Git Workflow Reference

```bash
# Before starting implementation
git checkout main && git pull origin main
git checkout -b feat/3-4-project-state-validation

# After completing implementation
./scripts/ci-lint.sh && ./scripts/ci-typecheck.sh && ./scripts/ci-test.sh

# Commit with conventional format
git commit -m "feat(doctor): add project state validation"
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.4: Project State Validation]
- [Source: _bmad-output/planning-artifacts/architecture.md#Testing Strategy]
- [Source: _bmad-output/project-context.md#Architecture & Dependency Injection]
- [Source: _bmad-output/implementation-artifacts/3-3-ml-model-validation.md] - Pattern reference for model validation
- [Source: src/nest/adapters/manifest.py] - Existing manifest adapter with error handling
- [Source: src/nest/services/doctor_service.py] - Existing doctor service with model validation
- [Source: src/nest/ui/doctor_display.py] - Existing display patterns

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

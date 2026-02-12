# Story 4.4: Agent Template Migration Check

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user running `nest update`**,
I want **to know if my local agent file is outdated after a version update**,
So that **I get the latest agent instructions and my `@nest` agent always uses the best possible template**.

## Business Context

This is the **FOURTH** story in Epic 4 (Tool Updates & Maintenance). It builds directly on:
- **Story 4.1** (User Config Management) — reads `project_name` from the manifest to regenerate the agent file with the correct project name
- **Story 4.2** (Version Discovery & Comparison) — no direct dependency, but runs as part of the same `nest update` flow
- **Story 4.3** (Interactive Version Selection) — runs AFTER a successful version update completes; `UpdateService.execute_update()` returns `UpdateResult(success=True)` as the trigger

**Downstream Dependencies:**
- **Story 4.5:** Update Command CLI Integration — wires `AgentMigrationService` into the CLI flow (called after `UpdateService.execute_update()` succeeds), adds Rich UI prompts for user confirmation

**Functional Requirements Covered:** FR16 (Agent template migration — check if local agent file is outdated and prompt for update)

**Architecture References:**
- [Source: architecture.md § Agent Generation] — AgentWriter protocol, VSCodeAgentWriter, Jinja template
- [Source: architecture.md § Project Structure] — `agents/vscode_writer.py`, `agents/templates/vscode.md.jinja`
- [Source: architecture.md § Protocol Boundaries] — `AgentWriterProtocol`, `FileSystemProtocol`, `ManifestProtocol`
- [Source: architecture.md § Dependency Injection] — Manual constructor injection
- [Source: epics.md § Story 4.4] — Acceptance criteria, backup behavior, skip logic

## Acceptance Criteria

### AC1: Agent Template Comparison — Outdated Detection

**Given** a Nest project exists with `.github/agents/nest.agent.md`
**When** `AgentMigrationService.check_migration_needed()` is called with the project directory
**Then** it renders the current bundled template (via `VSCodeAgentWriter`) into a string
**And** reads the local agent file content
**And** compares the two strings
**And** returns an `AgentMigrationCheckResult` with `migration_needed=True` if they differ

### AC2: Agent Template Comparison — Up-to-Date

**Given** a Nest project exists with `.github/agents/nest.agent.md`
**When** the local file content matches the current bundled template (rendered with same project name)
**Then** `AgentMigrationCheckResult.migration_needed` is `False`
**And** `message` is `"Agent file is up to date"`

### AC3: Agent File Regeneration with Backup

**Given** `migration_needed=True` and user confirms update
**When** `AgentMigrationService.execute_migration()` is called
**Then** the existing agent file is backed up as `nest.agent.md.bak` in the same directory
**And** `AgentWriter.generate()` regenerates the file with the current project name
**And** returns `AgentMigrationResult(success=True, backed_up=True)`

### AC4: User Declines Agent Update

**Given** `migration_needed=True`
**When** user declines the migration (handled by CLI layer in Story 4.5)
**Then** `execute_migration()` is NOT called
**And** the local agent file remains unchanged
**And** Story 4.5's CLI displays: `"Keeping existing agent file. Run nest doctor to update later."`

### AC5: No Agent File Exists

**Given** a Nest project exists BUT `.github/agents/nest.agent.md` is missing
**When** `check_migration_needed()` runs
**Then** `AgentMigrationCheckResult.migration_needed` is `True`
**And** `agent_file_missing` is `True`
**And** `message` is `"Agent file missing — will be created"`

### AC6: No Manifest (Not a Nest Project)

**Given** the directory has no `.nest_manifest.json`
**When** `check_migration_needed()` runs
**Then** `AgentMigrationCheckResult.migration_needed` is `False`
**And** `skipped` is `True`
**And** `message` is `"Not a Nest project — skipping agent check"`

### AC7: Regeneration Without Backup (Missing Agent File)

**Given** `agent_file_missing=True` (AC5 scenario)
**When** `execute_migration()` is called
**Then** `AgentWriter.generate()` creates the file fresh (no backup needed)
**And** returns `AgentMigrationResult(success=True, backed_up=False)`

### AC8: Template Rendering Uses Project Name from Manifest

**Given** the manifest contains `project_name: "Nike"`
**When** `check_migration_needed()` renders the template for comparison
**Then** it loads the manifest to extract `project_name`
**And** renders the template with `project_name="Nike"`
**And** compares against the local file

### AC9: Backup File Already Exists

**Given** `nest.agent.md.bak` already exists from a previous migration
**When** `execute_migration()` creates a new backup
**Then** the old `.bak` file is overwritten with the current agent file content
**And** the agent file is regenerated fresh

### AC10: Filesystem Error During Migration

**Given** backup or regeneration fails (e.g., permission error, disk full)
**When** the error is caught
**Then** `AgentMigrationResult(success=False, error="...")` is returned
**And** the original agent file is preserved if possible (backup-first strategy)

## Tasks / Subtasks

- [x] **Task 1: Add Result Models** (AC: #1, #2, #5, #6, #7, #10)
  - [x] 1.1 Add `AgentMigrationCheckResult` to `src/nest/core/models.py`
  - [x] 1.2 Add `AgentMigrationResult` to `src/nest/core/models.py`

- [x] **Task 2: Add `render()` Method to VSCodeAgentWriter** (AC: #1, #2, #8)
  - [x] 2.1 Add `render(project_name: str) -> str` method to `VSCodeAgentWriter` that returns the rendered template string WITHOUT writing to disk
  - [x] 2.2 Refactor `generate()` to internally call `render()` then write (DRY)
  - [x] 2.3 Add `render()` to `AgentWriterProtocol` in `adapters/protocols.py`

- [x] **Task 3: Implement `AgentMigrationService`** (AC: #1-#3, #5-#10)
  - [x] 3.1 Create `src/nest/services/agent_migration_service.py`
  - [x] 3.2 Constructor accepts: `agent_writer: AgentWriterProtocol`, `filesystem: FileSystemProtocol`, `manifest: ManifestProtocol`
  - [x] 3.3 Implement `check_migration_needed(project_dir: Path) -> AgentMigrationCheckResult`:
    - Check manifest exists (via `ManifestProtocol.exists()`) — if not, return skipped result (AC6)
    - Load manifest to get `project_name` (AC8)
    - Check if agent file exists at `project_dir / ".github" / "agents" / "nest.agent.md"`
    - If agent file missing → return `migration_needed=True, agent_file_missing=True` (AC5)
    - If agent file exists → render template with project_name, read local file, compare (AC1/AC2)
  - [x] 3.4 Implement `execute_migration(project_dir: Path) -> AgentMigrationResult`:
    - Load manifest to get `project_name`
    - Determine agent file path: `project_dir / ".github" / "agents" / "nest.agent.md"`
    - If agent file exists → backup to `nest.agent.md.bak` (AC3, AC9)
    - Regenerate via `agent_writer.generate(project_name, agent_path)` (AC3, AC7)
    - Wrap in try/except for filesystem errors (AC10)
    - Return `AgentMigrationResult`

- [x] **Task 4: Write Unit Tests for `render()` Method** (AC: #1, #2, #8)
  - [x] 4.1 Update `tests/agents/test_vscode_writer.py`
  - [x] 4.2 Test `render()` returns string with correct project name interpolation
  - [x] 4.3 Test `render()` does NOT write to filesystem
  - [x] 4.4 Test `generate()` still works (produces same output as before — no regressions)

- [x] **Task 5: Write Unit Tests for `AgentMigrationService`** (AC: #1-#3, #5-#10)
  - [x] 5.1 Create `tests/services/test_agent_migration_service.py`
  - [x] 5.2 Test `check_migration_needed` returns `migration_needed=True` when content differs (AC1)
  - [x] 5.3 Test `check_migration_needed` returns `migration_needed=False` when content matches (AC2)
  - [x] 5.4 Test `check_migration_needed` returns `agent_file_missing=True` when agent file doesn't exist (AC5)
  - [x] 5.5 Test `check_migration_needed` returns `skipped=True` when no manifest (AC6)
  - [x] 5.6 Test `check_migration_needed` renders template with project name from manifest (AC8)
  - [x] 5.7 Test `execute_migration` creates backup and regenerates file (AC3)
  - [x] 5.8 Test `execute_migration` creates file without backup when agent file missing (AC7)
  - [x] 5.9 Test `execute_migration` overwrites existing `.bak` file (AC9)
  - [x] 5.10 Test `execute_migration` returns error result on filesystem failure (AC10)
  - [x] 5.11 Test `execute_migration` loads project name from manifest

- [x] **Task 6: Run CI Validation**
  - [x] 6.1 Lint passes (`ruff check` — 0 new issues)
  - [x] 6.2 Typecheck passes (`pyright` — 0 errors)
  - [x] 6.3 All tests pass (existing 538 + new → 555 total)

## Dev Notes

### Architecture Patterns to Follow

**Layer Placement:**
- `services/agent_migration_service.py` → **Services layer** — orchestrates the migration check and execution
- `agents/vscode_writer.py` → **Agents layer** — add `render()` method for template-to-string rendering
- `adapters/protocols.py` → Update `AgentWriterProtocol` with `render()` method
- `core/models.py` → Add `AgentMigrationCheckResult` and `AgentMigrationResult` models

**Composition Root:** `AgentMigrationService` will be instantiated in `cli/update_cmd.py` (Story 4.5). For this story, no CLI wiring is needed — the service is standalone and fully testable.

### Why a Separate Service?

The `UpdateService` handles version discovery and `uv tool install`. Agent template migration is a distinct concern that:
- Requires different dependencies (`AgentWriterProtocol`, `ManifestProtocol`, `FileSystemProtocol`) compared to `UpdateService` (`GitClientProtocol`, `SubprocessRunnerProtocol`, `UserConfigProtocol`)
- Can be called independently from `nest doctor --fix` (already partially exists in `DoctorService`)
- Keeps single-responsibility principle: update = version management, migration = template management

### Result Model Design

```python
# core/models.py — Add alongside existing models

class AgentMigrationCheckResult(BaseModel):
    """Result of checking whether agent template needs migration.

    Attributes:
        migration_needed: True if local agent file differs from current template.
        agent_file_missing: True if agent file doesn't exist at all.
        skipped: True if check was skipped (e.g., not a Nest project).
        message: Human-readable status description.
    """

    migration_needed: bool
    agent_file_missing: bool = False
    skipped: bool = False
    message: str


class AgentMigrationResult(BaseModel):
    """Result of executing agent template migration.

    Attributes:
        success: Whether the migration completed successfully.
        backed_up: Whether the old file was backed up before replacement.
        error: Error message if migration failed.
    """

    success: bool
    backed_up: bool = False
    error: str | None = None
```

### AgentWriterProtocol Update

```python
# adapters/protocols.py — Update existing AgentWriterProtocol

@runtime_checkable
class AgentWriterProtocol(Protocol):
    def generate(self, project_name: str, output_path: Path) -> None: ...

    def render(self, project_name: str) -> str:
        """Render the agent template to a string without writing to disk.

        Args:
            project_name: Name of the project for interpolation.

        Returns:
            Rendered agent file content as string.
        """
        ...
```

### VSCodeAgentWriter Update

```python
# agents/vscode_writer.py — Add render() method

class VSCodeAgentWriter:
    def render(self, project_name: str) -> str:
        """Render agent template to string without writing to disk.

        Args:
            project_name: Project name to interpolate.

        Returns:
            Rendered template content.
        """
        template = self._jinja_env.get_template("vscode.md.jinja")
        return template.render(project_name=project_name)

    def generate(self, project_name: str, output_path: Path) -> None:
        """Generate VS Code agent file (existing method, refactored)."""
        output_dir = output_path.parent
        if not self._filesystem.exists(output_dir):
            self._filesystem.create_directory(output_dir)

        content = self.render(project_name)  # DRY: reuse render()
        self._filesystem.write_text(output_path, content)
```

### AgentMigrationService Design

```python
# services/agent_migration_service.py

from pathlib import Path

from nest.adapters.protocols import (
    AgentWriterProtocol,
    FileSystemProtocol,
    ManifestProtocol,
)
from nest.core.models import AgentMigrationCheckResult, AgentMigrationResult

AGENT_FILE_PATH = Path(".github") / "agents" / "nest.agent.md"
AGENT_BACKUP_SUFFIX = ".bak"


class AgentMigrationService:
    """Service for checking and executing agent template migrations.

    Compares the local agent file against the current bundled template
    and performs backup + regeneration when templates change.
    """

    def __init__(
        self,
        agent_writer: AgentWriterProtocol,
        filesystem: FileSystemProtocol,
        manifest: ManifestProtocol,
    ) -> None: ...

    def check_migration_needed(
        self,
        project_dir: Path,
    ) -> AgentMigrationCheckResult: ...

    def execute_migration(
        self,
        project_dir: Path,
    ) -> AgentMigrationResult: ...
```

### Agent File Path Constant

The agent file path `".github/agents/nest.agent.md"` is already used in:
- `init_service.py` — hardcoded as `target_dir / ".github" / "agents" / "nest.agent.md"`
- `project_checker.py` — likely uses same path for `agent_file_exists()`

Define `AGENT_FILE_PATH` as a constant in the service. Alternatively, if you want a shared constant, you could add it to `core/paths.py`, but verify first if `project_checker.py` already defines one. The priority is consistency — if the path is already defined somewhere, import and reuse it.

### Backup Strategy

The backup is a simple file copy:
1. Read current agent file content via `filesystem.read_text(agent_path)`
2. Write content to `agent_path.with_suffix(agent_path.suffix + ".bak")` → i.e., `nest.agent.md.bak`
3. Then regenerate via `agent_writer.generate(project_name, agent_path)`

This means if step 3 fails, the original is still recoverable from `.bak`. If step 2 fails, the original is untouched.

### Testing Strategy

**Unit tests for `AgentMigrationService`** — Mock all three protocols:

```python
# tests/services/test_agent_migration_service.py

class MockAgentWriter:
    """Mock for AgentWriterProtocol with render() support."""

    def __init__(self, template_content: str = "rendered-template") -> None:
        self.template_content = template_content
        self.generate_calls: list[tuple[str, Path]] = []

    def render(self, project_name: str) -> str:
        return self.template_content.replace("{{project_name}}", project_name)

    def generate(self, project_name: str, output_path: Path) -> None:
        self.generate_calls.append((project_name, output_path))
```

Use `MockFileSystem` from `conftest.py` for filesystem operations. Use `MockManifest` patterns from existing tests for manifest operations.

**Key test scenarios:**
- Content match → `migration_needed=False`
- Content differs → `migration_needed=True`
- No agent file → `migration_needed=True`, `agent_file_missing=True`
- No manifest → `skipped=True`
- Backup created before regeneration
- Filesystem error → `success=False` with error message

### Existing Patterns to Reuse

| Pattern | Source | How to Reuse |
|---------|--------|-------------|
| AgentWriterProtocol | `adapters/protocols.py` | Extend with `render()` method |
| VSCodeAgentWriter | `agents/vscode_writer.py` | Add `render()`, refactor `generate()` |
| ManifestProtocol | `adapters/protocols.py` | Use `exists()` and `load()` |
| FileSystemProtocol | `adapters/protocols.py` | Use `read_text()`, `write_text()`, `exists()` |
| Result models | `core/models.py` | Follow `UpdateResult` pattern with BaseModel |
| Service constructor | `services/init_service.py` | Protocol-only constructor params |
| Test mocks | `tests/agents/test_vscode_writer.py` | Extend MockFileSystem from conftest |
| MockManifest | `tests/conftest.py` or services tests | Follow existing mock patterns |

### Files to Create

| File | Purpose |
|------|---------|
| `src/nest/services/agent_migration_service.py` | `AgentMigrationService` — orchestrates template comparison + migration |
| `tests/services/test_agent_migration_service.py` | Unit tests for `AgentMigrationService` |

### Files to Modify

| File | Change |
|------|--------|
| `src/nest/agents/vscode_writer.py` | Add `render()` method, refactor `generate()` to use it |
| `src/nest/adapters/protocols.py` | Add `render()` to `AgentWriterProtocol` |
| `src/nest/core/models.py` | Add `AgentMigrationCheckResult`, `AgentMigrationResult` |
| `tests/agents/test_vscode_writer.py` | Add tests for `render()` method |

### Files NOT to Touch

- `cli/update_cmd.py` — CLI integration and Rich prompts happen in Story 4.5
- `cli/main.py` — No command registration changes needed
- `services/update_service.py` — Keep version management separate from template migration
- `services/doctor_service.py` — Already has agent regeneration via remediation; this service is complementary (doctor remediation creates fresh, migration service does comparison + backup)
- `ui/messages.py` — No new UI messages needed (display logic is Story 4.5)
- `core/version.py` — Not relevant to template comparison
- `adapters/git_client.py` — Not needed
- `adapters/user_config.py` — Not needed (project name comes from manifest, not user config)

### Project Structure Notes

- `services/agent_migration_service.py` is a new service not in the original architecture's service list, but is architecturally sound — it follows the same layered pattern and protocol-based DI
- The architecture specifies `AgentWriterProtocol` for extensibility; adding `render()` extends this without breaking existing consumers
- `DoctorService` already has agent file regeneration capability via `_agent_writer` — the migration service is distinct because it handles comparison + backup (doctor just blindly regenerates)
- No `__init__.py` creation needed — `tests/services/` directory already exists

### Dependency Notes

- **No new pip/uv dependencies required** — all functionality uses existing stdlib + Jinja2 (already a dependency via `vscode_writer.py`)
- Pydantic `BaseModel` already imported in `core/models.py`
- `ManifestProtocol.load()` raises `ManifestError` if manifest is corrupt — handle gracefully in migration check

### Previous Story Intelligence

**Story 4.3 Learnings:**
- 538 tests baseline — maintain this + add new
- `ruff check` has 1 pre-existing E501 in `test_docling_processor.py` — not a blocker
- `ConfigError` pattern: raise for unrecoverable (no config), return result for recoverable (update failed)
- Follow same test class grouping by AC
- `BaseModel` for all result types (not `@dataclass`) — consistent with `UpdateCheckResult`, `UpdateResult`

**Story 4.1 Learnings:**
- `ManifestProtocol.load()` raises `FileNotFoundError` if file missing — check `exists()` first
- `ManifestProtocol.exists()` returns bool — safe to call without try/except

**Init Service Pattern:**
- `InitService` uses `agent_writer.generate(project_name.strip(), agent_path)` — same pattern for migration
- Agent path is `target_dir / ".github" / "agents" / "nest.agent.md"` — match this exactly

### Edge Cases to Handle

1. **Manifest exists but is corrupt** — `manifest.load()` raises `ManifestError`. Catch and return skipped result with appropriate message.
2. **Agent file with different project name** — Template rendering uses manifest's `project_name`. If user manually edited the project name in the manifest, the comparison correctly detects the difference.
3. **Whitespace differences** — String comparison is exact. If the Jinja template adds/removes whitespace between versions, it correctly triggers migration.
4. **Concurrent write** — Not a concern for CLI tool (single-user, single-process).

### Git Workflow

```bash
git checkout main && git pull origin main
git checkout -b feat/4-4-agent-template-migration-check
# ... implement ...
# Run CI: uv run ruff check src/ tests/ && uv run pyright src/ && uv run pytest --timeout=30
```

### References

- [Source: architecture.md § Agent Generation] — AgentWriter protocol, VSCodeAgentWriter, Jinja template
- [Source: architecture.md § Project Structure] — `agents/vscode_writer.py`, `agents/templates/vscode.md.jinja`
- [Source: architecture.md § Protocol Boundaries] — AgentWriterProtocol, FileSystemProtocol, ManifestProtocol
- [Source: architecture.md § Dependency Injection] — Manual constructor injection, composition root in CLI
- [Source: architecture.md § Error Handling] — Result types for recoverable errors
- [Source: epics.md § Story 4.4] — Acceptance criteria, backup behavior, skip logic
- [Source: epics.md § Story 4.5] — Downstream dependency (CLI integration prompts user for confirmation)
- [Source: project-context.md § Architecture & DI] — Protocol-based DI rules
- [Source: project-context.md § Error Handling] — Custom exception hierarchy, result types
- [Source: project-context.md § Testing Rules] — Test naming, AAA pattern, mock patterns
- [Source: project-context.md § Python Language Rules] — Modern 3.10+ syntax, type hints
- [Source: 4-3-interactive-version-selection.md] — UpdateService design, subprocess patterns, test conventions
- [Source: 4-1-user-config-management.md] — UserConfig model, adapter patterns
- [Source: agents/vscode_writer.py] — Existing VSCodeAgentWriter implementation
- [Source: agents/templates/vscode.md.jinja] — Current agent template
- [Source: tests/agents/test_vscode_writer.py] — Existing test patterns for agent writer

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (GitHub Copilot)

### Debug Log References

None — clean implementation, all tests passed on first run after lint fixes.

### Completion Notes List

- Task 1: Added `AgentMigrationCheckResult` and `AgentMigrationResult` Pydantic BaseModels to `core/models.py`
- Task 2: Added `render()` to `VSCodeAgentWriter` (returns template string), refactored `generate()` to call `render()` internally (DRY), added `render()` to `AgentWriterProtocol`
- Task 3: Created `AgentMigrationService` with `check_migration_needed()` and `execute_migration()`. Handles all ACs: manifest-missing skip, agent-file-missing detection, content comparison, backup-first strategy, filesystem error handling
- Task 4: Added 4 tests for `render()` method in `test_vscode_writer.py` (returns string, no filesystem writes, matches generate output, multiple interpolations)
- Task 5: Added 13 tests for `AgentMigrationService` covering all ACs (content differs/matches, file missing, no manifest, corrupt manifest, backup+regenerate, no-backup fresh create, overwrite .bak, filesystem failure, manifest load failure, project name from manifest, generate failure preserves backup)
- Task 6: All CI green — ruff 0 new issues, pyright 0 errors, 555 tests passing (was 538, +17 new)
- Updated `MockAgentWriter` in `conftest.py` with `render()` support; updated `MockManifest` to support returning a manifest from `load()`; added `mock_manifest_with_project` fixture

### File List

- `src/nest/core/models.py` — Added `AgentMigrationCheckResult`, `AgentMigrationResult`
- `src/nest/adapters/protocols.py` — Added `render()` to `AgentWriterProtocol`
- `src/nest/agents/vscode_writer.py` — Added `render()` method, refactored `generate()` to use it
- `src/nest/services/agent_migration_service.py` — NEW: `AgentMigrationService` with `check_migration_needed()` and `execute_migration()`
- `tests/agents/test_vscode_writer.py` — Added `TestRender` class with 4 tests
- `tests/services/test_agent_migration_service.py` — NEW: 13 tests across `TestCheckMigrationNeeded` and `TestExecuteMigration`
- `tests/conftest.py` — Updated `MockAgentWriter` with `render()`, updated `MockManifest` with optional `_manifest`, added `mock_manifest_with_project` fixture

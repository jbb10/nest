# Story 1.4: Init Command CLI Integration

Status: review
Branch: feat/1-4-init-command-cli-integration

---

## Story

**As a** user,
**I want** `nest init` to provide clear feedback and next-step guidance,
**So that** I know exactly what to do after initialization.

---

## Acceptance Criteria

### AC1: Success Output with Next Steps
**Given** I successfully run `nest init "Nike"`
**When** all steps complete
**Then** the console displays:
```
✓ Project "Nike" initialized!

Next steps:
  1. Drop your documents into raw_inbox/
  2. Run `nest sync` to process them
  3. Open VS Code and use @nest in Copilot Chat

Supported formats: PDF, DOCX, PPTX, XLSX, HTML
```

### AC2: Step Progress Display
**Given** the init command runs
**When** each step executes
**Then** Rich spinners/checkmarks show progress:
- `[•] Creating project structure... ✓`
- `[•] Generating agent file... ✓`
- `[•] Checking ML models...` (then download or cached message)

### AC3: Composition Root Pattern
**Given** the CLI layer (`init_cmd.py`)
**When** it creates the InitService
**Then** it injects: FileSystemAdapter, VSCodeAgentWriter, ManifestAdapter, DoclingModelDownloader
**And** follows the composition root pattern from Architecture

### AC4: Error Handling with Guidance
**Given** any step fails
**When** error is caught
**Then** appropriate error message is shown (What → Why → Action format)
**And** cleanup is performed for partial state

### AC5: Duplicate Init Command Resolution
**Given** `init_cmd.py` and `main.py` both define init commands
**When** the CLI is invoked
**Then** only ONE init command implementation exists
**And** the composition root is in a single location

---

## Tasks / Subtasks

- [x] **Task 1: Consolidate CLI Entry Points** (AC: #3, #5)
  - [x] 1.1 Audit duplication between `cli/main.py` and `cli/init_cmd.py`
  - [x] 1.2 Keep composition root in `init_cmd.py` (more modular)
  - [x] 1.3 Update `main.py` to import and use `init_command` from `init_cmd.py`
  - [x] 1.4 Remove duplicate `init_command` implementation from `main.py`
  - [x] 1.5 Ensure `__main__.py` still works correctly
  - [x] 1.6 Add `_placeholder` command to prevent Typer single-command promotion (TECH DEBT: Remove in Story 2.x when sync command is added)

- [x] **Task 2: Enhance Success Output** (AC: #1)
  - [x] 2.1 Update `init_cmd.py` success output to match exact AC format (already matches)
  - [x] 2.2 Use proper Rich formatting for "Next steps:" section (already done)
  - [x] 2.3 Add "Supported formats" line with dim styling (already done)
  - [x] 2.4 Ensure project name is quoted in success message (already done)

- [x] **Task 3: Add Step Progress Display** (AC: #2)
  - [x] 3.1 Create progress status helper in `ui/messages.py`
  - [x] 3.2 Add `status_start(message: str)` for showing spinner/bullet
  - [x] 3.3 Add `status_done(message: str)` for showing completion checkmark
  - [x] 3.4 Update `InitService.execute()` to emit progress events
  - [x] 3.5 Wire progress display in `init_cmd.py` (handled in service layer)

- [x] **Task 4: Enhance Error Output** (AC: #4)
  - [x] 4.1 Add `ModelError` handling with specific guidance
  - [x] 4.2 Add "already exists" error with actionable message
  - [x] 4.3 Add "project name required" error formatting
  - [x] 4.4 Implement What → Why → Action format for all errors

- [x] **Task 5: Test Updates** (AC: all)
  - [x] 5.1 Update `tests/cli/` for consolidated init command
  - [x] 5.2 Add CLI output tests for success message format
  - [x] 5.3 Add CLI output tests for error message formats
  - [x] 5.4 Verify integration tests still pass

---

## Dev Notes

### Current State Analysis

**Duplication Issue Identified:**
Both `cli/main.py` and `cli/init_cmd.py` define `init_command`. The `init_cmd.py` version is more complete (has composition root function `create_init_service()`), but `main.py` has inline wiring.

```python
# cli/main.py - Current (duplicate)
@app.command("init")
def init_command(...):
    # Inline composition root - DUPLICATE

# cli/init_cmd.py - Current (preferred)
def create_init_service() -> InitService:
    # Proper composition root pattern

def init_command(...):
    # Uses create_init_service()
```

**Resolution:** Keep `init_cmd.py` as the authoritative source and import into `main.py`.

### Architecture Compliance

**Layer Responsibilities:**
```
cli/__main__.py          → Entry point, calls main.py
cli/main.py              → Typer app definition, imports commands
cli/init_cmd.py          → Init command implementation + composition root
services/init_service.py → Business logic orchestration (NO CLI concerns)
ui/messages.py           → Rich console helpers for output
```

**Composition Root Pattern (Architecture doc):**
```python
# cli/init_cmd.py - SINGLE location for init dependencies
def create_init_service() -> InitService:
    filesystem = FileSystemAdapter()
    return InitService(
        filesystem=filesystem,
        manifest=ManifestAdapter(),
        agent_writer=VSCodeAgentWriter(filesystem=filesystem),
        model_downloader=DoclingModelDownloader(),
    )
```

### File Structure Changes

```
src/nest/cli/
├── __init__.py           # No changes
├── __main__.py           # No changes  
├── main.py               # UPDATE: Import init_command from init_cmd
└── init_cmd.py           # UPDATE: Enhanced output formatting

src/nest/ui/
└── messages.py           # UPDATE: Add status_start/status_done helpers
```

### Output Formatting Specifications

**Success Output (AC1):**
```python
# init_cmd.py
console = get_console()
success(f'Project "{project_name}" initialized!')
console.print()
console.print("[bold]Next steps:[/bold]")
console.print("  1. Drop your documents into raw_inbox/")
console.print("  2. Run [cyan]nest sync[/cyan] to process them")
console.print("  3. Open VS Code and use @nest in Copilot Chat")
console.print()
console.print("[dim]Supported formats: PDF, DOCX, PPTX, XLSX, HTML[/dim]")
```

**Progress Display (AC2):**
```python
# New ui/messages.py helpers
def status_start(message: str) -> None:
    """Show in-progress status with bullet."""
    _console.print(f"[blue]•[/blue] {message}...", end="")

def status_done() -> None:
    """Complete current status line with checkmark."""
    _console.print(" [green]✓[/green]")
```

**Note:** Rich's `Status` context manager could be used for actual spinners, but simple bullet + checkmark matches the acceptance criteria better and is simpler.

### Error Handling Patterns

**What → Why → Action Format:**
```python
# ModelError
error("Cannot download ML models")
console.print("  Reason: Network timeout after 3 retries")
console.print("  Action: Check your internet connection and run `nest init` again")

# Already exists
error("Nest project already exists")
console.print("  Reason: .nest_manifest.json found in this directory")
console.print("  Action: Use `nest sync` to process documents instead")

# Missing project name
error("Project name required")
console.print("  Usage: nest init 'Client Name'")
```

### Previous Story Intelligence

**From Story 1.3 (ML Model Download):**
- `DoclingModelDownloader` is already integrated into `InitService`
- Model download outputs already use `info()` and `success()` from `ui/messages.py`
- Error handling for `ModelError` already exists in `InitService.execute()`

**From Story 1.2 (Agent File Generation):**
- `VSCodeAgentWriter` is properly injected via composition root
- Agent file path is `.github/agents/nest.agent.md`

### Git Intelligence

Recent commits show consistent patterns:
- `feat(scope): description` format for commits
- `fix(review): complete story X-Y code review fixes` for review-driven changes
- Code review is done as separate step after story completion

### Testing Requirements

**CLI Output Tests:**
```python
# tests/cli/test_init_cmd.py
def test_init_success_output(capsys, tmp_path):
    """Verify success message format matches AC1."""
    # Use Typer test runner
    result = runner.invoke(app, ["init", "Nike", "--dir", str(tmp_path)])
    assert 'Project "Nike" initialized!' in result.output
    assert "Next steps:" in result.output
    assert "Supported formats:" in result.output

def test_init_already_exists_error(capsys, tmp_path):
    """Verify error message format for existing project."""
    # Create manifest first
    (tmp_path / ".nest_manifest.json").write_text("{}")
    result = runner.invoke(app, ["init", "Nike", "--dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "already exists" in result.output
```

### Project Context Reference

**Critical Rules from project-context.md:**
- NEVER use `print()` — Always use Rich helpers from `ui/messages.py`
- Error messages: What → Why → Action format
- Type hints: Modern Python 3.10+ syntax
- Imports: Absolute only (`from nest.ui.messages import ...`)
- Run `./scripts/ci-lint.sh && ./scripts/ci-typecheck.sh && ./scripts/ci-test.sh` before commit

### Dependencies

**No new dependencies required** — all components already exist:
- Rich (for console output)
- Typer (for CLI framework)
- All adapters implemented in previous stories

### Estimated Effort

Small story — primarily CLI output formatting and consolidation:
- Task 1 (Consolidate): ~15 min
- Task 2 (Success output): ~10 min
- Task 3 (Progress display): ~20 min
- Task 4 (Error output): ~15 min
- Task 5 (Tests): ~30 min

**Total: ~1.5 hours**

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5

### Debug Log References

N/A

### Completion Notes List

- **Task 1**: Consolidated CLI entry points by removing duplicate init_command from main.py and importing from init_cmd.py. Added `_placeholder` command to prevent Typer's single-command promotion (ensures `nest init Nike` works instead of `nest Nike`). Tech debt: remove _placeholder when sync command is added in Story 2.x.

- **Task 2**: Success output already matched AC1 format from previous implementation. Verified quotes around project name, Next steps section with Rich formatting, and Supported formats line with dim styling.

- **Task 3**: Added `status_start()` and `status_done()` helpers to ui/messages.py. Integrated progress display into InitService.execute() showing:
  - `• Creating project structure... ✓`
  - `• Generating agent file... ✓`
  - `• Checking ML models... cached/downloading`

- **Task 4**: Enhanced error output with What → Why → Action format:
  - ModelError: "Cannot download ML models" with network guidance
  - NestError (already exists): Shows reason and suggests `nest sync`
  - NestError (project name): Shows usage example

- **Task 5**: Added 5 CLI tests covering success output, error formats, and command registration. All 35 tests pass.

### Change Log

- 2026-01-13: Implemented Story 1.4 - Init Command CLI Integration
  - Consolidated CLI entry points (AC5)
  - Added progress display (AC2)
  - Enhanced error output with What → Why → Action format (AC4)
  - Added CLI tests (5 new tests)

### File List

- `src/nest/cli/main.py` - MODIFIED: Removed duplicate init_command, added _placeholder
- `src/nest/cli/init_cmd.py` - MODIFIED: Added ModelError handling with What → Why → Action format
- `src/nest/ui/messages.py` - MODIFIED: Added status_start() and status_done() helpers
- `src/nest/services/init_service.py` - MODIFIED: Added progress display for steps
- `tests/cli/test_init_cmd.py` - NEW: CLI command tests (5 tests)
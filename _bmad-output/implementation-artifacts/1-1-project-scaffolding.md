# Story 1.1: Project Scaffolding

Status: ready-for-dev
Branch: feat/1-1-project-scaffolding

---

## Story

**As a** user starting a new project,
**I want** to run `nest init "Project Name"` and have the basic folder structure created,
**So that** I have a properly organized workspace ready for documents.

---

## Acceptance Criteria

### AC1: Directory Creation
**Given** I am in an empty directory
**When** I run `nest init "Nike"`
**Then** the following directories are created:
- `raw_inbox/`
- `processed_context/`
- `.github/agents/`

### AC2: Manifest Creation
**Given** I run `nest init "Nike"`
**When** project scaffolding completes
**Then** a `.nest_manifest.json` file is created with:
```json
{
  "nest_version": "1.0.0",
  "project_name": "Nike",
  "last_sync": null,
  "files": {}
}
```
**And** the manifest uses the Pydantic `Manifest` model for validation

### AC3: Gitignore Update (Existing)
**Given** a `.gitignore` file exists in the directory
**When** I run `nest init "Nike"`
**Then** `raw_inbox/` is appended to `.gitignore` if not already present
**And** a comment explaining why is included

### AC4: Gitignore Creation (New)
**Given** a `.gitignore` file does NOT exist
**When** I run `nest init "Nike"`
**Then** a new `.gitignore` is created with `raw_inbox/` entry

### AC5: Missing Project Name Error
**Given** I run `nest init` without a project name
**When** the command executes
**Then** an error is displayed: "Project name required. Usage: nest init 'Project Name'"

### AC6: Existing Project Error
**Given** I run `nest init` in a directory that already has `.nest_manifest.json`
**When** the command executes
**Then** an error is displayed: "Nest project already exists. Use `nest sync` to process documents."

---

## Tasks / Subtasks

- [ ] **Task 1: Create Pydantic Manifest Model** (AC: #2)
  - [ ] 1.1 Create `src/nest/core/models.py` with `Manifest` dataclass/Pydantic model
  - [ ] 1.2 Define fields: `nest_version: str`, `project_name: str`, `last_sync: datetime | None`, `files: dict[str, FileEntry]`
  - [ ] 1.3 Add `FileEntry` model: `sha256: str`, `processed_at: datetime`, `output: str`, `status: Literal["success", "failed"]`
  - [ ] 1.4 Write unit tests for model validation

- [ ] **Task 2: Create Manifest Protocol & Adapter** (AC: #2)
  - [ ] 2.1 Define `ManifestProtocol` in `src/nest/adapters/protocols.py`
  - [ ] 2.2 Implement `ManifestAdapter` in `src/nest/adapters/manifest.py`
  - [ ] 2.3 Methods: `create(path, project_name)`, `load(path)`, `save(path, manifest)`, `exists(path)`
  - [ ] 2.4 Write tests with mock filesystem

- [ ] **Task 3: Create FileSystem Protocol & Adapter** (AC: #1, #3, #4)
  - [ ] 3.1 Define `FileSystemProtocol` in `src/nest/adapters/protocols.py`
  - [ ] 3.2 Implement `FileSystemAdapter` in `src/nest/adapters/filesystem.py`
  - [ ] 3.3 Methods: `create_directory(path)`, `write_text(path, content)`, `read_text(path)`, `exists(path)`, `append_text(path, content)`
  - [ ] 3.4 Write tests

- [ ] **Task 4: Create Init Service** (AC: #1-6)
  - [ ] 4.1 Create `src/nest/services/init_service.py`
  - [ ] 4.2 Inject: `FileSystemProtocol`, `ManifestProtocol`
  - [ ] 4.3 Implement `execute(project_name: str, target_dir: Path)` method
  - [ ] 4.4 Add validation: check existing manifest, missing project name
  - [ ] 4.5 Handle gitignore logic (create or append)
  - [ ] 4.6 Write comprehensive unit tests with mocks

- [ ] **Task 5: Create UI Message Helpers** (AC: all)
  - [ ] 5.1 Create `src/nest/ui/messages.py`
  - [ ] 5.2 Implement: `success(msg)`, `error(msg)`, `warning(msg)`, `info(msg)`
  - [ ] 5.3 Use Rich Console for colored output

- [ ] **Task 6: Create CLI Init Command** (AC: #5, #6 + success output)
  - [ ] 6.1 Create `src/nest/cli/init_cmd.py`
  - [ ] 6.2 Use Typer for argument parsing: `nest init "Project Name"`
  - [ ] 6.3 Wire dependencies in composition root pattern
  - [ ] 6.4 Display success message with next steps
  - [ ] 6.5 Handle and display errors (What → Why → Action format)

- [ ] **Task 7: Integration & E2E Testing**
  - [ ] 7.1 Create `tests/integration/test_init_flow.py`
  - [ ] 7.2 Test full init flow in temp directory
  - [ ] 7.3 Test error scenarios (existing project, missing name)

---

## Dev Notes

### Architecture Compliance

**Layer Responsibilities:**
```
cli/init_cmd.py        → Parse args, compose dependencies, call service
services/init_service.py → Orchestrate scaffolding logic
core/models.py         → Manifest Pydantic model (NO I/O)
adapters/manifest.py   → Manifest file operations
adapters/filesystem.py → Directory/file operations
adapters/protocols.py  → Protocol definitions
ui/messages.py         → Rich console output
```

**Composition Root Pattern (cli/main.py or init_cmd.py):**
```python
def create_init_service() -> InitService:
    return InitService(
        filesystem=FileSystemAdapter(),
        manifest=ManifestAdapter(),
    )
```

### File Structure to Create

```
src/nest/
├── __init__.py
├── cli/
│   ├── __init__.py
│   ├── main.py           # Typer app, entry point
│   └── init_cmd.py       # nest init command
├── services/
│   ├── __init__.py
│   └── init_service.py   # Scaffolding orchestration
├── core/
│   ├── __init__.py
│   └── models.py         # Manifest, FileEntry Pydantic models
├── adapters/
│   ├── __init__.py
│   ├── protocols.py      # FileSystemProtocol, ManifestProtocol
│   ├── filesystem.py     # FileSystemAdapter
│   └── manifest.py       # ManifestAdapter
└── ui/
    ├── __init__.py
    └── messages.py       # success(), error(), info(), warning()
```

### Code Patterns Required

**Type Hints (Modern 3.10+ syntax):**
```python
# ✓ Correct
def execute(self, project_name: str, target_dir: Path) -> None:
def create_directory(self, path: Path) -> None:

# ✗ NEVER
from typing import Optional
def execute(self, project_name: str, target_dir: str) -> None:
```

**Imports (Absolute only):**
```python
# ✓ Correct
from nest.adapters.protocols import FileSystemProtocol
from nest.core.models import Manifest

# ✗ NEVER
from ..adapters.protocols import FileSystemProtocol
```

**Path Handling:**
```python
# ✓ Correct
from pathlib import Path
output_dir = target_dir / "processed_context"
manifest_path = target_dir / ".nest_manifest.json"

# ✗ NEVER
import os
output_dir = os.path.join(target_dir, "processed_context")
```

**Console Output (Rich only):**
```python
# ✓ Correct
from nest.ui.messages import success, error
success("Project 'Nike' initialized!")
error("Nest project already exists")

# ✗ NEVER
print("Project initialized")
```

**Error Messages (What → Why → Action):**
```python
error("Cannot initialize project")
console.print("  Reason: .nest_manifest.json already exists")
console.print("  Action: Use `nest sync` to process documents")
```

### Pydantic Model Example

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel

class FileEntry(BaseModel):
    sha256: str
    processed_at: datetime
    output: str
    status: Literal["success", "failed"]
    error: str | None = None

class Manifest(BaseModel):
    nest_version: str
    project_name: str
    last_sync: datetime | None = None
    files: dict[str, FileEntry] = {}
```

### Gitignore Content

```python
GITIGNORE_COMMENT = "# Raw documents excluded from version control (processed versions in processed_context/)"
GITIGNORE_ENTRY = "raw_inbox/"

def update_gitignore(self, target_dir: Path) -> None:
    gitignore_path = target_dir / ".gitignore"
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if "raw_inbox/" not in content:
            with gitignore_path.open("a") as f:
                f.write(f"\n{GITIGNORE_COMMENT}\n{GITIGNORE_ENTRY}\n")
    else:
        gitignore_path.write_text(f"{GITIGNORE_COMMENT}\n{GITIGNORE_ENTRY}\n")
```

### Success Output Format

```
✓ Project "Nike" initialized!

Next steps:
  1. Drop your documents into raw_inbox/
  2. Run `nest sync` to process them
  3. Open VS Code and use @nest in Copilot Chat

Supported formats: PDF, DOCX, PPTX, XLSX, HTML
```

### Testing Approach

**Unit Tests (per module):**
```python
# tests/services/test_init_service.py
def test_init_creates_directories():
    mock_fs = MockFileSystem()
    mock_manifest = MockManifestAdapter()
    service = InitService(filesystem=mock_fs, manifest=mock_manifest)
    
    service.execute("Nike", Path("/tmp/project"))
    
    assert mock_fs.created_dirs == [
        Path("/tmp/project/raw_inbox"),
        Path("/tmp/project/processed_context"),
        Path("/tmp/project/.github/agents"),
    ]

def test_init_fails_when_manifest_exists():
    mock_fs = MockFileSystem()
    mock_manifest = MockManifestAdapter(exists=True)
    service = InitService(filesystem=mock_fs, manifest=mock_manifest)
    
    with pytest.raises(NestError, match="already exists"):
        service.execute("Nike", Path("/tmp/project"))
```

**Integration Tests:**
```python
# tests/integration/test_init_flow.py
def test_full_init_creates_project_structure(tmp_path):
    result = subprocess.run(
        ["nest", "init", "Nike"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 0
    assert (tmp_path / "raw_inbox").is_dir()
    assert (tmp_path / "processed_context").is_dir()
    assert (tmp_path / ".nest_manifest.json").is_file()
```

### Project Structure Notes

- This story creates the **foundational adapters and protocols** that all other stories will reuse
- `FileSystemProtocol` and `ManifestProtocol` are shared across init, sync, status, doctor
- The `Manifest` model is the core data structure for tracking processed files
- Story 1.2 (Agent File Generation) will add `AgentWriterProtocol` and `VSCodeAgentWriter`
- Story 1.3 (ML Models) will add model download logic but won't change this structure

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Layer Structure]
- [Source: _bmad-output/planning-artifacts/architecture.md#Protocol-Based DI]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.1]
- [Source: _bmad-output/project-context.md#Python Language Rules]
- [Source: _bmad-output/project-context.md#Architecture & Dependency Injection]

---

## Dev Agent Record

### Agent Model Used

_To be filled by Dev agent_

### Change Log

| Date | Change |
|------|--------|
| 2026-01-13 | Story created by SM - ready for development |

### Completion Notes List

_To be filled during development_

### File List

_To be filled during development_

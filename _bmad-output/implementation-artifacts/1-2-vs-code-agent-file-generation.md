# Story 1.2: VS Code Agent File Generation

Status: review
Branch: feat/1-2-vs-code-agent-file-generation

---

## Story

**As a** consultant,
**I want** the `@nest` agent to be automatically created during init,
**So that** I can immediately use it in VS Code Copilot Chat.

---

## Acceptance Criteria

### AC1: VS Code Agent File Creation
**Given** I run `nest init "Nike"`
**When** project scaffolding completes
**Then** `.github/agents/nest.agent.md` is created
**And** the file uses VS Code Custom Agent format with frontmatter:
```yaml
---
name: nest
description: Expert analyst for Nike project documents
icon: book
---
```
**And** the file includes instructions for:
- Reading `processed_context/00_MASTER_INDEX.md` first
- Citing sources with filenames
- Never reading `raw_inbox/` or system files
- Honest "I cannot find that" responses

### AC2: Template-Based Generation
**Given** the AgentWriter protocol is implemented
**When** VSCodeAgentWriter is instantiated
**Then** it renders the agent file from `vscode.md.jinja` template
**And** the project name is interpolated into the template

### AC3: Directory Auto-Creation
**Given** `.github/agents/` directory doesn't exist
**When** agent file generation runs
**Then** the directory is created automatically

---

## Tasks / Subtasks

- [x] **Task 1: Create AgentWriter Protocol** (AC: #2)
  - [x] 1.1 Create `src/nest/adapters/protocols.py` (update existing from story 1.1)
  - [x] 1.2 Define `AgentWriterProtocol` with method: `generate(project_name: str, output_path: Path) -> None`
  - [x] 1.3 Add docstring explaining extensibility (future: Cursor, generic formats)

- [x] **Task 2: Create VS Code Agent Template** (AC: #1, #2)
  - [x] 2.1 Create `src/nest/agents/templates/vscode.md.jinja` with Jinja2 template
  - [x] 2.2 Include YAML frontmatter: `name`, `description`, `icon`
  - [x] 2.3 Interpolate `{{ project_name }}` in description
  - [x] 2.4 Add instructions section with all required guidance from AC#1
  - [x] 2.5 Ensure template matches VS Code Custom Agent format exactly

- [x] **Task 3: Implement VSCodeAgentWriter** (AC: #2, #3)
  - [x] 3.1 Create `src/nest/agents/__init__.py`
  - [x] 3.2 Create `src/nest/agents/vscode_writer.py`
  - [x] 3.3 Implement `VSCodeAgentWriter` class implementing `AgentWriterProtocol`
  - [x] 3.4 Use Jinja2 to render template with project name
  - [x] 3.5 Accept `FileSystemProtocol` in constructor for directory creation
  - [x] 3.6 Auto-create `.github/agents/` directory if needed
  - [x] 3.7 Write rendered content to output path

- [x] **Task 4: Update InitService Integration** (AC: all)
  - [x] 4.1 Update `src/nest/services/init_service.py` constructor
  - [x] 4.2 Add `agent_writer: AgentWriterProtocol` parameter
  - [x] 4.3 Call `agent_writer.generate()` after directory creation
  - [x] 4.4 Pass project name and `.github/agents/nest.agent.md` path
  - [x] 4.5 Update existing tests to include mock agent writer

- [x] **Task 5: Update CLI Composition Root** (AC: all)
  - [x] 5.1 Update `src/nest/cli/init_cmd.py` or `main.py`
  - [x] 5.2 Wire `VSCodeAgentWriter` into `InitService` composition
  - [x] 5.3 Inject `FileSystemAdapter` into `VSCodeAgentWriter`
  - [x] 5.4 Verify init command output mentions agent file creation

- [x] **Task 6: Add Jinja2 Dependency** (AC: #2)
  - [x] 6.1 Add `jinja2` to `pyproject.toml` dependencies
  - [x] 6.2 Run `uv sync` to update lock file
  - [x] 6.3 Verify import works in VSCodeAgentWriter

- [x] **Task 7: Comprehensive Testing** (AC: all)
  - [x] 7.1 Write `tests/agents/test_vscode_writer.py` unit tests
  - [x] 7.2 Test template rendering with different project names
  - [x] 7.3 Test directory auto-creation
  - [x] 7.4 Update `tests/services/test_init_service.py` to verify agent generation
  - [x] 7.5 Update `tests/integration/test_init_flow.py` to check agent file exists
  - [x] 7.6 Verify agent file content matches VS Code format

---

## Dev Notes

### Architecture Compliance

**Layer Responsibilities:**
```
cli/init_cmd.py              → Wire VSCodeAgentWriter into InitService
services/init_service.py     → Call agent_writer.generate() during init
agents/vscode_writer.py      → Render template, write file
agents/templates/            → Jinja2 templates for different platforms
adapters/protocols.py        → AgentWriterProtocol definition
```

**Strategy Pattern for Extensibility:**
```
AgentWriterProtocol (Protocol)
├── VSCodeAgentWriter      ← V1 implementation (this story)
├── CursorAgentWriter      ← Future story
└── GenericMarkdownWriter  ← Future story
```

**Composition Root Update:**
```python
# cli/init_cmd.py or main.py
def create_init_service() -> InitService:
    filesystem = FileSystemAdapter()
    return InitService(
        filesystem=filesystem,
        manifest=ManifestAdapter(),
        agent_writer=VSCodeAgentWriter(filesystem=filesystem),
    )
```

### File Structure to Create/Modify

```
src/nest/
├── agents/
│   ├── __init__.py                    # NEW
│   ├── vscode_writer.py               # NEW
│   └── templates/
│       └── vscode.md.jinja            # NEW
├── adapters/
│   └── protocols.py                   # UPDATE: Add AgentWriterProtocol
└── services/
    └── init_service.py                # UPDATE: Add agent_writer param

tests/
└── agents/
    ├── __init__.py                    # NEW
    └── test_vscode_writer.py          # NEW
```

### VS Code Agent Template Structure

**Template Path:** `src/nest/agents/templates/vscode.md.jinja`

```markdown
---
name: nest
description: Expert analyst for {{ project_name }} project documents
icon: book
---

# @nest — Project Document Analyst

You are an expert document analyst specialized in the {{ project_name }} project. Your role is to help users understand, search, and extract insights from project documents.

## Core Responsibilities

1. **Start with the Index:** Always begin by reading `processed_context/00_MASTER_INDEX.md` to understand available documents
2. **Cite Sources:** When answering, always cite the specific filename(s) used
3. **Navigate Structure:** Documents mirror the structure in `raw_inbox/` — use this to find related files
4. **Stay Focused:** Never read `raw_inbox/` (raw documents) or system files (`.nest_manifest.json`, `.nest_errors.log`)

## Response Guidelines

- **Found Information:** Provide answer with clear citations: "According to contracts/2024/alpha.md..."
- **Not Found:** Be honest: "I cannot find information about X in the available documents. I checked: [list files]."
- **Multiple Sources:** When information spans files, cite all relevant sources
- **Clarification Needed:** Ask clarifying questions if the user's query is ambiguous

## Technical Context

- All files in `processed_context/` are Markdown conversions of original documents
- Tables from PDFs/Excel are converted to Markdown table format
- File paths are relative to `processed_context/` directory
- The index is regenerated after each `nest sync` command

## Example Interactions

**User:** "What's the project budget?"
**You:** "According to `financials/2024/budget.md`, the total project budget is $2.5M, allocated as follows: [details]. (Source: financials/2024/budget.md)"

**User:** "What does the contract say about termination?"
**You:** "I found termination clauses in `contracts/2024/alpha.md` (Section 12) and `contracts/2024/beta.md` (Section 9). Here's what each states: [details]."

**User:** "What's the deadline for Phase 2?"
**You:** "I cannot find information about Phase 2 deadlines in the available documents. I checked project plans, timelines, and contracts. Could you specify which document might contain this, or would you like me to search for related information?"

---

**Remember:** Your strength is thorough document analysis with accurate citations. Always be precise, cite sources, and honest about limitations.
```

### Code Patterns Required

**AgentWriter Protocol Definition:**
```python
# src/nest/adapters/protocols.py
from typing import Protocol
from pathlib import Path

class AgentWriterProtocol(Protocol):
    """Protocol for generating agent instruction files.
    
    Extensibility: Implementations can support different platforms
    (VS Code, Cursor, generic Markdown, etc.).
    """
    
    def generate(self, project_name: str, output_path: Path) -> None:
        """Generate agent file at specified path.
        
        Args:
            project_name: Name of the project for interpolation.
            output_path: Full path where agent file should be written.
            
        Raises:
            IOError: If file cannot be written.
        """
        ...
```

**VSCodeAgentWriter Implementation:**
```python
# src/nest/agents/vscode_writer.py
from pathlib import Path
from jinja2 import Environment, PackageLoader, select_autoescape

from nest.adapters.protocols import FileSystemProtocol, AgentWriterProtocol

class VSCodeAgentWriter:
    """Generates VS Code Custom Agent files from Jinja2 templates."""
    
    def __init__(self, filesystem: FileSystemProtocol):
        """Initialize writer with filesystem adapter.
        
        Args:
            filesystem: Filesystem adapter for directory/file operations.
        """
        self._filesystem = filesystem
        self._jinja_env = Environment(
            loader=PackageLoader("nest.agents", "templates"),
            autoescape=select_autoescape(),
        )
    
    def generate(self, project_name: str, output_path: Path) -> None:
        """Generate VS Code agent file.
        
        Args:
            project_name: Project name to interpolate into template.
            output_path: Path to write agent file (e.g., .github/agents/nest.agent.md).
            
        Raises:
            IOError: If directory cannot be created or file cannot be written.
        """
        # Ensure parent directory exists
        output_dir = output_path.parent
        if not self._filesystem.exists(output_dir):
            self._filesystem.create_directory(output_dir)
        
        # Render template
        template = self._jinja_env.get_template("vscode.md.jinja")
        content = template.render(project_name=project_name)
        
        # Write file
        self._filesystem.write_text(output_path, content)
```

**Updated InitService:**
```python
# src/nest/services/init_service.py (UPDATE)
class InitService:
    def __init__(
        self,
        filesystem: FileSystemProtocol,
        manifest: ManifestProtocol,
        agent_writer: AgentWriterProtocol,  # NEW parameter
    ):
        self._filesystem = filesystem
        self._manifest = manifest
        self._agent_writer = agent_writer
    
    def execute(self, project_name: str, target_dir: Path) -> None:
        # ... existing directory creation ...
        
        # Generate agent file (NEW)
        agent_path = target_dir / ".github" / "agents" / "nest.agent.md"
        self._agent_writer.generate(project_name, agent_path)
        
        # ... existing manifest creation ...
```

### Testing Approach

**Unit Tests (agents/test_vscode_writer.py):**
```python
def test_generate_creates_agent_file():
    mock_fs = MockFileSystem()
    writer = VSCodeAgentWriter(filesystem=mock_fs)
    
    writer.generate("Nike", Path("/project/.github/agents/nest.agent.md"))
    
    written_content = mock_fs.read_text(Path("/project/.github/agents/nest.agent.md"))
    assert "name: nest" in written_content
    assert "description: Expert analyst for Nike project documents" in written_content
    assert "icon: book" in written_content

def test_generate_creates_parent_directory():
    mock_fs = MockFileSystem()
    writer = VSCodeAgentWriter(filesystem=mock_fs)
    
    writer.generate("Nike", Path("/project/.github/agents/nest.agent.md"))
    
    assert mock_fs.directory_exists(Path("/project/.github/agents"))

def test_template_interpolates_project_name():
    mock_fs = MockFileSystem()
    writer = VSCodeAgentWriter(filesystem=mock_fs)
    
    writer.generate("Acme Corp", Path("/project/.github/agents/nest.agent.md"))
    
    content = mock_fs.read_text(Path("/project/.github/agents/nest.agent.md"))
    assert "Acme Corp" in content
```

**Integration Tests (integration/test_init_flow.py UPDATE):**
```python
def test_init_creates_agent_file(tmp_path):
    result = subprocess.run(
        ["nest", "init", "Nike"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    
    agent_path = tmp_path / ".github" / "agents" / "nest.agent.md"
    assert agent_path.exists()
    
    content = agent_path.read_text()
    assert content.startswith("---\nname: nest\n")
    assert "Nike" in content
```

### Learnings from Story 1.1

**What Worked Well:**
1. ✅ Protocol-based DI made testing easy (continue same pattern)
2. ✅ FileSystemAdapter abstraction — reuse for agent file generation
3. ✅ Pydantic models caught validation issues early
4. ✅ Comprehensive test coverage (54→55 tests) prevented regressions
5. ✅ Conftest.py with shared fixtures (MockFileSystem, MockManifest) — extend for MockAgentWriter

**Code Patterns Established (Maintain Consistency):**
- Absolute imports: `from nest.adapters.protocols import AgentWriterProtocol`
- Modern type hints: `def generate(self, project_name: str, output_path: Path) -> None:`
- Path objects: `agent_path = target_dir / ".github" / "agents" / "nest.agent.md"`
- Rich console: Import from `nest.ui.messages` (success, error, info)
- Composition root: All wiring in `cli/init_cmd.py`

**Files/Patterns to Reuse:**
- `tests/conftest.py` — Add `MockAgentWriter` factory
- `src/nest/adapters/filesystem.py` — Already has `create_directory()`, `write_text()` methods
- `src/nest/ui/messages.py` — Use for agent generation feedback
- Same test structure: unit tests per module + integration test

**Ruff/Pyright Compliance:**
- Use `Annotated[str, typer.Argument(...)]` syntax for CLI args (ruff B008)
- Break long lines >88 chars (ruff E501)
- Add explicit return types (pyright strict mode)
- No unused imports (ruff F401)

**Git Workflow:**
```bash
# Start feature branch (BEFORE any code changes)
git checkout main && git pull origin main
git checkout -b feat/1-2-vs-code-agent-file-generation

# Commit pattern (conventional commits)
git add -A
git commit -m "feat(agent): implement VSCodeAgentWriter with Jinja2 templates"
git commit -m "test(agent): add comprehensive agent writer tests"
git commit -m "feat(init): integrate agent generation into init service"
```

### Package Structure Updates

**pyproject.toml Changes:**
```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "jinja2>=3.1.0",  # NEW: Template engine for agent files
]

[project.entry-points."nest.agents"]
# Future: Plugin system for custom agent writers
```

**Package Data (include templates):**
```toml
[tool.hatch.build.targets.wheel]
packages = ["src/nest"]
include = [
    "src/nest/agents/templates/**/*.jinja",  # Include Jinja templates
]
```

### Success Indicators

After running `nest init "Nike"`:
1. ✅ Agent file exists at `.github/agents/nest.agent.md`
2. ✅ File starts with valid YAML frontmatter
3. ✅ "Nike" appears in description and throughout instructions
4. ✅ All required instructions present (index, citations, boundaries, honesty)
5. ✅ File is valid Markdown and can be loaded by VS Code Copilot
6. ✅ Tests pass: `pytest tests/agents/ tests/services/ tests/integration/`
7. ✅ Ruff and pyright clean: `./scripts/ci-lint.sh && ./scripts/ci-typecheck.sh`

### Anti-Patterns to Avoid

**❌ DON'T hardcode agent content in Python:**
```python
# ✗ WRONG — No flexibility
content = f"---\nname: nest\ndescription: {project_name}\n---\n..."
```

**✅ DO use Jinja2 template:**
```python
# ✓ CORRECT — Template-based, extensible
template = jinja_env.get_template("vscode.md.jinja")
content = template.render(project_name=project_name)
```

**❌ DON'T tightly couple to VS Code format:**
```python
# ✗ WRONG — Hard to add Cursor support later
class AgentFileGenerator:
    def generate_vscode(self, ...):  # Only VS Code
```

**✅ DO use protocol + strategy pattern:**
```python
# ✓ CORRECT — Easy to add new platforms
class AgentWriterProtocol(Protocol):
    def generate(self, ...): ...

class VSCodeAgentWriter: ...      # Strategy 1
class CursorAgentWriter: ...      # Strategy 2 (future)
```

**❌ DON'T skip directory creation check:**
```python
# ✗ WRONG — Will fail if .github/agents/ doesn't exist
output_path.write_text(content)
```

**✅ DO ensure directory exists first:**
```python
# ✓ CORRECT — Robust
if not self._filesystem.exists(output_dir):
    self._filesystem.create_directory(output_dir)
self._filesystem.write_text(output_path, content)
```

### Project Structure Notes

- This story adds **agent generation capability** to the init flow
- **AgentWriterProtocol** enables future platform support (Cursor, generic Markdown)
- **Jinja2 templates** keep agent instructions maintainable and versionable
- **FileSystemAdapter** is reused (no new adapter needed)
- Story 1.3 (ML Models) will add model download logic but won't touch agent generation
- Story 1.4 (CLI Integration) will add final polish to init command output

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.2]
- [Source: _bmad-output/planning-artifacts/architecture.md#Extensibility: Multi-Platform Agent Support]
- [Source: _bmad-output/planning-artifacts/architecture.md#Agent Generation]
- [Source: _bmad-output/project-context.md#Architecture & Dependency Injection]
- [Source: _bmad-output/implementation-artifacts/1-1-project-scaffolding.md#Dev Notes]

---

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (via GitHub Copilot)

### Debug Log References

No critical issues encountered. Implementation followed red-green-refactor cycle with all tests passing.

### Completion Notes List

- ✅ Created AgentWriterProtocol in adapters/protocols.py with extensibility for future platforms
- ✅ Implemented VSCodeAgentWriter using Jinja2 template engine for flexible agent file generation
- ✅ Created vscode.md.jinja template with proper VS Code Custom Agent format (YAML frontmatter + instructions)
- ✅ Updated InitService to accept and call agent_writer during project initialization
- ✅ Wired VSCodeAgentWriter into CLI composition root in main.py
- ✅ Added jinja2>=3.1.0 dependency and configured package to include template files
- ✅ Created comprehensive unit tests (4 tests) and integration tests (3 tests) - all passing
- ✅ Agent file correctly interpolates project name throughout template
- ✅ Directory auto-creation works correctly (.github/agents/ created if missing)
- ✅ All acceptance criteria validated and met
- ✅ Ruff linting and Pyright type checking pass with zero errors
- ✅ Created missing core modules (models.py, exceptions.py) and __init__.py files
- ✅ Retrieved and integrated filesystem/manifest adapters from story 1.1
- ✅ Created README.md for package distribution

### File List

**New Files:**
- src/nest/__init__.py
- src/nest/core/__init__.py
- src/nest/core/models.py
- src/nest/core/exceptions.py
- src/nest/agents/__init__.py
- src/nest/agents/vscode_writer.py
- src/nest/agents/templates/vscode.md.jinja
- src/nest/cli/__init__.py
- src/nest/cli/main.py
- src/nest/cli/__main__.py
- src/nest/ui/__init__.py
- src/nest/ui/messages.py
- src/nest/services/__init__.py
- src/nest/adapters/__init__.py
- src/nest/adapters/filesystem.py
- src/nest/adapters/manifest.py
- tests/agents/__init__.py
- tests/agents/test_vscode_writer.py
- tests/integration/__init__.py
- tests/integration/test_init_flow.py
- README.md

**Modified Files:**
- src/nest/adapters/protocols.py (added AgentWriterProtocol)
- src/nest/services/init_service.py (added agent_writer parameter and call)
- pyproject.toml (added jinja2 dependency and template file inclusion)
- _bmad-output/implementation-artifacts/sprint-status.yaml (marked story in-progress)

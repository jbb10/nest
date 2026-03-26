# Story 10.1: Multi-Agent Template Bundle

Status: review

## Story

As a **developer maintaining the Nest agent system**,
I want **the single agent template replaced with a coordinator + three specialized subagent templates**,
So that **generated agent files use the new multi-agent architecture with dedicated researcher, synthesizer, and planner subagents**.

## Acceptance Criteria

### AC1: Four Jinja Templates Exist

**Given** the `src/nest/agents/templates/` directory
**When** the template bundle is complete
**Then** it contains four files:
- `coordinator.md.jinja` (replaces `vscode.md.jinja`)
- `researcher.md.jinja`
- `synthesizer.md.jinja`
- `planner.md.jinja`
**And** the old `vscode.md.jinja` is removed

### AC2: Coordinator Template References Subagents

**Given** the `coordinator.md.jinja` template
**When** rendered
**Then** its YAML frontmatter includes:
```yaml
agents: ['nest-master-researcher', 'nest-master-synthesizer', 'nest-master-planner']
```
**And** it references `.nest/00_MASTER_INDEX.md` for the index
**And** it references `.nest/glossary.md` for terminology
**And** all document reading rules reference `_nest_context/` for content

### AC3: Subagent Templates Have Correct Frontmatter

**Given** the three subagent templates
**When** rendered
**Then** each has `user-invokable: false` in frontmatter
**And** each has a unique `name` matching the coordinator's `agents:` list
**And** none reference `_nest_sources/` or `.nest/` system files (except `.nest/00_MASTER_INDEX.md` and `.nest/glossary.md`)

### AC4: VSCodeAgentWriter Supports Multi-File Rendering

**Given** the updated `VSCodeAgentWriter`
**When** `render_all()` is called
**Then** it returns a dictionary mapping filenames to rendered content:
```python
{
    "nest.agent.md": "...",
    "nest-master-researcher.agent.md": "...",
    "nest-master-synthesizer.agent.md": "...",
    "nest-master-planner.agent.md": "...",
}
```

### AC5: VSCodeAgentWriter Supports Multi-File Generation

**Given** the updated `VSCodeAgentWriter`
**When** `generate_all(output_dir: Path)` is called
**Then** all four agent files are written to `output_dir`
**And** the directory is created if it does not exist

### AC6: Backward-Compatible render() and generate()

**Given** the existing `render()` and `generate()` methods
**When** called
**Then** `render()` returns the coordinator template content (backward compatible)
**And** `generate()` writes the coordinator file (backward compatible)
**And** no existing callers break

### AC7: Agent File Constants Updated

**Given** a constants module or the agent migration service
**When** agent file paths are referenced
**Then** an `AGENT_FILES` list (or similar) contains all four filenames:
```python
AGENT_FILES = [
    "nest.agent.md",
    "nest-master-researcher.agent.md",
    "nest-master-synthesizer.agent.md",
    "nest-master-planner.agent.md",
]
```

### AC8: AgentWriterProtocol Updated

**Given** `AgentWriterProtocol` in `adapters/protocols.py`
**When** the protocol is updated
**Then** it includes `render_all() -> dict[str, str]` and `generate_all(output_dir: Path) -> None`
**And** the existing `render()` and `generate()` signatures remain

### AC9: NEW_AGENTS Source Folder Removed

**Given** all four Jinja templates have been created and tests pass
**When** the story is complete
**Then** the `NEW_AGENTS/` directory and its contents are deleted from the repository
**And** the templates in `src/nest/agents/templates/` are the single source of truth

## Tasks / Subtasks

- [x] **Task 1: Create Four Agent Templates** (AC: #1, #2, #3)
  - [x] 1.1 Create `src/nest/agents/templates/coordinator.md.jinja` from `NEW_AGENTS/nest-master-coordinator.agent.md`
  - [x] 1.2 Create `src/nest/agents/templates/researcher.md.jinja` from `NEW_AGENTS/nest-master-researcher.agent.md`
  - [x] 1.3 Create `src/nest/agents/templates/synthesizer.md.jinja` from `NEW_AGENTS/nest-master-synthesizer.agent.md`
  - [x] 1.4 Create `src/nest/agents/templates/planner.md.jinja` from `NEW_AGENTS/nest-master-planner.agent.md`
  - [x] 1.5 Remove `src/nest/agents/templates/vscode.md.jinja`
  - [x] 1.6 Verify all templates reference `.nest/00_MASTER_INDEX.md` (not `_nest_context/`)
  - [x] 1.7 Verify all templates reference `.nest/glossary.md`
  - [x] 1.8 Verify subagent templates have `user-invokable: false`

- [x] **Task 2: Add Agent File Constants** (AC: #7)
  - [x] 2.1 Add `AGENT_FILES` list to `src/nest/core/paths.py` (where other path constants live)
  - [x] 2.2 Add `TEMPLATE_TO_AGENT_FILE` dict mapping template names to output filenames
  - [x] 2.3 Add `AGENT_DIR = Path(".github") / "agents"` constant

- [x] **Task 3: Update AgentWriterProtocol** (AC: #8)
  - [x] 3.1 Add `render_all() -> dict[str, str]` to protocol
  - [x] 3.2 Add `generate_all(output_dir: Path) -> None` to protocol
  - [x] 3.3 Keep existing `render()` and `generate()` signatures

- [x] **Task 4: Update VSCodeAgentWriter** (AC: #4, #5, #6)
  - [x] 4.1 Implement `render_all()` using `TEMPLATE_TO_AGENT_FILE` mapping, renders all 4 templates, returns filename-to-content dict
  - [x] 4.2 Implement `generate_all()` -- writes all 4 files to output directory, creates dir if missing
  - [x] 4.3 Update `render()` to load `coordinator.md.jinja` instead of `vscode.md.jinja` (backward compat)
  - [x] 4.4 Update `generate()` -- no change needed, already delegates to `render()`
  - [x] 4.5 Update Jinja `PackageLoader` -- no change needed, still loads from `nest.agents` / `templates`

- [x] **Task 5: Write Unit Tests** (AC: all)
  - [x] 5.1 Update `tests/agents/test_vscode_writer.py`
  - [x] 5.2 Test `render_all()` returns dict with 4 entries keyed by agent filenames
  - [x] 5.3 Test each rendered template contains correct frontmatter (`name`, `agents`, `user-invokable`)
  - [x] 5.4 Test `generate_all()` writes 4 files to directory
  - [x] 5.5 Test `render()` backward compat returns coordinator content
  - [x] 5.6 Test `generate()` backward compat writes coordinator file
  - [x] 5.7 Test directory auto-creation in `generate_all()`
  - [x] 5.8 Test coordinator template contains `agents:` frontmatter field
  - [x] 5.9 Test subagent templates contain `user-invokable: false`

- [x] **Task 6: Remove NEW_AGENTS Source Folder** (AC: #9)
  - [x] 6.1 Delete `NEW_AGENTS/` directory and all contents from the repository
  - [x] 6.2 Verify no references to `NEW_AGENTS/` remain in the codebase

- [x] **Task 7: Run CI Validation**
  - [x] 7.1 Lint passes (`ruff check`)
  - [x] 7.2 Typecheck passes (`pyright`)
  - [x] 7.3 All existing tests pass (no regressions)

## Dev Notes

### Template Content Source

The four agent files in `NEW_AGENTS/` are the validated source for the Jinja templates. Copy their **exact content** verbatim into the `.jinja` files. Since `project_name` was removed in Story 8.1, the templates are currently static markdown with no Jinja interpolation variables. Keeping them as `.jinja` files allows future variable injection without code changes.

**Source -> Destination mapping:**
| Source File | Template File | Output Filename |
|-------------|--------------|-----------------|
| `NEW_AGENTS/nest-master-coordinator.agent.md` | `src/nest/agents/templates/coordinator.md.jinja` | `nest.agent.md` |
| `NEW_AGENTS/nest-master-researcher.agent.md` | `src/nest/agents/templates/researcher.md.jinja` | `nest-master-researcher.agent.md` |
| `NEW_AGENTS/nest-master-synthesizer.agent.md` | `src/nest/agents/templates/synthesizer.md.jinja` | `nest-master-synthesizer.agent.md` |
| `NEW_AGENTS/nest-master-planner.agent.md` | `src/nest/agents/templates/planner.md.jinja` | `nest-master-planner.agent.md` |

**CRITICAL: The coordinator template output filename is `nest.agent.md` (NOT `nest-master-coordinator.agent.md`).** This is required because:
1. The coordinator frontmatter uses `name: nest-master-coordinator` but VS Code uses the filename for user invocation
2. The existing `init_service.py` and `doctor_service.py` generate to `nest.agent.md`
3. Backward compatibility requires the coordinator to land at the same path

### Backward Compatibility Strategy

**Callers of `render()` and `generate()` (must NOT break):**

| Caller | File | How it uses the writer |
|--------|------|----------------------|
| `InitService.execute()` | `src/nest/services/init_service.py:107` | `self._agent_writer.generate(agent_path)` where `agent_path = .github/agents/nest.agent.md` |
| `DoctorService._remediate_agent_file()` | `src/nest/services/doctor_service.py:605` | `self._agent_writer.generate(output_path)` where `output_path = .github/agents/nest.agent.md` |
| `AgentMigrationService.check_migration_needed()` | `src/nest/services/agent_migration_service.py:82` | `rendered = self._agent_writer.render()` -- compares against local `nest.agent.md` |
| `AgentMigrationService.execute_migration()` | `src/nest/services/agent_migration_service.py:137` | `self._agent_writer.generate(agent_path)` |

**Strategy:** `render()` returns coordinator content. `generate()` writes coordinator file. These callers will be updated to use `render_all()`/`generate_all()` in Stories 10.2 and 10.3.

### Constants Location

Add constants to `src/nest/core/paths.py` where all other path/filename constants live (e.g., `SOURCES_DIR`, `CONTEXT_DIR`, `NEST_META_DIR`). This avoids creating a new file.

```python
# Agent file constants (Epic 10: Multi-Agent Architecture)
AGENT_DIR = Path(".github") / "agents"
AGENT_FILES = [
    "nest.agent.md",
    "nest-master-researcher.agent.md",
    "nest-master-synthesizer.agent.md",
    "nest-master-planner.agent.md",
]
TEMPLATE_TO_AGENT_FILE = {
    "coordinator.md.jinja": "nest.agent.md",
    "researcher.md.jinja": "nest-master-researcher.agent.md",
    "synthesizer.md.jinja": "nest-master-synthesizer.agent.md",
    "planner.md.jinja": "nest-master-planner.agent.md",
}
```

### VSCodeAgentWriter Implementation Guidance

**`render_all()` implementation:**
```python
def render_all(self) -> dict[str, str]:
    result: dict[str, str] = {}
    for template_name, agent_filename in TEMPLATE_TO_AGENT_FILE.items():
        template = self._jinja_env.get_template(template_name)
        result[agent_filename] = template.render()
    return result
```

**`generate_all()` implementation:**
```python
def generate_all(self, output_dir: Path) -> None:
    if not self._filesystem.exists(output_dir):
        self._filesystem.create_directory(output_dir)
    for filename, content in self.render_all().items():
        self._filesystem.write_text(output_dir / filename, content)
```

**`render()` update -- just change the template name:**
```python
def render(self) -> str:
    template = self._jinja_env.get_template("coordinator.md.jinja")  # was "vscode.md.jinja"
    return template.render()
```

### AgentWriterProtocol Update

Add two new methods while keeping existing signatures:
```python
class AgentWriterProtocol(Protocol):
    def render(self) -> str: ...          # existing
    def generate(self, output_path: Path) -> None: ...  # existing
    def render_all(self) -> dict[str, str]: ...         # new
    def generate_all(self, output_dir: Path) -> None: ...  # new
```

### Template Path Reference Verification

All four templates must follow these rules:
- **Reference `.nest/00_MASTER_INDEX.md`** for the document index
- **Reference `.nest/glossary.md`** for terminology
- **Reference `_nest_context/`** for document content reading
- **Do NOT reference `_nest_sources/`** for reading (only coordinator mentions it in the "Technical Context" section to explain what it is)
- Subagents must NOT reference other `.nest/` system files (manifest, errors.log, hints files)

The `NEW_AGENTS/` source files have already been validated for correct path references. Copy verbatim.

### Coordinator Frontmatter: name Field

The coordinator template uses `name: nest-master-coordinator` in frontmatter. This is the internal agent name for VS Code's subagent dispatch. The output **filename** `nest.agent.md` is what VS Code shows to users. These are intentionally different.

### Existing Tests to Update

The existing tests in `tests/agents/test_vscode_writer.py` assert on `vscode.md.jinja` output (e.g., `name: nest`, `description: Expert analyst`). These must be updated:
- `test_render_contains_static_description` -- update expected description to match coordinator template
- `test_generate_creates_agent_file` -- update expected frontmatter fields
- `test_generate_includes_required_instructions` -- update expected content strings
- `test_generate_body_uses_folder_agnostic_text` -- update or replace this assertion

### azure-mcp/search Tool Reference

The coordinator and researcher agents reference `azure-mcp/search` in their tools list. This is an optional MCP tool that may not be available to all users. VS Code gracefully ignores unavailable tools, so this is safe to include.

### Project Structure Notes

All changes are within existing module boundaries:
- `src/nest/core/paths.py` -- add constants (existing file)
- `src/nest/adapters/protocols.py` -- extend protocol (existing file)
- `src/nest/agents/vscode_writer.py` -- extend class (existing file)
- `src/nest/agents/templates/` -- replace template files (existing directory)
- `tests/agents/test_vscode_writer.py` -- extend/update tests (existing file)
- `NEW_AGENTS/` -- delete after templates created

No new modules, no new directories, no new dependencies.

### References

- [Source: architecture.md] -- AgentWriter protocol, VSCodeAgentWriter, Jinja templates, file purpose index
- [Source: project-context.md] -- Protocol-based DI, testing rules, naming conventions
- [Source: epics.md#Epic 10] -- FR41-FR43, multi-agent scope and dependencies
- `src/nest/agents/vscode_writer.py` -- current single-file writer implementation
- `src/nest/agents/templates/vscode.md.jinja` -- current single template (to be replaced)
- `src/nest/adapters/protocols.py:228-253` -- current AgentWriterProtocol definition
- `src/nest/services/init_service.py:107` -- InitService.execute() calls generate()
- `src/nest/services/doctor_service.py:605` -- DoctorService._remediate_agent_file() calls generate()
- `src/nest/services/agent_migration_service.py:82,137` -- AgentMigrationService calls render() and generate()
- `NEW_AGENTS/nest-master-coordinator.agent.md` -- validated coordinator content
- `NEW_AGENTS/nest-master-researcher.agent.md` -- validated researcher content
- `NEW_AGENTS/nest-master-synthesizer.agent.md` -- validated synthesizer content
- `NEW_AGENTS/nest-master-planner.agent.md` -- validated planner content

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
None

### Completion Notes List
- All four Jinja templates created verbatim from `NEW_AGENTS/` source files
- `vscode.md.jinja` removed via `git rm`
- `AGENT_DIR`, `AGENT_FILES`, `TEMPLATE_TO_AGENT_FILE` constants added to `src/nest/core/paths.py`
- `AgentWriterProtocol` extended with `render_all()` and `generate_all()` (existing signatures preserved)
- `VSCodeAgentWriter` updated: `render()` loads `coordinator.md.jinja`, new `render_all()`/`generate_all()` methods added
- `MockAgentWriter` in `conftest.py` updated to implement new protocol methods
- 30 unit tests written covering all 9 ACs
- Integration test `test_init_creates_agent_file` updated for new coordinator frontmatter
- `NEW_AGENTS/` directory deleted (was untracked)
- No references to `NEW_AGENTS/` remain in source code
- 905 tests pass, 0 failures. Lint clean. Typecheck clean.

### File List
- `src/nest/agents/templates/coordinator.md.jinja` (created)
- `src/nest/agents/templates/researcher.md.jinja` (created)
- `src/nest/agents/templates/synthesizer.md.jinja` (created)
- `src/nest/agents/templates/planner.md.jinja` (created)
- `src/nest/agents/templates/vscode.md.jinja` (deleted)
- `src/nest/core/paths.py` (modified - added AGENT_DIR, AGENT_FILES, TEMPLATE_TO_AGENT_FILE)
- `src/nest/adapters/protocols.py` (modified - added render_all, generate_all to AgentWriterProtocol)
- `src/nest/agents/vscode_writer.py` (modified - added render_all, generate_all, updated render to use coordinator template)
- `tests/agents/test_vscode_writer.py` (modified - 30 tests covering all ACs)
- `tests/conftest.py` (modified - MockAgentWriter updated with render_all, generate_all)
- `tests/integration/test_init_flow.py` (modified - updated assertion for new coordinator frontmatter)
- `NEW_AGENTS/` (deleted - 4 files)

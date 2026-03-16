---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7]
inputDocuments:
  - prd.md
workflowType: 'architecture'
project_name: 'nest'
user_name: 'Jóhann'
date: '2026-01-11'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
Nest is structured around 5 CLI commands, each with distinct responsibilities:

1. **`nest init`** — Project scaffolding + first-run model download
2. **`nest sync`** — Incremental document processing with checksum tracking
3. **`nest update`** — Self-update + agent template migration (renamed from `upgrade`)
4. **`nest status`** — At-a-glance project state reporting
5. **`nest doctor`** — Environment and dependency validation

The core processing loop (sync) handles: file discovery → checksum comparison → Docling conversion → directory mirroring → orphan cleanup → index regeneration → manifest update.

**Non-Functional Requirements:**
- **Privacy:** All processing local (Docling, no cloud APIs)
- **Performance:** Incremental sync via SHA-256 checksums; skip unchanged files
- **Reliability:** Error logging to `.nest/errors.log`, configurable fail modes
- **Portability:** Cross-platform (macOS/Linux/Windows via Python 3.10+)
- **Maintainability:** DRY principle enforced — shared components across commands

**Scale & Complexity:**

- Primary domain: Python CLI tool
- Complexity level: Medium
- Estimated architectural components: 8-10 modules

### Technical Constraints & Dependencies

| Constraint | Impact |
|------------|--------|
| **`uv` required** | Users must pre-install uv; Nest won't bundle it |
| **Docling ML models** | ~1.5-2GB first-run download; cached at `~/.cache/docling/` |
| **VS Code agent format** | Must match exact frontmatter + instruction format |
| **Python 3.10+** | Minimum version for Docling compatibility |
| **Typer + Rich** | CLI framework choice locked in PRD |

### Cross-Cutting Concerns Identified

1. **Error Handling** — Consistent pattern across all commands (skip vs fail modes)
2. **Logging** — Unified error log format for `.nest/errors.log`
3. **Path Normalization** — Cross-platform path handling (Windows backslashes)
4. **Checksum Computation** — Reused by sync, status, doctor
5. **Progress Reporting** — Rich terminal output for long operations
6. **Model Management** — Download, cache verification, version checking
7. **Line Ending Normalization** — All Nest-generated text files use LF (`\n`) everywhere; `.gitattributes` enforces `eol=lf` for committed text files to prevent cross-platform checksum drift

### Architectural Drivers (User-Specified)

#### Extensibility: Multi-Platform Agent Support

Even though V1 targets VS Code Copilot only, the architecture must accommodate future agent instruction formats:

- **Design for abstraction:** Agent generation should be behind an interface/protocol
- **Strategy pattern:** Different "agent writers" for different platforms (VS Code, Cursor, generic, etc.)
- **Configuration-driven:** Agent format selection via config or flag in future versions
- **Template isolation:** Agent templates stored separately, not hard-coded

```
AgentWriter (Protocol)
├── VSCodeAgentWriter      # V1 implementation
├── CursorAgentWriter      # Future
├── GenericMarkdownWriter  # Future
└── ...
```

#### Testability: Dependency Injection & Seams

Code must be structured for easy testing and verification:

- **Dependency injection:** All external dependencies (filesystem, Docling, network) injected, not imported directly
- **Protocols/Interfaces:** Define contracts for all major components
- **Pure functions where possible:** Separate logic from I/O
- **Test seams:** Easy to mock filesystem, document processor, network calls
- **No global state:** Configuration passed explicitly, not via module globals

Example pattern:
```python
class SyncService:
    def __init__(
        self,
        filesystem: FileSystemProtocol,
        processor: DocumentProcessorProtocol,
        manifest: ManifestProtocol,
    ):
        ...
```

#### UX: Rich, To-the-Point Guidance

CLI experience should follow established tool patterns (git, npm, cargo):

- **`nest init`:** Explain what will be created, where to put files, what happens next
- **`nest sync`:** Show progress, summarize results, suggest next action
- **Contextual help:** Commands show relevant guidance based on current state
- **Error messages:** Actionable, not cryptic (say what to do, not just what failed)
- **Quiet mode:** `--quiet` flag for scripting, verbose by default for humans

Example guidance after `nest init`:
```
✓ Project "Nike" initialized!

Next steps:
  1. Drop your documents into _nest_sources/
  2. Run `nest sync` to process them
  3. Open VS Code and use @nest in Copilot Chat

Supported formats: PDF, DOCX, PPTX, XLSX, HTML
```

## Starter Template Evaluation

### Primary Technology Domain

Python CLI tool — technology stack defined by PRD constraints.

### Starter Options Considered

Given the specific technology stack (Typer + Rich + Docling + uv), general Python starters add little value. The project will use a **custom project structure** following Python packaging best practices.

### Selected Approach: Custom Project Structure

**Rationale:**
- PRD already specifies core dependencies (Typer, Rich, Docling)
- No opinionated starter matches this exact combination
- Clean structure allows precise control over dependency injection patterns
- Avoids inheriting unnecessary complexity from general-purpose starters

### Project Tooling Decisions

| Tool | Choice | Rationale |
|------|--------|-----------|
| **Package Manager** | uv | PRD requirement; also used for development |
| **Project Layout** | src layout (`src/nest/`) | Python packaging best practice for distributed tools |
| **Testing** | pytest | Python standard, excellent plugin ecosystem |
| **Type Checking** | Pyright (strict) | Matches VSCode/Pylance, fast, strict by default |
| **Linting/Formatting** | Ruff | Modern, fast (Rust-based), replaces flake8+black+isort |
| **CI Platform** | GitHub Actions | Matches GitHub distribution |

### Branching Strategy: Trunk-Based with Release Tags

```
main ─────●─────●─────●─────●─────●─────●─────●───→
          │           │                 │
          v1.0.0      v1.1.0            v1.2.0 ← latest
```

| Principle | Rule |
|-----------|------|
| **main = trunk** | All work merges here |
| **main may be ahead** | Commits between tags are "next version" work |
| **Tags = releases** | Only tagged commits are official releases |
| **`latest` tag** | Always points to most recent release (moved by release script) |
| **No release branches** | Single-version tool; no parallel version maintenance |
| **Feature branches** | Short-lived: `feature/*`, `fix/*`, `chore/*` |

### Conventional Commits (MANDATORY FOR AI DEVELOPERS)

All commits MUST follow conventional commit format. AI agents working on this codebase must validate their commits against this specification before pushing.

**Format:**
```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types and Semver Impact:**

| Type | When to Use | Semver Impact |
|------|-------------|---------------|
| `feat` | New user-facing feature | MINOR bump (0.x.0) |
| `fix` | Bug fix | PATCH bump (0.0.x) |
| `docs` | Documentation changes only | No version bump |
| `chore` | Maintenance, dependencies, CI | No version bump |
| `refactor` | Code restructure, no behavior change | No version bump |
| `test` | Adding or modifying tests | No version bump |
| `perf` | Performance improvement | PATCH bump |
| `!` or `BREAKING CHANGE` | Breaking change | MAJOR bump (x.0.0) |

**Examples:**
```
feat(sync): add --dry-run flag for preview mode
fix(init): handle spaces in project names correctly
chore(deps): bump docling to 2.1.0
feat(agent)!: change agent file format

BREAKING CHANGE: Agent files now use .agent.md extension
```

**AI Developer Rules:**
1. Every commit message MUST match this format
2. Scope should match module name (sync, init, doctor, agent, manifest, etc.)
3. Description must be imperative mood ("add" not "added")
4. Breaking changes require `!` after type OR `BREAKING CHANGE` footer
5. Run `./scripts/ci-lint.sh` before committing

### Testing Strategy

**Test Layers:**

| Layer | Purpose | Location | Execution |
|-------|---------|----------|-----------|
| Unit | Pure functions, isolated logic | `tests/core/`, `tests/adapters/` | `pytest -m "not e2e"` |
| Integration | Service orchestration with mocks | `tests/services/`, `tests/integration/` | `pytest -m "not e2e"` |
| **E2E** | Full CLI, real file I/O, real Docling | `tests/e2e/` | `pytest -m "e2e" --timeout=60` |

**E2E Test Infrastructure:**

```
tests/e2e/
├── conftest.py                # CLI runner, temp_project fixtures
├── test_init_e2e.py           # Full init command flow
├── test_sync_e2e.py           # Full sync command flow
├── test_negative_e2e.py       # Error handling tests
└── fixtures/                  # Real test documents (binary)
    ├── quarterly.pdf
    ├── summary.docx
    ├── deck.pptx
    └── data.xlsx
```

**E2E Skip Condition:**
```python
def docling_available() -> bool:
    """Check if Docling models are downloaded."""
    cache_dir = Path.home() / ".cache" / "docling"
    return cache_dir.exists() and any(cache_dir.iterdir())

skip_without_docling = pytest.mark.skipif(
    not docling_available(),
    reason="Docling models not downloaded"
)
```

**Binary Fixture Handling (`.gitattributes`):**
```gitattributes
# E2E test fixtures
tests/e2e/fixtures/*.pdf binary
tests/e2e/fixtures/*.docx binary
tests/e2e/fixtures/*.pptx binary
tests/e2e/fixtures/*.xlsx binary

# Nest project files — see "Line Ending Normalization Standard" section
# for the full .gitattributes generated by nest init
```

**E2E Fixture Scope:**
- `temp_project` fixture uses `scope="class"` to share init overhead within test classes
- `cli_runner` fixture uses `scope="function"` (stateless, fast)

**Story Completion Requirement:**
A story is NOT complete until all applicable E2E tests pass. When creating stories, the Scrum Master MUST evaluate if new E2E tests are needed and add them to acceptance criteria.

---

### CI Strategy

**Makefile-Based Architecture:**
All CI logic is defined in a project-root `Makefile` — the single source of truth for linting, formatting, type checking, and testing. Both developers and GitHub Actions invoke the same `make` targets.

```
Makefile          # Single source of truth for all repo operations
scripts/
└── release.sh    # Release automation with human approval gate
```

**Makefile Targets:**

| Target | Command | Purpose |
|--------|---------|---------|
| `make lint` | `uv run ruff check .` | Lint with ruff |
| `make format-check` | `uv run ruff format --check .` | Verify formatting |
| `make format` | `uv run ruff format .` | Auto-format code |
| `make typecheck` | `uv run pyright` | Strict type checking |
| `make test` | `uv run pytest tests/ -v --ignore=tests/e2e` | Unit + integration tests |
| `make test-e2e` | `uv run pytest -m "e2e" --timeout=60` | E2E tests (require Docling) |
| `make test-all` | `make test` + `make test-e2e` | All tests |
| `make ci` | lint + format-check + typecheck + test-all | Full pre-release suite |
| `make release` | `./scripts/release.sh` | Run release process |

**GitHub Actions (`.github/workflows/ci.yml`):**

```yaml
name: CI

on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: make lint && make format-check

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: make typecheck

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - uses: astral-sh/setup-uv@v5
      - run: make test

  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: make test-e2e
```

**Local Execution:**
```bash
# Quick validation (current Python)
make ci

# Individual checks
make lint
make typecheck
make test
```

### CD Strategy: Local Release with Human Gate

**Releases are executed from developer terminal, NOT from GitHub Actions pipeline.**

**Tools:** `git-cliff` for changelog generation, `perl` for cross-platform in-place file editing, `make ci` for validation.

**`scripts/release.sh` Workflow:**

```
┌─────────────────────────────────────────────────────┐
│  1. PRE-FLIGHT CHECKS                               │
│     • Verify on main branch                         │
│     • Verify working directory clean                │
│     • Pull latest from origin (--ff-only)          │
│     • Verify tools: uv, git, git-cliff, perl      │
├─────────────────────────────────────────────────────┤
│  2. VERSION DETERMINATION                           │
│     • Read current version from pyproject.toml     │
│     • Analyze commits since last tag               │
│     • Suggest version bump (patch/minor/major)     │
│     • Allow --patch/--minor/--major override       │
├─────────────────────────────────────────────────────┤
│  3. CHANGELOG GENERATION                            │
│     • Run git-cliff to parse conventional commits  │
│     • Generate formatted release notes             │
│     • Display preview in terminal                  │
├─────────────────────────────────────────────────────┤
│  4. ⏸️  HUMAN APPROVAL GATE                         │
│     • Display: version bump (old → new)            │
│     • Display: changelog preview                   │
│     • Display: files that will be modified         │
│     • Prompt: "Proceed with release? [y/N]"       │
│     • STOP here if not approved                    │
├─────────────────────────────────────────────────────┤
│  5. UPDATE FILES                                    │
│     • Update version in pyproject.toml (perl)     │
│     • Update version in src/nest/__init__.py (perl)│
│     • Generate CHANGELOG.md via git-cliff          │
├─────────────────────────────────────────────────────┤
│  6. CI VALIDATION                                   │
│     • Run make ci (full suite)                     │
│     • On failure: rollback file changes, abort     │
├─────────────────────────────────────────────────────┤
│  7. COMMIT, TAG & PUSH (after CI passes)           │
│     • Commit: "chore(release): v{version}"        │
│     • Create annotated tag: v{version}            │
│     • Move 'latest' tag to new release             │
│     • ⏸️ Second confirmation before push            │
│     • Push branch + tags to origin                 │
│     • Display: success message with install cmd   │
└─────────────────────────────────────────────────────┘
```

**Critical:** The `latest` tag is ALWAYS moved to point to the newest release. This ensures `uv tool install ...@latest` gets the most recent stable version.

**Cross-Platform:** Uses `perl -pi -e` for in-place file edits (works identically on macOS and Linux, unlike `sed -i` which differs between BSD and GNU).

**Rollback:** If CI fails or the user aborts at the push confirmation, all local changes (version bumps, tags, commits) are rolled back automatically.

**Post-Push:**
GitHub Actions triggers on tag push and runs release validation (same `make` targets) as safety confirmation.

**git-cliff Configuration (`cliff.toml`):**

```toml
[changelog]
header = "# Changelog\n\nAll notable changes to Nest.\n\n"
body = """
## [{{ version }}] - {{ timestamp | date(format="%Y-%m-%d") }}
{% for group, commits in commits | group_by(attribute="group") %}
### {{ group | upper_first }}
{% for commit in commits %}
- {% if commit.scope %}**{{ commit.scope }}**: {% endif %}{{ commit.message }}
{%- endfor %}
{% endfor %}
"""
trim = true
footer = ""

[git]
conventional_commits = true
filter_unconventional = true
filter_commits = true
tag_pattern = "v[0-9]*"
sort_commits = "newest"
commit_parsers = [
  { message = "^feat", group = "Features" },
  { message = "^fix", group = "Bug Fixes" },
  { message = "^doc", group = "Documentation" },
  { message = "^perf", group = "Performance" },
  { message = "^refactor", group = "Refactoring" },
  { message = "^test", group = "Testing" },
  { message = "^chore\\(release\\)", skip = true },
  { message = "^chore", group = "Maintenance" },
]
```

### User Configuration Storage

**Location:** `~/.config/nest/config.toml`

**Purpose:** Store installation source so users never re-enter git URL.

**Schema:**
```toml
[install]
source = "git+https://github.com/jbb10/nest"
installed_version = "1.2.0"
installed_at = "2026-01-12T10:30:00Z"
```

**Behavior:**
- **Created:** Automatically on first `nest` command execution
- **Read by:** `nest update` to determine where to fetch updates from
- **Updated by:** `nest update` after successful version change (updates `installed_version` and `installed_at`)
- **Never requires manual editing** by users

### `nest update` Command Behavior

**Display:**
```
$ nest update

  Current version: 1.2.0
  Latest version:  1.4.0

  Available versions:
    • 1.4.0 (latest)
    • 1.3.1
    • 1.3.0
    • 1.2.1
    • 1.2.0 (installed)

  Update to 1.4.0? [Y/n/version]:
```

**Input Options:**
- `Y` or Enter → Update to latest
- `n` → Cancel
- `1.3.1` → Install specific version (upgrade or downgrade)

**Implementation:**
1. Read `source` from `~/.config/nest/config.toml`
2. Query available tags: `git ls-remote --tags <source>`
3. Parse and sort versions (semver)
4. Display current vs available
5. On confirmation: `uv tool install --force <source>@v{version}`
6. Update `installed_version` and `installed_at` in config.toml

### User Journey

**Initial Install:**
```bash
$ uv tool install git+https://github.com/jbb10/nest@latest

Installing nest v1.2.0...
✓ Installed nest

Run 'nest init "Project Name"' to get started.
```
*Config file created at `~/.config/nest/config.toml`*

**Daily Use:**
```bash
$ nest init "Nike"
$ nest sync
$ nest status
# Git URL never needed again
```

**Update:**
```bash
$ nest update
# Shows versions, prompts, updates config on success
```

**Downgrade (if needed):**
```bash
$ nest update
# Enter specific older version when prompted
```

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Project structure and module organization
- Dependency injection approach
- Error handling strategy

**Important Decisions (Shape Architecture):**
- Configuration management (user config + manifest)
- Logging strategy (console vs file)

**Deferred Decisions (Post-MVP):**
- Multi-platform agent support (Cursor, etc.) — architecture supports it, implementation deferred
- Semantic search for large projects — mentioned in PRD roadmap

### Project Structure

```
src/nest/
├── __init__.py
├── __main__.py              # Entry point: python -m nest
├── cli/                     # CLI layer (Typer commands)
│   ├── __init__.py
│   ├── main.py              # App definition, command registration
│   ├── init_cmd.py
│   ├── sync_cmd.py
│   ├── update_cmd.py
│   ├── status_cmd.py
│   └── doctor_cmd.py
├── core/                    # Business logic (no I/O)
│   ├── __init__.py
│   ├── checksum.py          # SHA-256 computation
│   ├── manifest.py          # Manifest read/write/update
│   ├── index_generator.py   # Master index generation
│   └── version.py           # Version comparison, semver parsing
├── services/                # Orchestration layer
│   ├── __init__.py
│   ├── init_service.py
│   ├── sync_service.py
│   ├── update_service.py
│   ├── status_service.py
│   └── doctor_service.py
├── adapters/                # External dependencies (injectable)
│   ├── __init__.py
│   ├── protocols.py         # Protocol definitions (interfaces)
│   ├── filesystem.py        # File I/O wrapper
│   ├── docling_processor.py # Docling integration
│   ├── git_client.py        # Git tag queries for update
│   └── user_config.py       # ~/.config/nest/config.toml
├── agents/                  # Agent file generation (extensible)
│   ├── __init__.py
│   ├── protocol.py          # AgentWriter protocol
│   ├── vscode_writer.py     # VS Code agent format
│   └── templates/           # Agent instruction templates
│       └── vscode.md.jinja
└── ui/                      # Rich console output
    ├── __init__.py
    ├── console.py           # Shared Rich console instance
    ├── progress.py          # Progress bars, spinners
    └── messages.py          # User guidance messages
```

**Layer Responsibilities:**

| Layer | Responsibility | Dependencies |
|-------|----------------|--------------|
| `cli/` | Argument parsing, composition root | services, ui |
| `services/` | Orchestration, workflow coordination | core, adapters (via protocols) |
| `core/` | Pure business logic, no I/O | None (pure functions) |
| `adapters/` | External system integration | protocols, external libs |
| `agents/` | Agent file generation (Strategy pattern) | protocols, templates |
| `ui/` | Rich console output, user messages | Rich library |

### Dependency Injection

**Approach:** Manual constructor injection (no DI framework)

**Rationale:**
- Project size doesn't warrant framework overhead
- Maximally explicit — AI agents can trace dependencies easily
- No hidden magic or auto-wiring

**Composition Root:** `cli/main.py`

All dependency wiring happens at the CLI layer entry point:

```python
# cli/main.py (composition root)
def create_sync_service() -> SyncService:
    return SyncService(
        filesystem=FileSystemAdapter(),
        processor=DoclingProcessor(),
        manifest=ManifestAdapter(),
    )

@app.command()
def sync(...):
    service = create_sync_service()
    service.execute(...)
```

**Testing Pattern:**
```python
def test_sync_skips_unchanged_files():
    mock_fs = MockFileSystem(files={"doc.pdf": b"..."})
    mock_processor = MockProcessor()
    mock_manifest = MockManifest(existing={"doc.pdf": "sha256..."})
    
    service = SyncService(mock_fs, mock_processor, mock_manifest)
    result = service.execute()
    
    assert mock_processor.process_called == False  # Skipped
```

### Error Handling

**Custom Exception Hierarchy:**

```python
class NestError(Exception):
    """Base for all Nest errors — catch this for general handling"""

class ProcessingError(NestError):
    """Document processing failed (corrupt file, unsupported format)"""

class ManifestError(NestError):
    """Manifest read/write/validation failed"""

class ConfigError(NestError):
    """User configuration invalid or missing"""

class ModelError(NestError):
    """Docling model download or validation failed"""
```

**Result Types for Batch Operations:**

```python
@dataclass
class ProcessingResult:
    source_path: Path
    status: Literal["success", "skipped", "failed"]
    output_path: Path | None = None
    error: str | None = None

@dataclass
class SyncResult:
    processed: list[ProcessingResult]
    orphans_removed: list[Path]
    index_updated: bool
    
    @property
    def success_count(self) -> int: ...
    @property
    def failure_count(self) -> int: ...
    @property
    def skip_count(self) -> int: ...
```

**Error Handling Flow:**

1. Services collect results, never throw on individual file failures
2. Services return aggregated `SyncResult` with all outcomes
3. CLI layer inspects `--on-error` flag:
   - `skip` (default): Report failures, exit 0 if any succeeded
   - `fail`: Exit 1 if any failures occurred
4. All errors logged to `.nest/errors.log` regardless of flag

### Configuration Management

**User Configuration (`~/.config/nest/config.toml`):**

```python
# adapters/user_config.py
from pydantic import BaseModel
from datetime import datetime

class InstallConfig(BaseModel):
    source: str  # git+https://...
    installed_version: str
    installed_at: datetime

class UserConfig(BaseModel):
    install: InstallConfig
```

**Project Manifest (`.nest/manifest.json`):**

```python
# core/manifest.py
from pydantic import BaseModel
from datetime import datetime
from typing import Literal

class FileEntry(BaseModel):
    sha256: str
    processed_at: datetime
    output: str
    status: Literal["success", "failed", "skipped"]

class Manifest(BaseModel):
    nest_version: str
    project_name: str
    last_sync: datetime
    files: dict[str, FileEntry]
```

**Rationale:**
- TOML for user config: Human-editable if needed, Python-native
- JSON for manifest: Machine-focused, PRD-specified format
- Pydantic for both: Validation, serialization, IDE autocompletion

### Logging Strategy

**Two Separate Output Streams:**

| Stream | Purpose | Technology |
|--------|---------|------------|
| Console | User-facing feedback | Rich (not logging) |
| Error Log | Detailed diagnostics | Python `logging` |

**Console Output (Rich):**
- Progress bars during sync
- Success/failure summaries
- User guidance messages
- Color-coded status indicators

**Error Log (`.nest/errors.log`):**

```python
# Format
2026-01-12T10:30:00 ERROR [sync] contracts/alpha.pdf: Password protected file
2026-01-12T10:30:01 ERROR [sync] reports/q3.xlsx: Encoding error (tried UTF-8, Latin-1)
2026-01-12T10:31:00 WARNING [doctor] Model checksum mismatch: TableFormer

# Implementation
import logging

error_logger = logging.getLogger("nest.errors")
error_logger.addHandler(logging.FileHandler(".nest/errors.log"))
error_logger.setLevel(logging.WARNING)
```

**Rule:** Never use `logging` for console output. Never use Rich for error log.

### Decision Impact Analysis

**Implementation Sequence:**

1. **Core protocols and models first** — `adapters/protocols.py`, Pydantic models
2. **Adapters** — FileSystem, UserConfig, Manifest adapters
3. **Core logic** — Checksum, index generation
4. **Services** — Init, Sync, Status, Doctor, Update
5. **CLI commands** — Wire services, add Rich output
6. **Agent generation** — VSCode writer + template

**Cross-Component Dependencies:**

```
cli/main.py
    └── services/*
            └── adapters/protocols.py (interfaces)
            └── core/* (pure logic)
            └── adapters/* (implementations)
            └── agents/* (agent generation)
    └── ui/* (console output)
```

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:** 8 areas where AI agents could make different choices

All AI agents working on Nest MUST follow these patterns exactly. Deviation will cause integration conflicts.

### Naming Patterns

**Python Naming (PEP 8 — No Deviations):**

| Element | Convention | Example |
|---------|------------|--------|
| Modules/files | `lowercase_with_underscores` | `sync_service.py` |
| Classes | `PascalCase` | `class SyncService:` |
| Functions/methods | `lowercase_with_underscores` | `def compute_checksum():` |
| Variables | `lowercase_with_underscores` | `file_path = Path(...)` |
| Constants | `UPPERCASE_WITH_UNDERSCORES` | `DEFAULT_TIMEOUT = 30` |
| Private | Leading underscore | `_internal_helper()` |

**Examples:**
```python
# ✓ Correct
class DoclingProcessor:
    def process_document(self, source_path: Path) -> ProcessingResult:
        raw_content = self._extract_content(source_path)
        return ProcessingResult(status="success", output_path=output_path)

# ✗ Wrong
class doclingProcessor:  # Should be PascalCase
    def processDocument(self, sourcePath):  # Should be snake_case
```

### Import Patterns

**Rule: Absolute imports only. No relative imports.**

```python
# ✓ Correct
from nest.adapters.filesystem import FileSystemAdapter
from nest.core.checksum import compute_sha256
from nest.services.sync_service import SyncService

# ✗ Wrong
from ..adapters.filesystem import FileSystemAdapter
from .checksum import compute_sha256
```

**Import ordering (enforced by Ruff):**
1. Standard library
2. Third-party packages
3. Local application imports

```python
import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console

from nest.adapters.protocols import FileSystemProtocol
from nest.core.checksum import compute_sha256
```

### Type Hint Patterns

**Rule: Modern Python 3.10+ syntax. Explicit types on all public functions.**

```python
# ✓ Correct (modern syntax)
def process_files(
    paths: list[Path],
    options: dict[str, str] | None = None,
) -> list[ProcessingResult]:
    ...

# ✗ Wrong (legacy syntax)
from typing import Dict, List, Optional
def process_files(
    paths: List[Path],
    options: Optional[Dict[str, str]] = None,
) -> List[ProcessingResult]:
```

**Type rules:**
- Use `Path` not `str` for filesystem paths
- Use `datetime` not `str` for timestamps
- Use `| None` not `Optional[]`
- Use `list[]`, `dict[]` not `List[]`, `Dict[]`
- Explicit return type on all public functions and methods
- Use `Literal[]` for string enums: `Literal["success", "failed", "skipped"]`

### Docstring Patterns

**Rule: Google style docstrings on all public functions, classes, and modules.**

```python
def compute_checksum(path: Path, algorithm: str = "sha256") -> str:
    """Compute cryptographic hash of a file.
    
    Reads the file in chunks to handle large files efficiently.
    
    Args:
        path: Path to the file to hash.
        algorithm: Hash algorithm to use. Defaults to "sha256".
        
    Returns:
        Hex-encoded hash string.
        
    Raises:
        FileNotFoundError: If path does not exist.
        PermissionError: If file is not readable.
        
    Example:
        >>> compute_checksum(Path("doc.pdf"))
        'e3b0c44298fc1c149afbf4c8996fb924...'
    """
```

**Class docstrings:**
```python
class SyncService:
    """Orchestrates document synchronization workflow.
    
    Coordinates file discovery, checksum comparison, document processing,
    and manifest updates. Designed for dependency injection.
    
    Attributes:
        filesystem: Filesystem adapter for I/O operations.
        processor: Document processor for conversions.
        manifest: Manifest manager for state tracking.
    """
```

### Test Patterns

**Structure: Separate `tests/` directory mirroring `src/nest/`**

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── cli/
│   ├── __init__.py
│   └── test_sync_cmd.py
├── core/
│   ├── __init__.py
│   └── test_checksum.py
├── services/
│   ├── __init__.py
│   └── test_sync_service.py
├── adapters/
│   ├── __init__.py
│   └── test_filesystem.py
└── integration/
    ├── __init__.py
    └── test_full_sync.py
```

**File naming:** `test_{module}.py`

**Function naming:** `test_{behavior}_when_{condition}` or `test_{behavior}`

```python
# ✓ Good test names
def test_sync_skips_unchanged_files():
def test_sync_processes_new_files():
def test_sync_fails_when_manifest_corrupt():
def test_checksum_handles_large_files():

# ✗ Bad test names
def test_sync():  # Too vague
def test1():  # Meaningless
def sync_test():  # Wrong prefix
```

**Test structure (Arrange-Act-Assert):**
```python
def test_sync_skips_unchanged_files():
    # Arrange
    mock_fs = MockFileSystem(files={"doc.pdf": b"content"})
    mock_manifest = MockManifest(existing={"doc.pdf": "abc123"})
    mock_fs.compute_hash = lambda p: "abc123"  # Same hash
    service = SyncService(mock_fs, MockProcessor(), mock_manifest)
    
    # Act
    result = service.execute(Path("_nest_sources"))
    
    # Assert
    assert result.skip_count == 1
    assert result.success_count == 0
```

### CLI Output Patterns

**Rich console icons and colors:**

| Outcome | Icon | Color | Example |
|---------|------|-------|--------|
| Success | ✓ | Green | `✓ Processed 10 files` |
| Failure | ✗ | Red | `✗ Failed to process alpha.pdf` |
| Warning | ⚠ | Yellow | `⚠ Model checksum mismatch` |
| Info | • | Blue | `• Scanning _nest_sources/` |
| Progress | bar | Cyan | `Processing [████████--] 80%` |

**Message formatting rules:**
- Imperative for ongoing actions: "Processing files..."
- Past tense for completed actions: "Processed 10 files"
- No periods at end of single-line messages
- Capitalize first word only
- Use Rich markup: `[green]✓[/green] Success`

**Example output implementation:**
```python
# ui/messages.py
from rich.console import Console

console = Console()

def success(message: str) -> None:
    console.print(f"[green]✓[/green] {message}")

def error(message: str) -> None:
    console.print(f"[red]✗[/red] {message}")

def warning(message: str) -> None:
    console.print(f"[yellow]⚠[/yellow] {message}")

def info(message: str) -> None:
    console.print(f"[blue]•[/blue] {message}")
```

### Error Message Patterns

**User-facing errors (Rich console):**

Format: What happened → Why → What to do

```python
# Pattern
error("Cannot process {file}")
console.print(f"  Reason: {reason}")
console.print(f"  Action: {suggested_action}")

# Example output
✗ Cannot process contracts/alpha.pdf
  Reason: File is password protected
  Action: Remove password protection and run `nest sync` again
```

**Log errors (`.nest/errors.log`):**

Format: `{timestamp} {level} [{context}] {file}: {technical_detail}`

```
2026-01-12T10:30:00 ERROR [sync] contracts/alpha.pdf: Password protected (PyPDF2.PdfReadError: File has not been decrypted)
2026-01-12T10:30:01 ERROR [sync] reports/q3.xlsx: Encoding error (UnicodeDecodeError: 'utf-8' codec can't decode byte 0x80)
2026-01-12T10:31:00 WARNING [doctor] TableFormer model: Checksum mismatch (expected abc123, got def456)
```

### Path Handling Patterns

**Rule: Always use `pathlib.Path`. Never string concatenation.**

**Centralized Path Constants (`core/paths.py`):**

All directory names, special filenames, and extension lists are defined as constants in `core/paths.py`. All modules MUST import from this single source of truth.

```python
# core/paths.py — Single source of truth for path constants
SOURCES_DIR = "_nest_sources"
CONTEXT_DIR = "_nest_context"
MASTER_INDEX_FILE = "00_MASTER_INDEX.md"

# Extensions for Docling source processing (files that need conversion)
SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".xlsx", ".html"]

# Extensions for context text files (indexable in _nest_context/)
# These are plain-text formats an LLM can reason about as project context.
# Used by: index generation, status counting, user-curated file counting.
CONTEXT_TEXT_EXTENSIONS = [
    ".md", ".txt", ".text", ".rst",
    ".csv", ".json", ".yaml", ".yml", ".toml", ".xml",
]
```

**Usage Rules:**
- `SUPPORTED_EXTENSIONS` — Used **only** by discovery service when scanning `_nest_sources/` for files needing Docling processing.
- `CONTEXT_TEXT_EXTENSIONS` — Used by index service, status service, and orphan service when scanning `_nest_context/` to determine which files are text-based context. Any file in `_nest_context/` whose extension is NOT in this list is ignored (not indexed, not counted).
- Both constants MUST be imported from `nest.core.paths`. Never hardcode extension lists elsewhere.

```python
# ✓ Correct
from pathlib import Path

def get_output_path(source: Path, sources_dir: Path, context_dir: Path) -> Path:
    relative = source.relative_to(sources_dir)
    return context_dir / relative.with_suffix(".md")

# ✗ Wrong
import os

def get_output_path(source: str, sources_dir: str, context_dir: str) -> str:
    relative = source.replace(sources_dir, "")
    return os.path.join(context_dir, relative.replace(".pdf", ".md"))
```

**Path rules:**
- Use `/` operator for joining: `base / "subdir" / "file.txt"`
- Resolve at entry points: `path.resolve()` when receiving from CLI
- Store relative paths in manifest (for portability)
- Convert to absolute when performing I/O
- Use `.exists()`, `.is_file()`, `.is_dir()` for checks

### Enforcement Guidelines

**All AI Agents MUST:**

1. Run `ruff check` and `ruff format` before every commit
2. Run `pyright` with strict mode before every commit
3. Follow naming conventions exactly — no "creative variations"
4. Use absolute imports only
5. Include type hints on all public functions
6. Write Google-style docstrings on all public interfaces
7. Place tests in `tests/` directory mirroring source structure
8. Use Rich console helpers for user output, never `print()`
9. Use `pathlib.Path` for all filesystem operations
10. Follow error message patterns (What → Why → Action)

**Pattern Violations:**
- CI will fail on Ruff/Pyright errors
- Code review should catch convention deviations
- When in doubt, refer to this document

### Text File I/O Encoding Standard

**All text file I/O MUST explicitly specify `encoding='utf-8'`.**

Relying on Python's platform-dependent default encoding causes cross-platform inconsistencies:
- macOS/Linux default to UTF-8
- Windows may default to CP1252 or locale-specific encodings

This leads to corrupt manifest keys, false change detection, and forced rebuilds on Windows.

```python
# ✓ ALWAYS specify encoding for text I/O
path.write_text(content, encoding='utf-8')
path.read_text(encoding='utf-8')
open(path, 'r', encoding='utf-8')
open(path, 'w', encoding='utf-8')

# ✗ NEVER rely on platform defaults
path.write_text(content)  # Platform-dependent!
path.read_text()          # Platform-dependent!
```

**Where to apply:**
- Adapter layer (`FileSystemAdapter`, `ManifestAdapter`) — protects all downstream services
- Any service that bypasses adapters for direct `Path` I/O (e.g., `.gitignore` handling)
- Binary I/O (`read_bytes()`, `shutil.copy2`) is not affected

### Line Ending Normalization Standard

**All Nest-generated text files MUST use LF (`\n`) line endings, regardless of platform.**

Nest projects are committed to Git as a shared knowledge base. Because `compute_sha256()` hashes raw bytes (binary mode), line ending differences between platforms produce different checksums for identical content — causing false "modified" detection and unnecessary full rebuilds.

**Two-Layer Defense:**

**Layer 1 — Python writes (belt):** All `write_text()` calls for Nest-generated output MUST pass `newline="\n"` to force LF on all platforms:

```python
# ✓ ALWAYS specify newline for Nest-generated text
path.write_text(content, encoding='utf-8', newline='\n')

# ✗ Produces CRLF on Windows
path.write_text(content, encoding='utf-8')
```

**Where to apply `newline='\n'`:**
- `FileSystemAdapter.write_text()` — all service-generated output
- `DoclingProcessor` — converted Markdown output
- `InitService._setup_gitignore()` and `_setup_gitattributes()` — project config files
- Any direct `Path.write_text()` call for Nest-generated content

**Where NOT to apply:**
- `PassthroughProcessor` — uses `shutil.copy2()` (binary copy), preserving original content. Line endings are normalized by `.gitattributes` at the Git layer.
- `read_text()` calls — Python's universal newline mode handles reading correctly

**Layer 2 — `.gitattributes` (suspenders):** `nest init` generates a `.gitattributes` file that enforces LF normalization for all committed text files and marks binary documents correctly:

```gitattributes
# Binary source documents — never touch line endings
_nest_sources/**/*.pdf binary
_nest_sources/**/*.docx binary
_nest_sources/**/*.pptx binary
_nest_sources/**/*.xlsx binary
_nest_sources/**/*.html binary

# Text source files — normalize to LF for consistent checksums
_nest_sources/**/*.md text eol=lf
_nest_sources/**/*.txt text eol=lf
_nest_sources/**/*.yaml text eol=lf
_nest_sources/**/*.yml text eol=lf
_nest_sources/**/*.json text eol=lf
_nest_sources/**/*.csv text eol=lf
_nest_sources/**/*.xml text eol=lf
_nest_sources/**/*.rst text eol=lf
_nest_sources/**/*.toml text eol=lf

# Context output — same LF normalization
_nest_context/**/*.md text eol=lf
_nest_context/**/*.txt text eol=lf
_nest_context/**/*.yaml text eol=lf
_nest_context/**/*.yml text eol=lf
_nest_context/**/*.json text eol=lf
_nest_context/**/*.csv text eol=lf
_nest_context/**/*.xml text eol=lf
_nest_context/**/*.rst text eol=lf
_nest_context/**/*.toml text eol=lf

# Nest metadata — LF normalized
.nest/**/*.json text eol=lf
.nest/**/*.md text eol=lf
.nest/**/*.yaml text eol=lf
```

**Why both layers?**
- `.gitattributes` catches user-contributed passthrough files (e.g., a `.md` file created on Windows with CRLF, added to `_nest_sources/`, and committed). Git normalizes on commit.
- `newline='\n'` ensures Nest never *produces* CRLF in the first place, so there's no normalization step needed.

### Git Strategy: Shared Knowledge Base

**All Nest project files are committed to Git** except the per-machine error log. This enables the "shared knowledge database" model where one team member processes documents and the entire team benefits without installing Nest.

**`.gitignore` (generated by `nest init`):**
```
# Nest - per-machine runtime artifacts
.nest/errors.log
```

**What is committed and why:**

| Path | Committed | Rationale |
|------|-----------|-----------|
| `_nest_sources/` | ✅ | Source documents shared so any team member can add new ones |
| `_nest_context/` | ✅ | AI-readable output — the core value of the shared knowledge base |
| `.nest/manifest.json` | ✅ | Prevents unnecessary re-syncs when a teammate runs sync |
| `.nest/00_MASTER_INDEX.md` | ✅ | Part of the knowledge base, read by the `@nest` agent |
| `.nest/00_INDEX_HINTS.yaml` | ✅ | Enables incremental AI enrichment across team members |
| `.nest/errors.log` | ❌ | Per-machine runtime diagnostics, not shareable |
| `.gitattributes` | ✅ | Cross-platform consistency rules |
| `.github/agents/` | ✅ | VS Code agent definition |

### Anti-Patterns (What NOT to Do)

```python
# ✗ Mixed naming styles
class syncService:  # Should be PascalCase
    def ProcessFile(self):  # Should be snake_case

# ✗ Relative imports
from ..core import checksum

# ✗ Legacy type hints
from typing import Optional, List
def process(items: List[str]) -> Optional[str]:

# ✗ String path manipulation
output = input_path.replace(".pdf", ".md")

# ✗ Print instead of Rich
print("Processing files...")

# ✗ Vague error messages
raise Exception("Error")  # What error? Why? What to do?

# ✗ Missing type hints
def process(path):  # No types
    return result  # Unknown return type

# ✗ Platform-dependent encoding
path.write_text(content)  # Missing encoding='utf-8'
path.read_text()          # Missing encoding='utf-8'
```

## Project Structure & Boundaries

### Complete Project Directory Structure

```
nest/
├── .github/
│   └── workflows/
│       └── ci.yml                   # CI workflow definition
├── cliff.toml                       # git-cliff changelog config
├── pyproject.toml                   # Package definition, dependencies, tool config
├── README.md                        # Project overview, installation, usage
├── CHANGELOG.md                     # Release history (generated by git-cliff)
├── LICENSE                          # License file
├── .gitignore                       # Git ignore patterns
├── .python-version                  # Python version for uv
│
├── scripts/                         # CI/CD and development scripts
│   ├── ci-lint.sh                   # Ruff check + format verification
│   ├── ci-typecheck.sh              # Pyright strict mode
│   ├── ci-test.sh                   # pytest with coverage
│   ├── ci-integration.sh            # Docling integration tests
│   └── release.sh                   # Release workflow with human gate
│
├── src/
│   └── nest/
│       ├── __init__.py              # Package version, metadata
│       ├── __main__.py              # Entry point: python -m nest
│       ├── py.typed                 # PEP 561 marker for type hints
│       │
│       ├── cli/                     # CLI layer (Typer commands)
│       │   ├── __init__.py
│       │   ├── main.py              # App definition, composition root
│       │   ├── init_cmd.py          # nest init command
│       │   ├── sync_cmd.py          # nest sync command
│       │   ├── update_cmd.py        # nest update command
│       │   ├── status_cmd.py        # nest status command
│       │   └── doctor_cmd.py        # nest doctor command
│       │
│       ├── core/                    # Business logic (pure, no I/O)
│       │   ├── __init__.py
│       │   ├── checksum.py          # SHA-256 computation
│       │   ├── manifest.py          # Manifest Pydantic models
│       │   ├── index_generator.py   # Master index generation logic
│       │   ├── version.py           # Semver parsing, comparison
│       │   └── exceptions.py        # Custom exception hierarchy
│       │
│       ├── services/                # Orchestration layer
│       │   ├── __init__.py
│       │   ├── init_service.py      # Init workflow orchestration
│       │   ├── sync_service.py      # Sync workflow orchestration
│       │   ├── update_service.py    # Update workflow orchestration
│       │   ├── status_service.py    # Status computation
│       │   └── doctor_service.py    # Health check orchestration
│       │
│       ├── adapters/                # External dependencies (injectable)
│       │   ├── __init__.py
│       │   ├── protocols.py         # Protocol definitions (interfaces)
│       │   ├── filesystem.py        # File I/O operations
│       │   ├── docling_processor.py # Docling document conversion
│       │   ├── git_client.py        # Git tag queries for update
│       │   ├── user_config.py       # ~/.config/nest/config.toml
│       │   └── manifest_adapter.py  # .nest/manifest.json I/O
│       │
│       ├── agents/                  # Agent file generation
│       │   ├── __init__.py
│       │   ├── protocol.py          # AgentWriter protocol
│       │   ├── vscode_writer.py     # VS Code agent implementation
│       │   └── templates/
│       │       └── vscode.md.jinja  # VS Code agent template
│       │
│       └── ui/                      # Rich console output
│           ├── __init__.py
│           ├── console.py           # Shared Rich console instance
│           ├── progress.py          # Progress bars, spinners
│           └── messages.py          # User guidance messages
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Shared fixtures, mock factories
│   │
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── test_init_cmd.py
│   │   ├── test_sync_cmd.py
│   │   ├── test_update_cmd.py
│   │   ├── test_status_cmd.py
│   │   └── test_doctor_cmd.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── test_checksum.py
│   │   ├── test_manifest.py
│   │   ├── test_index_generator.py
│   │   └── test_version.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── test_init_service.py
│   │   ├── test_sync_service.py
│   │   ├── test_update_service.py
│   │   ├── test_status_service.py
│   │   └── test_doctor_service.py
│   │
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── test_filesystem.py
│   │   ├── test_docling_processor.py
│   │   ├── test_git_client.py
│   │   └── test_user_config.py
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   └── test_vscode_writer.py
│   │
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_full_init.py        # End-to-end init workflow
│   │   ├── test_full_sync.py        # End-to-end sync with real Docling
│   │   └── test_full_update.py      # End-to-end update workflow
│   │
│   └── fixtures/
│       ├── __init__.py
│       ├── sample_files/            # Test PDFs, XLSX, etc.
│       │   ├── simple.pdf
│       │   ├── with_tables.pdf
│       │   ├── spreadsheet.xlsx
│       │   └── password_protected.pdf
│       └── expected_outputs/        # Expected Markdown conversions
│           ├── simple.md
│           ├── with_tables.md
│           └── spreadsheet.md
│
└── docs/
    ├── architecture.md              # This document (or link to it)
    ├── development.md               # Developer setup guide
    └── user-guide.md                # End-user documentation
```

### Architectural Boundaries

#### Layer Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│   cli/main.py, cli/*_cmd.py                                │
│   - Parses arguments (Typer)                               │
│   - Composition root (wires dependencies)                  │
│   - Calls services                                         │
│   - Formats output (Rich via ui/)                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                          │
│   services/*_service.py                                    │
│   - Orchestrates workflows                                 │
│   - Depends on protocols (not implementations)             │
│   - Returns result types                                   │
│   - Contains no I/O code                                   │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Core Layer    │  │ Adapters Layer  │  │  Agents Layer   │
│   core/*.py     │  │ adapters/*.py   │  │  agents/*.py    │
│                 │  │                 │  │                 │
│ - Pure functions│  │ - Implements    │  │ - AgentWriter   │
│ - Pydantic     │  │   protocols     │  │   protocol      │
│   models       │  │ - Wraps Docling │  │ - Template      │
│ - No I/O       │  │ - File I/O      │  │   rendering     │
│ - Testable     │  │ - Git queries   │  │ - Extensible    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

#### Protocol Boundaries (adapters/protocols.py)

```python
from typing import Protocol
from pathlib import Path

class FileSystemProtocol(Protocol):
    def read_bytes(self, path: Path) -> bytes: ...
    def write_text(self, path: Path, content: str) -> None: ...
    def list_files(self, directory: Path, pattern: str) -> list[Path]: ...
    def exists(self, path: Path) -> bool: ...
    def mkdir(self, path: Path) -> None: ...
    def remove(self, path: Path) -> None: ...

class DocumentProcessorProtocol(Protocol):
    def process(self, source: Path) -> str: ...
    def supports(self, extension: str) -> bool: ...

class ManifestProtocol(Protocol):
    def load(self, path: Path) -> Manifest: ...
    def save(self, path: Path, manifest: Manifest) -> None: ...

class GitClientProtocol(Protocol):
    def list_tags(self, remote_url: str) -> list[str]: ...

class UserConfigProtocol(Protocol):
    def load(self) -> UserConfig | None: ...
    def save(self, config: UserConfig) -> None: ...

class AgentWriterProtocol(Protocol):
    def write(self, project_name: str, output_dir: Path) -> Path: ...
```

### PRD Command to Module Mapping

| PRD Command | CLI | Service | Adapters Used |
|-------------|-----|---------|---------------|
| `nest init` | `init_cmd.py` | `InitService` | FileSystem, AgentWriter, Manifest, DoclingProcessor (model download) |
| `nest sync` | `sync_cmd.py` | `SyncService` | FileSystem, DoclingProcessor, Manifest |
| `nest update` | `update_cmd.py` | `UpdateService` | GitClient, UserConfig |
| `nest status` | `status_cmd.py` | `StatusService` | FileSystem, Manifest |
| `nest doctor` | `doctor_cmd.py` | `DoctorService` | FileSystem, UserConfig, DoclingProcessor |

### File Purpose Index

| File | Purpose |
|------|--------|
| `pyproject.toml` | Package metadata, dependencies, tool config (Ruff, Pyright, pytest) |
| `cliff.toml` | Changelog generation from conventional commits |
| `.github/workflows/ci.yml` | CI workflow: lint, typecheck, test matrix |
| `scripts/release.sh` | Release workflow with human approval gate |
| `src/nest/cli/main.py` | Typer app definition, composition root |
| `src/nest/core/exceptions.py` | `NestError`, `ProcessingError`, `ConfigError`, etc. |
| `src/nest/core/manifest.py` | `Manifest`, `FileEntry` Pydantic models |
| `src/nest/adapters/protocols.py` | All protocol definitions for DI |
| `src/nest/agents/templates/vscode.md.jinja` | VS Code agent instruction template |
| `src/nest/ui/messages.py` | `success()`, `error()`, `warning()`, `info()` |
| `tests/conftest.py` | `MockFileSystem`, `MockProcessor`, `MockManifest` factories |
| `tests/fixtures/sample_files/` | Real test documents for integration tests |

### Data Flow: Sync Command

```
User runs: nest sync

CLI Layer (sync_cmd.py)
    │
    ├─ Parse args (--on-error, --dry-run, --force)
    ├─ Create SyncService with injected adapters
    └─ Call service.execute()
          │
Service Layer (sync_service.py)
    │
    ├─ filesystem.list_files(_nest_sources/)
    ├─ manifest.load(.nest/manifest.json)
    │
    ├─ For each file:
    │     ├─ core.checksum.compute_sha256(file)
    │     ├─ Compare with manifest entry
    │     │
    │     ├─ If changed/new:
    │     │     ├─ processor.process(file) → markdown
    │     │     ├─ filesystem.write_text(_nest_context/...)
    │     │     └─ Add to results
    │     │
    │     └─ If unchanged:
    │           └─ Skip, add to results
    │
    ├─ Remove orphans (if enabled)
    ├─ core.index_generator.generate() → 00_MASTER_INDEX.md
    │     (scans _nest_context/ for CONTEXT_TEXT_EXTENSIONS files)
    ├─ manifest.save(updated_manifest)
    │
    └─ Return SyncResult
          │
CLI Layer (sync_cmd.py)
    │
    ├─ ui.progress.show_results(result)
    ├─ If failures and --on-error=fail: exit(1)
    └─ ui.messages.success("Synced N files")
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
All technology choices work together seamlessly:
- Python 3.10+ provides modern type syntax for Pyright strict mode
- Typer + Rich are designed to work together for CLI UX
- Pydantic integrates naturally with JSON/TOML for config serialization
- uv + src layout follows current Python packaging best practices
- pytest + DI pattern enables comprehensive testing with mocks

**Pattern Consistency:**
All implementation patterns align with technology choices:
- PEP 8 naming enforced by Ruff
- Modern type hints work with Pyright strict
- Google docstrings supported by tooling
- Absolute imports prevent circular dependency issues

**Structure Alignment:**
Project structure fully supports architectural decisions:
- Layered architecture enables separation of concerns
- Protocol-based adapters enable dependency injection
- Agent module isolation enables future platform extensibility
- Test structure mirrors source for easy navigation

### Requirements Coverage Validation ✅

**PRD Command Coverage:**

| Command | Service | Adapters | Status |
|---------|---------|----------|--------|
| `nest init` | InitService | FileSystem, AgentWriter, Manifest, DoclingProcessor | ✅ |
| `nest sync` | SyncService | FileSystem, DoclingProcessor, Manifest | ✅ |
| `nest update` | UpdateService | GitClient, UserConfig | ✅ |
| `nest status` | StatusService | FileSystem, Manifest | ✅ |
| `nest doctor` | DoctorService | FileSystem, UserConfig, DoclingProcessor | ✅ |

**Non-Functional Requirements Coverage:**

| NFR | Architectural Support | Status |
|-----|----------------------|--------|
| Privacy (local-only) | Docling runs entirely locally | ✅ |
| Performance (incremental) | SHA-256 manifest checksums | ✅ |
| Reliability (error handling) | Custom exceptions + Result types | ✅ |
| Portability (cross-platform) | pathlib.Path everywhere | ✅ |
| Maintainability (DRY) | Shared adapters, composition root | ✅ |
| Testability | Protocol-based DI, pure core functions | ✅ |
| Extensibility | AgentWriter protocol for future platforms | ✅ |

### Implementation Readiness Validation ✅

**Decision Completeness:**
- All critical decisions documented with rationale
- Technology stack fully specified
- Implementation patterns comprehensive with examples
- Anti-patterns explicitly documented

**Structure Completeness:**
- Complete directory tree (50+ files)
- All integration points mapped
- Test fixtures defined
- Data flow documented

**Pattern Completeness:**
- 8 naming convention categories defined
- Import, type, and docstring patterns specified
- Test structure and naming patterns established
- CLI output and error message patterns documented

### Gap Analysis Results

**Critical Gaps:** None — architecture is implementation-ready

**Important Gaps (non-blocking, address during implementation):**
- Specific Docling configuration (document during DoclingProcessor implementation)
- Exact pyproject.toml contents (generate during project scaffolding)
- Rich progress bar specifics (establish in first sync command)

**Deferred Items (post-MVP):**
- Pre-commit hook configuration
- VSCode workspace settings
- Performance benchmarking framework
- Additional agent writers (Cursor, etc.)

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed (Medium complexity CLI)
- [x] Technical constraints identified (uv, Docling, VS Code format)
- [x] Cross-cutting concerns mapped (error handling, logging, paths)

**✅ Architectural Decisions**
- [x] Critical decisions documented (structure, DI, error handling)
- [x] Technology stack fully specified (Python 3.10+, Typer, Rich, Docling, Pydantic)
- [x] CI/CD strategy defined (GitHub Actions + local scripts)
- [x] Release process documented (trunk-based, conventional commits, git-cliff)

**✅ Implementation Patterns**
- [x] Naming conventions established (PEP 8)
- [x] Structure patterns defined (layered architecture)
- [x] Communication patterns specified (protocol-based DI)
- [x] Process patterns documented (error handling, logging)

**✅ Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** ✅ READY FOR IMPLEMENTATION

**Confidence Level:** HIGH

**Key Strengths:**
- Clean layered architecture with clear boundaries
- Protocol-based DI enables comprehensive testing
- Extensible agent generation for future platforms
- Comprehensive patterns prevent AI agent conflicts
- Well-documented CI/CD and release process

**Areas for Future Enhancement:**
- Semantic search for large projects (PRD roadmap item)
- Multi-platform agent support (architecture supports, implementation deferred)
- Performance optimization for very large document sets
- Watch mode for automatic sync (PRD roadmap item)

### Implementation Handoff

**AI Agent Guidelines:**
1. Follow all architectural decisions exactly as documented
2. Use implementation patterns consistently across all components
3. Respect project structure and layer boundaries
4. Run CI scripts locally before committing
5. Use conventional commits for all changes
6. Always create feature branch before any code changes
7. Refer to this document for all architectural questions

**Git Workflow for AI Developers:**
1. `git checkout main && git pull origin main`
2. `git checkout -b feat/{story-key}` (or fix/, chore/, etc.)
3. Make commits following conventional commit format
4. Run CI scripts before each commit
5. Push branch, get review if needed
6. Merge to main (squash or regular)
7. Delete feature branch

**Implementation Priority Order:**
1. Project scaffolding (pyproject.toml, directory structure)
2. Core protocols and Pydantic models
3. Adapters (FileSystem, Manifest)
4. Core logic (checksum, index generator)
5. Services (Init → Sync → Status → Doctor → Update)
6. CLI commands with Rich output
7. Agent generation (VSCode writer)
8. CI/CD scripts and pipeline


---
project_name: 'Nest'
user_name: 'Jóhann'
date: '2026-01-12'
sections_completed: ['technology_stack', 'python_language_rules', 'architecture_di', 'cli_output_error_handling', 'testing_rules', 'git_workflow_ci', 'path_handling', 'anti_patterns']
status: 'complete'
rule_count: 47
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in Nest. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.10+ | Core language (required for Docling, modern type hints) |
| Typer | latest | CLI framework |
| Rich | latest | Terminal output (progress, colors, formatting) |
| Docling | latest | IBM document processor (PDF/XLSX/PPTX → Markdown) |
| Pydantic | v2 | Configuration & manifest validation |
| uv | latest | Package manager (dev + distribution) |
| Pyright | strict | Type checking (matches VSCode/Pylance) |
| Ruff | latest | Linting + formatting (replaces flake8/black/isort) |
| pytest | latest | Testing framework |
| git-cliff | latest | Changelog generation |

**Runtime Requirements:**
- Docling models: ~1.5-2GB cached at `~/.cache/docling/`
- User config: `~/.config/nest/config.toml`

---

## Critical Implementation Rules

### Python Language Rules

**Naming (PEP 8 — No Deviations):**
- Modules/files: `lowercase_with_underscores` → `sync_service.py`
- Classes: `PascalCase` → `class SyncService:`
- Functions/methods: `snake_case` → `def compute_checksum():`
- Constants: `UPPERCASE` → `DEFAULT_TIMEOUT = 30`
- Private: Leading underscore → `_internal_helper()`

**Imports (Absolute Only):**
```python
# ✓ Correct
from nest.adapters.filesystem import FileSystemAdapter
from nest.core.checksum import compute_sha256

# ✗ NEVER relative imports
from ..adapters.filesystem import FileSystemAdapter
```

**Import Order (Ruff-enforced):**
1. Standard library
2. Third-party packages  
3. Local application

**Type Hints (Modern 3.10+ Syntax):**
```python
# ✓ Correct
def process(paths: list[Path], opts: dict[str, str] | None = None) -> list[Result]:

# ✗ NEVER legacy syntax
from typing import List, Optional, Dict
def process(paths: List[Path], opts: Optional[Dict[str, str]] = None):
```

**Type Rules:**
- `Path` not `str` for filesystem paths
- `datetime` not `str` for timestamps
- `| None` not `Optional[]`
- `list[]`, `dict[]` not `List[]`, `Dict[]`
- `Literal["a", "b"]` for string enums
- Explicit return type on ALL public functions

**Docstrings (Google Style):**
```python
def compute_checksum(path: Path, algorithm: str = "sha256") -> str:
    """Compute cryptographic hash of a file.
    
    Args:
        path: Path to the file to hash.
        algorithm: Hash algorithm. Defaults to "sha256".
        
    Returns:
        Hex-encoded hash string.
        
    Raises:
        FileNotFoundError: If path does not exist.
    """
```

---

### Architecture & Dependency Injection

**Layer Structure:**
```
cli/          → Argument parsing, composition root, calls services
services/     → Orchestration, depends on protocols (not implementations)
core/         → Pure business logic, NO I/O, fully testable
adapters/     → External system wrappers, implement protocols
agents/       → Agent file generation (Strategy pattern)
ui/           → Rich console output helpers
```

**Composition Root:** `cli/main.py` — ALL dependency wiring happens here:
```python
def create_sync_service() -> SyncService:
    return SyncService(
        filesystem=FileSystemAdapter(),
        processor=DoclingProcessor(),
        manifest=ManifestAdapter(),
    )
```

**Protocol-Based DI (adapters/protocols.py):**
```python
class FileSystemProtocol(Protocol):
    def read_bytes(self, path: Path) -> bytes: ...
    def write_text(self, path: Path, content: str) -> None: ...
    def exists(self, path: Path) -> bool: ...

class DocumentProcessorProtocol(Protocol):
    def process(self, source: Path) -> str: ...
```

**Services depend on protocols, never implementations:**
```python
class SyncService:
    def __init__(
        self,
        filesystem: FileSystemProtocol,      # Protocol, not FileSystemAdapter
        processor: DocumentProcessorProtocol,
        manifest: ManifestProtocol,
    ): ...
```

**Testing Pattern (mock via constructor):**
```python
def test_sync_skips_unchanged():
    service = SyncService(
        filesystem=MockFileSystem(...),
        processor=MockProcessor(),
        manifest=MockManifest(...),
    )
    result = service.execute()
    assert result.skip_count == 1
```

---

### CLI Output Patterns

**NEVER use `print()` — Always use Rich helpers:**
```python
from nest.ui.messages import success, error, warning, info

success("Processed 10 files")      # ✓ green
error("Failed to process doc.pdf") # ✗ red
warning("Model checksum mismatch") # ⚠ yellow
info("Scanning raw_inbox/")        # • blue
```

**Message Formatting:**
- Imperative for ongoing: "Processing files..."
- Past tense for completed: "Processed 10 files"
- No periods at end of single-line messages
- Capitalize first word only

**User-Facing Errors (What → Why → Action):**
```python
error("Cannot process contracts/alpha.pdf")
console.print("  Reason: File is password protected")
console.print("  Action: Remove password and run `nest sync` again")
```

**Error Log Format (`.nest_errors.log`):**
```
2026-01-12T10:30:00 ERROR [sync] contracts/alpha.pdf: Password protected
2026-01-12T10:30:01 ERROR [sync] reports/q3.xlsx: Encoding error (UTF-8)
```

**Two Output Streams (never mix):**
- Console → Rich (user-facing feedback)
- Error log → Python `logging` (diagnostics)

---

### Error Handling

**Custom Exception Hierarchy:**
```python
class NestError(Exception): ...          # Base - catch for general handling
class ProcessingError(NestError): ...    # Document processing failed
class ManifestError(NestError): ...      # Manifest read/write failed
class ConfigError(NestError): ...        # User config invalid
class ModelError(NestError): ...         # Docling model issues
```

**Result Types for Batch Operations:**
```python
@dataclass
class ProcessingResult:
    source_path: Path
    status: Literal["success", "skipped", "failed"]
    output_path: Path | None = None
    error: str | None = None
```

**Services return results, never throw on individual failures.**

---

### Testing Rules

**Directory Structure (mirrors src/):**
```
tests/
├── conftest.py          # Shared fixtures, mock factories
├── cli/
│   └── test_sync_cmd.py
├── core/
│   └── test_checksum.py
├── services/
│   └── test_sync_service.py
├── adapters/
│   └── test_filesystem.py
├── integration/
│   └── test_full_sync.py
└── fixtures/
    └── sample_files/    # Real test PDFs, XLSX
```

**File Naming:** `test_{module}.py`

**Function Naming:** `test_{behavior}_when_{condition}` or `test_{behavior}`
```python
# ✓ Good
def test_sync_skips_unchanged_files():
def test_checksum_handles_large_files():
def test_sync_fails_when_manifest_corrupt():

# ✗ Bad
def test_sync():           # Too vague
def test1():               # Meaningless
def sync_test():           # Wrong prefix
```

**Structure (Arrange-Act-Assert):**
```python
def test_sync_skips_unchanged_files():
    # Arrange
    mock_fs = MockFileSystem(files={"doc.pdf": b"content"})
    mock_manifest = MockManifest(existing={"doc.pdf": "abc123"})
    service = SyncService(mock_fs, MockProcessor(), mock_manifest)
    
    # Act
    result = service.execute(Path("raw_inbox"))
    
    # Assert
    assert result.skip_count == 1
    assert result.success_count == 0
```

**Integration Tests:** Use real Docling, run via `./scripts/ci-integration.sh`

**🚨 DEV AGENT TESTING PROTOCOL (CRITICAL):**
```
NEVER run nest init|sync|status commands directly in the repository
✗ FORBIDDEN: nest init "TestProject"  (pollutes repo with .nest_manifest.json)
✗ FORBIDDEN: nest sync                (creates _nest_context/ artifacts in repo)

✓ CORRECT: pytest tests/e2e/test_init_e2e.py   (runs in isolated temp workspace)
✓ CORRECT: pytest -m e2e                        (E2E tests auto-cleanup)
```

**Rationale:**
- E2E tests use isolated temp directories (auto-created/auto-cleaned)
- Running nest commands in repo root creates test artifacts that pollute git
- All CLI functionality MUST be verified via E2E tests
- If debugging requires manual inspection, use `/tmp/nest-debug-{timestamp}` and DELETE after

**E2E Test Fixtures (conftest.py):**
- `e2e_workspace`: Creates isolated temp directory for each test
- Automatically cleans up after test completion
- Zero risk of repo pollution

---

### Git Workflow

**🚨 CRITICAL: Create branch BEFORE any code changes:**
```bash
git checkout main && git pull origin main
git checkout -b feat/{story-key}-{short-description}
```

**Branch Prefixes:**
- `feat/` — New features
- `fix/` — Bug fixes
- `chore/` — Maintenance, deps, CI
- `refactor/` — Code restructure
- `test/` — Test additions
- `docs/` — Documentation

**Conventional Commits (MANDATORY):**
```
<type>(<scope>): <description>

feat(sync): add --dry-run flag for preview mode
fix(init): handle spaces in project names
chore(deps): bump docling to 2.1.0
feat(agent)!: change agent file format    ← Breaking change
```

**Types → Semver:**
| Type | Bump |
|------|------|
| `feat` | MINOR |
| `fix`, `perf` | PATCH |
| `!` or `BREAKING CHANGE` | MAJOR |
| `docs`, `chore`, `refactor`, `test` | None |

**Commit Rules:**
1. Scope = module name (sync, init, doctor, agent, manifest)
2. Imperative mood ("add" not "added")
3. Run `./scripts/ci-lint.sh` before committing

---

### CI Validation

**Before EVERY commit, run:**
```bash
./scripts/ci-lint.sh && ./scripts/ci-typecheck.sh && ./scripts/ci-test.sh
```

**CI Scripts:**
- `ci-lint.sh` — Ruff check + format
- `ci-typecheck.sh` — Pyright strict
- `ci-test.sh` — pytest with coverage
- `ci-integration.sh` — Docling processing tests

---

### Path Handling

**ALWAYS use `pathlib.Path` — NEVER string concatenation:**
```python
# ✓ Correct
from pathlib import Path

def get_output_path(source: Path, raw_dir: Path, processed_dir: Path) -> Path:
    relative = source.relative_to(raw_dir)
    return processed_dir / relative.with_suffix(".md")

# ✗ NEVER
import os
output = input_path.replace(".pdf", ".md")
path = os.path.join(dir1, dir2, file)
```

**Path Rules:**
- Use `/` operator for joining: `base / "subdir" / "file.txt"`
- Resolve at CLI entry: `path.resolve()`
- Store relative paths in manifest (portability)
- Convert to absolute when performing I/O
- Use `.exists()`, `.is_file()`, `.is_dir()` for checks

---

### Project Paths

**User-created project structure:**
```
{project}/
├── .nest_manifest.json      # Sync state tracking
├── .nest_errors.log         # Error diagnostics
├── raw_inbox/               # Source documents (PDF, XLSX, PPTX)
├── processed_context/       # Converted markdown (mirrors raw_inbox/)
│   └── 00_MASTER_INDEX.md   # Auto-generated index
└── .github/copilot-instructions.md  # VS Code agent file
```

**Global paths:**
- `~/.config/nest/config.toml` — Install source, version
- `~/.cache/docling/` — Docling ML models (~1.5-2GB)

---

## Anti-Patterns (NEVER DO)

**Code Style:**
```python
# ✗ Mixed naming
class syncService:          # Should be PascalCase
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

# ✗ Vague errors
raise Exception("Error")    # What? Why? What to do?

# ✗ Missing type hints
def process(path):
    return result
```

**Architecture:**
- ❌ Importing implementations instead of protocols in services
- ❌ I/O operations in `core/` layer
- ❌ Global state or module-level singletons
- ❌ Direct Docling imports outside `adapters/docling_processor.py`
- ❌ Hard-coded paths instead of injected configuration

**Git:**
- ❌ Committing directly to `main` without feature branch
- ❌ Non-conventional commit messages
- ❌ Pushing without running CI scripts locally

**Output:**
- ❌ Using `logging` for user-facing messages
- ❌ Using Rich/print for error log entries
- ❌ Error messages without actionable guidance

---

## Usage Guidelines

**For AI Agents:**
- Read this file BEFORE implementing any code
- Follow ALL rules exactly as documented
- When in doubt, prefer the more restrictive option
- Run CI scripts before every commit

**For Humans:**
- Keep this file lean and focused on agent needs
- Update when technology stack changes
- Review quarterly for outdated rules

---

_Last Updated: 2026-01-12_


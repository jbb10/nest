# Story 4.1: User Config Management

Status: done

## Story

As a **user**,
I want **Nest to remember where it was installed from**,
So that **I never have to re-enter the git URL for updates**.

## Business Context

This is the **FIRST** story in Epic 4 (Tool Updates & Maintenance). It establishes the user configuration infrastructure that all subsequent Epic 4 stories depend on:
- **Story 4.2:** Version Discovery & Comparison — reads `source` from config
- **Story 4.3:** Interactive Version Selection — reads/updates `installed_version`
- **Story 4.4:** Agent Template Migration Check — reads config state
- **Story 4.5:** Update Command CLI Integration — depends on `UserConfigAdapter`

**No existing code touches user config** — this is a greenfield story that creates the `UserConfig` Pydantic model, `UserConfigProtocol`, and `UserConfigAdapter` from scratch.

**Functional Requirements Covered:** FR15 (partial — config persistence for self-update), FR16 (partial — stores version for migration checks)

**Architecture Reference:** [Source: architecture.md § User Configuration Storage, § Configuration Management]

## Acceptance Criteria

### AC1: Config Created Automatically on First Run

**Given** first run of any `nest` command
**When** user config at `~/.config/nest/config.toml` doesn't exist
**Then** the file is created with:
```toml
[install]
source = "git+https://github.com/jbb10/nest"
installed_version = "0.1.3"
installed_at = "2026-02-12T10:30:00Z"
```
**And** the `~/.config/nest/` directory is created if missing

### AC2: Config Loaded Successfully

**Given** user config exists at `~/.config/nest/config.toml`
**When** `UserConfigAdapter.load()` is called
**Then** it returns a validated `UserConfig` Pydantic model
**And** all fields are properly typed (source: `str`, installed_version: `str`, installed_at: `datetime`)

### AC3: Config Returns None When Missing

**Given** `UserConfigAdapter`
**When** loading config and file doesn't exist
**Then** it returns `None` (NOT an error)

### AC4: Corrupt Config Raises ConfigError

**Given** config file is corrupt or invalid TOML
**When** loading fails
**Then** a `ConfigError` is raised with clear message
**And** message suggests: "User config is corrupt. Delete ~/.config/nest/config.toml and re-run any nest command to regenerate."

### AC5: Config Updated After Successful Operation

**Given** user config exists
**When** `UserConfigAdapter.save()` is called with updated `UserConfig`
**Then** `installed_version` and `installed_at` are updated in file
**And** all other fields are preserved

### AC6: Directory Auto-Creation on Save

**Given** `~/.config/nest/` directory doesn't exist
**When** saving config
**Then** directory is created automatically (including parents)

### AC7: Config File Uses Correct Platform Path

**Given** any platform (macOS/Linux/Windows)
**When** determining config path
**Then** uses `~/.config/nest/config.toml` (expands `~` correctly per platform)

## Tasks / Subtasks

- [x] **Task 1: Add UserConfig Pydantic Model** (AC: #1, #2)
  - [x] 1.1 Add `InstallConfig` model with fields: `source`, `installed_version`, `installed_at`
  - [x] 1.2 Add `UserConfig` model with `install: InstallConfig`
  - [x] 1.3 Add to `src/nest/core/models.py` alongside existing models
- [x] **Task 2: Add UserConfigProtocol** (AC: #2, #3, #4, #5)
  - [x] 2.1 Add `UserConfigProtocol` to `src/nest/adapters/protocols.py`
  - [x] 2.2 Methods: `load() -> UserConfig | None`, `save(config: UserConfig) -> None`, `config_path() -> Path`
- [x] **Task 3: Implement UserConfigAdapter** (AC: #1–#7)
  - [x] 3.1 Create `src/nest/adapters/user_config.py`
  - [x] 3.2 Implement TOML reading with `tomllib` (3.11+) / `tomli` (3.10 fallback)
  - [x] 3.3 Implement TOML writing (simple manual formatting — schema is tiny and flat)
  - [x] 3.4 Handle `ConfigError` on corrupt/invalid TOML
  - [x] 3.5 Handle directory auto-creation on save
  - [x] 3.6 Handle `None` return when file doesn't exist
- [x] **Task 4: Add Default Config Factory** (AC: #1)
  - [x] 4.1 Add `create_default_config()` function that builds `UserConfig` with current Nest version
  - [x] 4.2 Default source: `"git+https://github.com/jbb10/nest"`
  - [x] 4.3 Current version from `nest.__version__`
- [x] **Task 5: Add TOML Compatibility Dependency** (AC: #1–#7)
  - [x] 5.1 Add `tomli>=2.0.0; python_version < "3.11"` to `pyproject.toml` dependencies
- [x] **Task 6: Write Unit Tests** (AC: #1–#7)
  - [x] 6.1 Create `tests/adapters/test_user_config.py`
  - [x] 6.2 Test loading valid config
  - [x] 6.3 Test loading returns None when missing
  - [x] 6.4 Test saving creates directories
  - [x] 6.5 Test saving updates fields
  - [x] 6.6 Test corrupt TOML raises ConfigError
  - [x] 6.7 Test config_path returns correct path
  - [x] 6.8 Test default config factory values
- [x] **Task 7: Run CI Validation**
  - [x] 7.1 Lint passes (ruff check — 0 new issues)
  - [x] 7.2 Typecheck passes (pyright — 0 errors)
  - [x] 7.3 Tests pass (464 passed, 0 failed)

## Dev Notes

### Architecture Patterns to Follow

**Layer:** This story lives entirely in the **adapters** layer (with models in **core**).

**Composition Root:** `UserConfigAdapter` will be instantiated in `cli/update_cmd.py` (Story 4.5) and potentially in `cli/main.py` for auto-creation on first run. For this story, no CLI wiring is required — the adapter and protocol are standalone.

**Protocol-Based DI Pattern:**
```python
# adapters/protocols.py — Add to existing file
@runtime_checkable
class UserConfigProtocol(Protocol):
    def load(self) -> UserConfig | None: ...
    def save(self, config: UserConfig) -> None: ...
    def config_path(self) -> Path: ...
```

**Services will depend on `UserConfigProtocol`, never `UserConfigAdapter` directly.**

### Pydantic Model Design

```python
# core/models.py — Add alongside existing models

class InstallConfig(BaseModel):
    """Installation source and version tracking.

    Attributes:
        source: Git URL for `uv tool install` (e.g., "git+https://github.com/jbb10/nest").
        installed_version: Currently installed Nest version string.
        installed_at: Timestamp when this version was installed/updated.
    """
    source: str
    installed_version: str
    installed_at: datetime


class UserConfig(BaseModel):
    """User-level configuration stored at ~/.config/nest/config.toml.

    Attributes:
        install: Installation source and version tracking.
    """
    install: InstallConfig
```

### TOML Read/Write Strategy

**Reading (cross-version compatible):**
```python
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # Backport for 3.10
```

**Writing (manual formatting — schema is tiny, no library needed):**
```python
def _serialize_toml(config: UserConfig) -> str:
    """Serialize UserConfig to TOML string.

    Manual formatting because the schema is flat and simple.
    Avoids adding a write-dependency (tomli_w) for 3 fields.
    """
    return (
        "[install]\n"
        f'source = "{config.install.source}"\n'
        f'installed_version = "{config.install.installed_version}"\n'
        f'installed_at = "{config.install.installed_at.isoformat()}"\n'
    )
```

**Why manual write:** The config schema has exactly 3 fields under one section. Adding `tomli_w` as a dependency for this is over-engineering. If the schema grows in future stories, this can be revisited.

### Config Path Resolution

```python
CONFIG_DIR = Path.home() / ".config" / "nest"
CONFIG_FILE = "config.toml"
```

**Cross-platform:** `Path.home()` correctly resolves on macOS, Linux, and Windows. The `~/.config/` convention is specified by the PRD and architecture — on Windows, `Path.home()` returns `C:\Users\<name>` so the full path becomes `C:\Users\<name>\.config\nest\config.toml`.

### Default Config Values

```python
from nest import __version__

DEFAULT_INSTALL_SOURCE = "git+https://github.com/jbb10/nest"

def create_default_config() -> UserConfig:
    return UserConfig(
        install=InstallConfig(
            source=DEFAULT_INSTALL_SOURCE,
            installed_version=__version__,
            installed_at=datetime.now(tz=timezone.utc),
        )
    )
```

### Error Handling Pattern

Follow the existing `ConfigError` from `core/exceptions.py`:
```python
from nest.core.exceptions import ConfigError

# On corrupt TOML:
raise ConfigError(
    "User config is corrupt. Delete ~/.config/nest/config.toml "
    "and re-run any nest command to regenerate."
)
```

### Dependency Addition

Add to `pyproject.toml` dependencies:
```toml
"tomli>=2.0.0; python_version < '3.11'",
```

This is a **conditional dependency** — only installed on Python 3.10. Python 3.11+ uses the built-in `tomllib`.

### Testing Strategy

**All tests use `tmp_path` fixture** — never touch real `~/.config/nest/`:
```python
def test_load_returns_none_when_missing(tmp_path: Path) -> None:
    adapter = UserConfigAdapter(config_dir=tmp_path)
    result = adapter.load()
    assert result is None

def test_save_creates_directory(tmp_path: Path) -> None:
    config_dir = tmp_path / "nested" / "dir"
    adapter = UserConfigAdapter(config_dir=config_dir)
    adapter.save(create_default_config())
    assert (config_dir / "config.toml").exists()
```

**Constructor injection for testability:** The `UserConfigAdapter` should accept an optional `config_dir: Path` parameter that overrides the default `~/.config/nest/` for testing.

### Existing Patterns to Reuse

| Pattern | Source | How to Reuse |
|---------|--------|-------------|
| Protocol definition | `adapters/protocols.py` | Follow `ManifestProtocol` format with `@runtime_checkable` |
| Pydantic model | `core/models.py` | Follow `Manifest` / `FileEntry` model patterns |
| Error raising | `core/exceptions.py` | Use existing `ConfigError` class |
| Test structure | `tests/adapters/test_manifest.py` | Follow arrange-act-assert with `tmp_path` |

### Files to Create

| File | Purpose |
|------|---------|
| `src/nest/adapters/user_config.py` | `UserConfigAdapter` implementation |
| `tests/adapters/test_user_config.py` | Unit tests for adapter |

### Files to Modify

| File | Change |
|------|--------|
| `src/nest/core/models.py` | Add `InstallConfig` and `UserConfig` Pydantic models |
| `src/nest/adapters/protocols.py` | Add `UserConfigProtocol` |
| `pyproject.toml` | Add `tomli` conditional dependency |

### Files NOT to Touch

- `cli/main.py` — CLI wiring happens in Story 4.5
- `services/` — No service uses UserConfig yet (Story 4.2+ will)
- `ui/` — No UI display needed for this story

### Project Structure Notes

- Adapter location `src/nest/adapters/user_config.py` matches architecture specification exactly
- Protocol added to existing `protocols.py` (not a separate file) — follows established pattern
- Model in `core/models.py` follows existing `Manifest`/`FileEntry` pattern
- Test location `tests/adapters/test_user_config.py` mirrors source structure

### Git Workflow

```bash
git checkout main && git pull origin main
git checkout -b feat/4-1-user-config-management
# ... implement ...
# Run: ./scripts/ci-lint.sh && ./scripts/ci-typecheck.sh && ./scripts/ci-test.sh
```

### References

- [Source: architecture.md § User Configuration Storage] — Config schema, location, behavior
- [Source: architecture.md § Configuration Management] — Pydantic models for config
- [Source: architecture.md § Dependency Injection] — Manual constructor injection pattern
- [Source: architecture.md § Protocol Boundaries] — `UserConfigProtocol` specification
- [Source: architecture.md § PRD Command to Module Mapping] — UpdateService uses UserConfig
- [Source: prd.md § 4.4 Command: nest update] — Update command reads/writes config
- [Source: epics.md § Story 4.1] — Acceptance criteria and BDD scenarios
- [Source: project-context.md § Architecture & DI] — Protocol-based DI rules
- [Source: project-context.md § Error Handling] — ConfigError usage
- [Source: project-context.md § Testing Rules] — Test naming, tmp_path, AAA pattern

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- pyright strict mode required `cast()` wrapper for `tomli` backport (untyped on Python 3.10 target)
- `_parse_toml()` helper isolates tomllib/tomli type-ignore comments to a single location

### Completion Notes List
- All 7 ACs covered by 16 unit tests — 100% pass
- `UserConfigAdapter` accepts `config_dir` constructor injection for testability
- Manual TOML serialization (3 fields, 1 section) — no `tomli_w` dependency needed
- `tomli` conditional dependency only installed on Python <3.11
- Full test suite: 464 passed, 0 failed
- Lint: 0 new issues (1 pre-existing E501 in test_docling_processor.py)
- Typecheck: 0 errors on all changed files

### File List

| File | Action |
|------|--------|
| `src/nest/core/models.py` | Modified — added `InstallConfig` and `UserConfig` models |
| `src/nest/adapters/protocols.py` | Modified — added `UserConfigProtocol` |
| `src/nest/adapters/user_config.py` | Created — `UserConfigAdapter`, `create_default_config()`, `_serialize_toml()`, `_parse_toml()` |
| `tests/adapters/test_user_config.py` | Created — 16 unit tests covering AC #1–#7 |
| `pyproject.toml` | Modified — added `tomli>=2.0.0; python_version < '3.11'` dependency |

# Story 4.2: Version Discovery & Comparison

Status: done

## Story

As a **user running `nest update`**,
I want **to see what versions are available and how they compare to my installed version**,
So that **I can decide whether to update and which version to target**.

## Business Context

This is the **SECOND** story in Epic 4 (Tool Updates & Maintenance). It builds directly on Story 4.1 (User Config Management) by reading `source` from the user config to determine where to query available versions.

**Downstream Dependencies:**
- **Story 4.3:** Interactive Version Selection — consumes the version list and comparison from this story
- **Story 4.5:** Update Command CLI Integration — uses `UpdateService` which orchestrates this logic

**This story creates three new components:**
1. `core/version.py` — Pure semver parsing and comparison logic (no I/O)
2. `adapters/git_client.py` — `GitClientAdapter` that queries remote tags via `git ls-remote`
3. `GitClientProtocol` added to `adapters/protocols.py`

**Functional Requirements Covered:** FR15 (partial — version discovery for self-update), FR17 (partial — displays available versions with current marked)

**Architecture References:**
- [Source: architecture.md § `nest update` Command Behavior] — Display format, flow
- [Source: architecture.md § Project Structure] — `core/version.py`, `adapters/git_client.py`
- [Source: architecture.md § Protocol Boundaries] — `GitClientProtocol` specification
- [Source: architecture.md § PRD Command to Module Mapping] — `UpdateService` uses `GitClient`

## Acceptance Criteria

### AC1: Git Remote Tag Query

**Given** a valid git remote URL (e.g., `git+https://github.com/jbjornsson/nest`)
**When** `GitClientAdapter.list_tags(remote_url)` is called
**Then** it executes `git ls-remote --tags <clean_url>` (strips `git+` prefix)
**And** returns a list of tag name strings (e.g., `["v0.1.0", "v0.1.1", "v0.1.2", "v0.1.3"]`)

### AC2: Semver Parsing

**Given** a version tag string like `"v1.2.3"` or `"1.2.3"`
**When** `parse_version(tag)` is called
**Then** it extracts major, minor, patch as integers
**And** returns a `Version` dataclass/namedtuple with those components
**And** strips the optional `v` prefix

### AC3: Version Sorting (Newest First)

**Given** a list of version strings `["v1.0.0", "v1.3.1", "v1.2.0", "v1.4.0", "v1.1.0"]`
**When** `sort_versions(versions)` is called
**Then** they are returned sorted newest-first: `["v1.4.0", "v1.3.1", "v1.2.0", "v1.1.0", "v1.0.0"]`

### AC4: Non-Semver Tags Filtered

**Given** remote tags include non-semver entries (e.g., `"latest"`, `"beta"`, `"docs-update"`)
**When** tag parsing runs
**Then** non-semver tags are silently filtered out
**And** only `v*.*.*` pattern tags are included

### AC5: Version Comparison Annotations

**Given** current installed version is `"0.1.2"`
**And** available versions are `["0.1.3", "0.1.2", "0.1.1", "0.1.0"]`
**When** `compare_versions(current, available)` runs
**Then** the result annotates each version:
- `0.1.3` → `"(latest)"`
- `0.1.2` → `"(installed)"`
- `0.1.1` → no annotation
- `0.1.0` → no annotation

### AC6: Network Error Handling

**Given** network is unavailable or git command fails
**When** `GitClientAdapter.list_tags()` raises an error
**Then** a `ConfigError` is raised with message: `"Cannot reach update server. Check your internet connection."`

### AC7: No Tags Found

**Given** remote repository has no version tags
**When** tag parsing completes
**Then** an empty list is returned
**And** the calling code can display: `"No releases found. You may be on a development version."`

### AC8: GitClientProtocol Defined

**Given** `adapters/protocols.py`
**When** `GitClientProtocol` is added
**Then** it has method: `list_tags(remote_url: str) -> list[str]`
**And** it is `@runtime_checkable`
**And** `GitClientAdapter` satisfies this protocol

## Tasks / Subtasks

- [x] **Task 1: Create `core/version.py` — Semver Parsing & Comparison** (AC: #2, #3, #4, #5)
  - [x] 1.1 Create `Version` NamedTuple with `major: int`, `minor: int`, `patch: int` fields
  - [x] 1.2 Implement `parse_version(tag: str) -> Version | None` — strips `v` prefix, returns None for non-semver
  - [x] 1.3 Implement `sort_versions(tags: list[str]) -> list[str]` — filters non-semver, sorts newest-first
  - [x] 1.4 Implement `compare_versions(current: str, available: list[str]) -> list[tuple[str, str]]` — returns `(version, annotation)` pairs
  - [x] 1.5 Add `is_newer(version_a: str, version_b: str) -> bool` helper for comparing two versions
- [x] **Task 2: Add `GitClientProtocol`** (AC: #8)
  - [x] 2.1 Add `GitClientProtocol` to `src/nest/adapters/protocols.py`
  - [x] 2.2 Method: `list_tags(remote_url: str) -> list[str]`
  - [x] 2.3 Decorate with `@runtime_checkable`
- [x] **Task 3: Implement `GitClientAdapter`** (AC: #1, #6)
  - [x] 3.1 Create `src/nest/adapters/git_client.py`
  - [x] 3.2 Implement `list_tags()` using `subprocess.run` to execute `git ls-remote --tags`
  - [x] 3.3 Parse stdout to extract tag names (strip `refs/tags/` prefix, ignore `^{}` derefs)
  - [x] 3.4 Strip `git+` prefix from source URLs before passing to git
  - [x] 3.5 Handle subprocess errors (CalledProcessError, TimeoutExpired) → raise `ConfigError`
  - [x] 3.6 Set reasonable timeout (10 seconds) for network operations
- [x] **Task 4: Write Unit Tests for `core/version.py`** (AC: #2, #3, #4, #5)
  - [x] 4.1 Create `tests/core/test_version.py`
  - [x] 4.2 Test `parse_version` with valid semver (with/without `v` prefix)
  - [x] 4.3 Test `parse_version` returns None for non-semver strings
  - [x] 4.4 Test `sort_versions` orders newest-first
  - [x] 4.5 Test `sort_versions` filters non-semver tags
  - [x] 4.6 Test `sort_versions` handles empty list
  - [x] 4.7 Test `compare_versions` annotates latest and installed correctly
  - [x] 4.8 Test `compare_versions` when current version is latest
  - [x] 4.9 Test `compare_versions` when current version not in list
  - [x] 4.10 Test `is_newer` comparison helper
- [x] **Task 5: Write Unit Tests for `GitClientAdapter`** (AC: #1, #6, #7)
  - [x] 5.1 Create `tests/adapters/test_git_client.py`
  - [x] 5.2 Test `list_tags` with mocked subprocess returning valid `ls-remote` output
  - [x] 5.3 Test `list_tags` strips `git+` prefix from URL
  - [x] 5.4 Test `list_tags` parses tags correctly (strips `refs/tags/`, ignores `^{}`)
  - [x] 5.5 Test `list_tags` returns empty list when no tags
  - [x] 5.6 Test `list_tags` raises `ConfigError` on subprocess failure
  - [x] 5.7 Test `list_tags` raises `ConfigError` on timeout
- [x] **Task 6: Run CI Validation**
  - [x] 6.1 Lint passes (ruff check — 0 new issues)
  - [x] 6.2 Typecheck passes (pyright — 0 errors)
  - [x] 6.3 All tests pass (existing + new)

## Dev Notes

### Architecture Patterns to Follow

**Layer Placement:**
- `core/version.py` → **Core layer** — pure functions, no I/O, no imports from adapters/services
- `adapters/git_client.py` → **Adapters layer** — wraps `subprocess` for git interaction
- `adapters/protocols.py` → Add `GitClientProtocol` alongside existing protocols

**Composition Root:** `GitClientAdapter` will be instantiated in `cli/update_cmd.py` (Story 4.5). For this story, no CLI wiring is needed — the adapter and core module are standalone.

**Protocol-Based DI Pattern:**
```python
# adapters/protocols.py — Add to existing file
@runtime_checkable
class GitClientProtocol(Protocol):
    def list_tags(self, remote_url: str) -> list[str]: ...
```

**Services will depend on `GitClientProtocol`, never `GitClientAdapter` directly.**

### Core Version Module Design

```python
# core/version.py — Pure business logic, no I/O

from typing import NamedTuple


class Version(NamedTuple):
    """Parsed semantic version components.

    Attributes:
        major: Major version number.
        minor: Minor version number.
        patch: Patch version number.
    """
    major: int
    minor: int
    patch: int


def parse_version(tag: str) -> Version | None:
    """Parse a version string into components.

    Handles both "v1.2.3" and "1.2.3" formats. Returns None for
    non-semver strings (e.g., "latest", "beta", "docs-update").

    Args:
        tag: Version tag string to parse.

    Returns:
        Version tuple if valid semver, None otherwise.
    """
    ...


def sort_versions(tags: list[str]) -> list[str]:
    """Sort version tags newest-first, filtering non-semver.

    Args:
        tags: Raw tag strings from git remote.

    Returns:
        Sorted version strings (without 'v' prefix), newest first.
        Non-semver tags are excluded.
    """
    ...


def compare_versions(
    current: str,
    available: list[str],
) -> list[tuple[str, str]]:
    """Annotate available versions relative to current.

    Args:
        current: Currently installed version string.
        available: Sorted list of available version strings.

    Returns:
        List of (version, annotation) tuples.
        Annotations: "(latest)" for newest, "(installed)" for current, "" otherwise.
    """
    ...


def is_newer(version_a: str, version_b: str) -> bool:
    """Check if version_a is newer than version_b.

    Args:
        version_a: First version string.
        version_b: Second version string.

    Returns:
        True if version_a > version_b.
    """
    ...
```

### GitClientAdapter Design

```python
# adapters/git_client.py

import subprocess
from nest.core.exceptions import ConfigError

GIT_TIMEOUT_SECONDS = 10


class GitClientAdapter:
    """Adapter for querying git remote tags.

    Wraps subprocess calls to `git ls-remote --tags` to discover
    available version tags from a remote repository.
    """

    def list_tags(self, remote_url: str) -> list[str]:
        """Query remote repository for version tags.

        Executes `git ls-remote --tags <url>` and parses output to
        extract tag names.

        Args:
            remote_url: Git remote URL. Handles 'git+https://...' prefix
                        by stripping the 'git+' part.

        Returns:
            List of tag name strings (e.g., ["v1.0.0", "v1.2.1"]).

        Raises:
            ConfigError: If git command fails or network is unavailable.
        """
        ...
```

### Git ls-remote Output Format

The `git ls-remote --tags` command produces output like:
```
abc123def456	refs/tags/v0.1.0
abc123def456	refs/tags/v0.1.0^{}
def789ghi012	refs/tags/v0.1.1
def789ghi012	refs/tags/v0.1.1^{}
ghi345jkl678	refs/tags/v0.1.2
ghi345jkl678	refs/tags/v0.1.2^{}
mno901pqr234	refs/tags/latest
```

**Parsing rules:**
- Split each line by tab → take second column (ref path)
- Strip `refs/tags/` prefix → left with tag name
- **Ignore entries ending with `^{}`** — these are dereferenced annotated tags
- Return all remaining tag names as raw strings (filtering happens in `core/version.py`)

### URL Cleaning

The user config stores source URLs with `git+` prefix (e.g., `git+https://github.com/jbjornsson/nest`) because `uv tool install` uses that format. The `git ls-remote` command does NOT accept the `git+` prefix, so it must be stripped:

```python
def _clean_url(remote_url: str) -> str:
    """Strip git+ prefix if present for git CLI compatibility."""
    if remote_url.startswith("git+"):
        return remote_url[4:]
    return remote_url
```

### Error Handling Pattern

Follow the existing `ConfigError` from `core/exceptions.py`:
```python
from nest.core.exceptions import ConfigError

# On subprocess failure:
raise ConfigError(
    "Cannot reach update server. Check your internet connection."
)

# On timeout:
raise ConfigError(
    "Cannot reach update server. Check your internet connection."
)
```

**Why `ConfigError` not a new exception class?** The architecture specifies `UpdateService` uses `GitClient` and `UserConfig` — both connection/config concerns. No need for a new exception type as this is a configuration/external-dependency failure, fitting `ConfigError` semantics.

### Testing Strategy

**Unit tests for `core/version.py`** — Pure functions, no mocking needed:
```python
# tests/core/test_version.py

def test_parse_version_with_v_prefix() -> None:
    result = parse_version("v1.2.3")
    assert result == Version(1, 2, 3)

def test_parse_version_without_prefix() -> None:
    result = parse_version("1.2.3")
    assert result == Version(1, 2, 3)

def test_parse_version_returns_none_for_non_semver() -> None:
    assert parse_version("latest") is None
    assert parse_version("beta") is None
    assert parse_version("v1.2") is None  # Missing patch
```

**Unit tests for `GitClientAdapter`** — Mock `subprocess.run`:
```python
# tests/adapters/test_git_client.py

from unittest.mock import patch, MagicMock

SAMPLE_LS_REMOTE = (
    "abc123\trefs/tags/v0.1.0\n"
    "abc123\trefs/tags/v0.1.0^{}\n"
    "def456\trefs/tags/v0.1.1\n"
    "def456\trefs/tags/v0.1.1^{}\n"
    "ghi789\trefs/tags/latest\n"
)

@patch("nest.adapters.git_client.subprocess.run")
def test_list_tags_parses_output(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(stdout=SAMPLE_LS_REMOTE, returncode=0)
    adapter = GitClientAdapter()
    tags = adapter.list_tags("git+https://github.com/jbjornsson/nest")
    assert "v0.1.0" in tags
    assert "v0.1.1" in tags
    assert "latest" in tags  # Filtering is done in core/version.py
    # ^{} entries should NOT appear
    assert not any(t.endswith("^{}") for t in tags)
```

### Existing Patterns to Reuse

| Pattern | Source | How to Reuse |
|---------|--------|-------------|
| Protocol definition | `adapters/protocols.py` | Follow `UserConfigProtocol` format with `@runtime_checkable` |
| Adapter constructor | `adapters/user_config.py` | Simple class, no complex init needed |
| Error raising | `core/exceptions.py` | Use existing `ConfigError` class |
| Test structure | `tests/adapters/test_user_config.py` | Follow Arrange-Act-Assert with mocked subprocess |
| Core pure functions | `core/checksum.py` | Follow pure-function pattern (no I/O in core) |
| NamedTuple model | Project conventions | Use `typing.NamedTuple` for lightweight immutable data |

### Files to Create

| File | Purpose |
|------|---------|
| `src/nest/core/version.py` | Semver parsing, sorting, comparison (pure logic) |
| `src/nest/adapters/git_client.py` | `GitClientAdapter` — wraps `git ls-remote` |
| `tests/core/test_version.py` | Unit tests for version module |
| `tests/adapters/test_git_client.py` | Unit tests for git client adapter |

### Files to Modify

| File | Change |
|------|--------|
| `src/nest/adapters/protocols.py` | Add `GitClientProtocol` |

### Files NOT to Touch

- `cli/update_cmd.py` — CLI wiring happens in Story 4.5
- `services/update_service.py` — Service orchestration happens in Story 4.3+
- `ui/` — No UI display needed for this story (display logic is Story 4.3/4.5)
- `core/models.py` — No new Pydantic models needed (NamedTuple is sufficient for Version)
- `pyproject.toml` — No new dependencies (subprocess is stdlib, git is a system dependency)

### Project Structure Notes

- `core/version.py` is specified in architecture.md § Project Structure as `core/version.py — Version comparison, semver parsing`
- `adapters/git_client.py` is specified in architecture.md § Project Structure as `adapters/git_client.py — Git tag queries for update`
- Both file locations match architecture specification exactly
- Protocol added to existing `protocols.py` (not separate file) — follows established pattern
- No `__init__.py` creation needed — `tests/core/` directory already exists

### Dependency Notes

- **No new dependencies required** — `subprocess` is Python stdlib, `git` is assumed available (same assumption as `uv` per architecture constraints)
- The `git` executable must be on PATH — this is reasonable given the project already depends on `uv` and git-based installation
- If git is not available, the `ConfigError` message guides the user

### Version String Conventions

Throughout this story, version strings may appear in two forms:
- **With prefix:** `"v1.2.3"` — as stored in git tags
- **Without prefix:** `"1.2.3"` — as stored in `config.toml` `installed_version` field

The `parse_version()` function handles both. The `sort_versions()` function returns versions **without** the `v` prefix for consistency with config storage. The `compare_versions()` function accepts the `current` param without prefix (matching config) and `available` without prefix (from `sort_versions()`).

### Previous Story Intelligence (Story 4.1)

**Learnings from Story 4.1 implementation:**
- `UserConfigAdapter` accepts `config_dir` constructor injection for testability — follow same DI pattern for `GitClientAdapter` (no constructor params needed since it wraps subprocess, but consider accepting a `timeout` param for testability)
- `_parse_toml()` wrapper was needed for pyright strict mode with `tomli` backport — may need similar `cast()` patterns when dealing with subprocess stdout typing
- Manual TOML serialization was chosen over adding `tomli_w` dependency — similarly, avoid adding unnecessary dependencies for this story
- Test structure from `test_user_config.py` uses class-based grouping by AC — follow same pattern in `test_git_client.py` and `test_version.py`
- All Story 4.1 tests pass: 464 passed, 0 failed — maintain this baseline

**Files created/modified in Story 4.1:**
- `src/nest/adapters/user_config.py` — `UserConfigAdapter`, `create_default_config()` (will be used by Story 4.3+ to read install source)
- `src/nest/core/models.py` — `InstallConfig`, `UserConfig` Pydantic models
- `src/nest/adapters/protocols.py` — `UserConfigProtocol` (pattern to follow for `GitClientProtocol`)

### Git Workflow

```bash
git checkout main && git pull origin main
git checkout -b feat/4-2-version-discovery-and-comparison
# ... implement ...
# Run: ./scripts/ci-lint.sh && ./scripts/ci-typecheck.sh && ./scripts/ci-test.sh
```

### References

- [Source: architecture.md § `nest update` Command Behavior] — Version display format, 6-step flow
- [Source: architecture.md § Project Structure] — `core/version.py`, `adapters/git_client.py` locations
- [Source: architecture.md § Protocol Boundaries] — `GitClientProtocol` specification
- [Source: architecture.md § PRD Command to Module Mapping] — `UpdateService` uses `GitClient`, `UserConfig`
- [Source: architecture.md § Dependency Injection] — Manual constructor injection, composition root
- [Source: architecture.md § Error Handling] — `ConfigError` for config/external dependency failures
- [Source: epics.md § Story 4.2] — Acceptance criteria and BDD scenarios
- [Source: epics.md § Story 4.3] — Downstream consumer of version list
- [Source: prd.md § 4.4 Command: nest update] — User-facing update flow
- [Source: project-context.md § Architecture & DI] — Protocol-based DI rules
- [Source: project-context.md § Error Handling] — ConfigError usage
- [Source: project-context.md § Testing Rules] — Test naming, AAA pattern, mock patterns
- [Source: project-context.md § Python Language Rules] — NamedTuple, type hints, imports
- [Source: 4-1-user-config-management.md § Dev Agent Record] — Previous story learnings and patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

No issues encountered during implementation.

### Completion Notes List

- **Task 1**: Created `core/version.py` with `Version` NamedTuple, `parse_version()`, `sort_versions()`, `compare_versions()`, and `is_newer()`. Pure functions, no I/O. Regex-based semver parsing handles `v` prefix and filters non-semver. `sort_versions()` returns stripped (no `v`) versions newest-first. `compare_versions()` handles edge case where current is also latest with `"(installed) (latest)"` annotation.
- **Task 2**: Added `GitClientProtocol` to `adapters/protocols.py` with `@runtime_checkable` decorator and `list_tags(remote_url: str) -> list[str]` method. Follows existing `UserConfigProtocol` pattern.
- **Task 3**: Created `adapters/git_client.py` with `GitClientAdapter` implementing `list_tags()` via `subprocess.run`. Strips `git+` prefix, parses `refs/tags/` output, ignores `^{}` deref entries. Raises `ConfigError` on `CalledProcessError`, `TimeoutExpired`, and `OSError` (git not found). Constructor accepts `timeout` param for testability (default 10s).
- **Task 4**: 35 tests in `tests/core/test_version.py` covering all AC #2/#3/#4/#5 scenarios including edge cases (empty input, prerelease tags, v-prefix handling, current-is-latest, duplicate tag dedup).
- **Task 5**: 16 tests in `tests/adapters/test_git_client.py` covering AC #1/#6/#7/#8 — mocked subprocess, protocol satisfaction, error handling, malformed line handling.
- **Task 6**: `ruff check` 0 issues, `pyright` 0 errors, 514/514 tests pass (464 existing + 50 new).

### File List

| File | Action |
|------|--------|
| `src/nest/core/version.py` | Created |
| `src/nest/adapters/git_client.py` | Created |
| `src/nest/adapters/protocols.py` | Modified — added `GitClientProtocol` |
| `tests/core/test_version.py` | Created |
| `tests/adapters/test_git_client.py` | Created |

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 | **Date:** 2026-02-12

### Findings Summary

| Severity | Count | Fixed |
|----------|-------|-------|
| HIGH | 0 | — |
| MEDIUM | 3 | 3 |
| LOW | 3 | 1 |

### Issues Found & Resolved

**M1 (FIXED): `sort_versions` duplicate version deduplication missing**
- `sort_versions(["v1.0.0", "1.0.0"])` returned `["1.0.0", "1.0.0"]`
- Added `seen` set for dedup after prefix normalization
- Added test: `test_deduplicates_normalized_versions`

**M2 (FIXED): `_parse_tags` accepted empty string tag names**
- Malformed line `"hash\trefs/tags/"` produced empty string `""` in result
- Added `if tag_name:` guard before `append`
- Added tests: `test_skips_empty_tag_names`, `test_skips_lines_without_tab`

**M3 (FIXED): Missing tests for M1 and M2 edge cases**
- 3 new tests added (1 in test_version.py, 2 in test_git_client.py)

**L1 (FIXED): `_clean_url` used manual if/slice instead of `str.removeprefix()`**
- Refactored to single-line `removeprefix("git+")` — idiomatic for Python 3.10+

**L2 (NOTED): `parse_version` accepts leading zeros**
- `"v01.2.3"` → `Version(1, 2, 3)` — not strict semver but functionally harmless
- No real git tags use leading zeros; deferred to future if needed

**L3 (NOTED): No cross-component pipeline test**
- `list_tags` → `sort_versions` → `compare_versions` pipeline not tested end-to-end
- Appropriately scoped to Story 4.3/4.5 service integration

### Verification

- 514/514 tests pass (50 from this story)
- `ruff check` — 0 issues
- `pyright` — 0 errors
- All ACs verified implemented: AC1-AC8 ✓

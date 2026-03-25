# Story 6.5: `nest config ai` Shell RC Writer

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user who wants to set up AI enrichment**,
I want **a `nest config ai` command that writes my API credentials to my shell RC file**,
So that **the keys are available as environment variables in all future terminal sessions without manual editing**.

## Business Context

This is the **fifth story in Epic 6** (Built-in AI Enrichment). Stories 6.1–6.4 created the LLM provider adapter, AI index enrichment, AI glossary generation, and parallel execution with token reporting. AI currently auto-detects credentials from `NEST_API_KEY` or `OPENAI_API_KEY` environment variables (see `create_llm_provider()` in `src/nest/adapters/llm_provider.py`).

This story adds the **`nest config ai`** subcommand that interactively prompts the user for endpoint, model, and API key, then writes them as `export` statements to the user's shell RC file (`.zshrc`, `.bashrc`, `.bash_profile`, `.profile`, or fish `config.fish`). The command uses idempotent comment-delimited blocks so re-running replaces rather than duplicates configuration.

Story 6.4's first-run discovery message already references this command: `💡 Run 'nest config ai' to change AI settings.`

**Key design principles:**
- **Shell auto-detection** — reads `$SHELL` to pick the correct RC file and syntax (bash export, fish `set -gx`)
- **Idempotent writes** — uses `# --- Nest AI Configuration ---` / `# --- End Nest AI Configuration ---` sentinel comments; replaces block on re-run
- **Interactive prompts with smart defaults** — pre-fills from existing env vars; masks API key display
- **`--remove` flag** — cleanly strips the config block from RC file
- **No project required** — this is a global user setup command, not project-scoped

## Acceptance Criteria

### AC1: Shell Detection and RC File Resolution

**Given** the user runs `nest config ai`
**When** the command starts
**Then** it detects the user's shell from the `$SHELL` environment variable
**And** resolves the correct RC file:
  - zsh → `~/.zshrc`
  - bash (macOS) → `~/.bash_profile` if it exists, else `~/.bashrc`
  - bash (Linux) → `~/.bashrc`
  - fish → `~/.config/fish/config.fish`
  - fallback → `~/.profile`

### AC2: Interactive Prompts with Smart Defaults

**Given** the shell RC file is identified
**When** the interactive prompt runs
**Then** it asks for:
  - API endpoint (with default: `https://api.openai.com/v1`)
  - Model/deployment name (with default: `gpt-4o-mini`)
  - API key (input masked with `••••` style)

**Given** AI env vars are already set in the environment (from any source)
**When** `nest config ai` runs
**Then** it shows the current values as defaults in the prompts:
```
  API endpoint [https://my-corp.openai.azure.com/]: 
  Model [gpt-4o-mini]: 
  API key [••••sk-1234]: 
```
**And** the user can press Enter to keep existing values or type new ones

### AC3: Config Block Written to RC File

**Given** the user provides all values
**When** the config is saved
**Then** the following block is written to the shell RC file:
```bash
# --- Nest AI Configuration (managed by `nest config ai`) ---
export NEST_BASE_URL="https://..."
export NEST_TEXT_MODEL="gpt-4o-mini"
export NEST_API_KEY="sk-..."
# --- End Nest AI Configuration ---
```
**And** a success message is shown: `✓ Added to ~/.zshrc`
**And** a reminder is shown: `⚠ Run 'source ~/.zshrc' or open a new terminal to activate.`

### AC4: Idempotent Block Replacement

**Given** the Nest AI config block already exists in the RC file
**When** `nest config ai` runs again
**Then** the existing block is replaced (not duplicated)
**And** all other content in the RC file is preserved

### AC5: RC File Creation

**Given** the RC file does not exist
**When** `nest config ai` runs
**Then** the file is created with the config block
**And** the parent directory is created if needed (e.g., `~/.config/fish/`)

### AC6: Remove Configuration

**Given** the user wants to remove AI configuration
**When** running `nest config ai --remove`
**Then** the Nest AI config block is removed from the RC file
**And** all other content is preserved
**And** a message confirms: `✓ AI configuration removed from ~/.zshrc`

**Given** `--remove` is run but no config block exists
**When** the command completes
**Then** a message is shown: `• No Nest AI configuration found in ~/.zshrc`

### AC7: Fish Shell Compatibility

**Given** fish shell is detected
**When** config is written
**Then** fish-compatible syntax is used:
```fish
# --- Nest AI Configuration (managed by `nest config ai`) ---
set -gx NEST_BASE_URL "https://..."
set -gx NEST_TEXT_MODEL "gpt-4o-mini"
set -gx NEST_API_KEY "sk-..."
# --- End Nest AI Configuration ---
```

### AC8: All Tests Pass

**Given** all unit tests
**When** the changes are complete
**Then** RC file detection is tested for all shell types
**And** idempotent write/replace is tested
**And** fish syntax generation is tested
**And** `--remove` is tested
**And** all tests pass with no regressions

## Tasks / Subtasks

### Task 1: Create Shell RC Service (`src/nest/services/shell_rc_service.py`) (AC: 1, 3, 4, 5, 7)

- [x] 1.1: Create `src/nest/services/shell_rc_service.py` with `ShellRCService` class
- [x] 1.2: Add `detect_shell()` method that reads `$SHELL` env var and returns shell type:
  ```python
  def detect_shell(self) -> str:
      """Detect current shell from $SHELL environment variable.

      Returns:
          Shell name: "zsh", "bash", "fish", or "unknown".
      """
      shell_path = os.environ.get("SHELL", "")
      shell_name = Path(shell_path).name if shell_path else ""
      if shell_name in ("zsh", "bash", "fish"):
          return shell_name
      return "unknown"
  ```
- [x] 1.3: Add `resolve_rc_path(shell: str)` method that returns the correct RC file path:
  ```python
  def resolve_rc_path(self, shell: str) -> Path:
      """Resolve the correct RC file path for the given shell.

      Args:
          shell: Shell name from detect_shell().

      Returns:
          Path to the shell RC file.
      """
      home = Path.home()
      if shell == "zsh":
          return home / ".zshrc"
      if shell == "bash":
          if sys.platform == "darwin":
              bash_profile = home / ".bash_profile"
              if bash_profile.exists():
                  return bash_profile
          return home / ".bashrc"
      if shell == "fish":
          return home / ".config" / "fish" / "config.fish"
      # fallback
      return home / ".profile"
  ```
- [x] 1.4: Add `BLOCK_START` and `BLOCK_END` constants:
  ```python
  BLOCK_START = '# --- Nest AI Configuration (managed by `nest config ai`) ---'
  BLOCK_END = '# --- End Nest AI Configuration ---'
  ```
- [x] 1.5: Add `generate_config_block(endpoint, model, api_key, shell)` method:
  ```python
  def generate_config_block(
      self,
      endpoint: str,
      model: str,
      api_key: str,
      shell: str,
  ) -> str:
      """Generate the shell config block with env var exports.

      Args:
          endpoint: API endpoint URL.
          model: Model/deployment name.
          api_key: API key value.
          shell: Shell type for syntax selection.

      Returns:
          Complete config block string including sentinel comments.
      """
      if shell == "fish":
          lines = [
              BLOCK_START,
              f'set -gx NEST_BASE_URL "{endpoint}"',
              f'set -gx NEST_TEXT_MODEL "{model}"',
              f'set -gx NEST_API_KEY "{api_key}"',
              BLOCK_END,
          ]
      else:
          lines = [
              BLOCK_START,
              f'export NEST_BASE_URL="{endpoint}"',
              f'export NEST_TEXT_MODEL="{model}"',
              f'export NEST_API_KEY="{api_key}"',
              BLOCK_END,
          ]
      return "\n".join(lines) + "\n"
  ```
- [x] 1.6: Add `write_config(rc_path, endpoint, model, api_key, shell)` method that handles both create and idempotent replace:
  ```python
  def write_config(
      self,
      rc_path: Path,
      endpoint: str,
      model: str,
      api_key: str,
      shell: str,
  ) -> None:
      """Write or replace the Nest AI config block in the RC file.

      Creates the file and parent directories if they don't exist.
      If a config block already exists, replaces it in-place.
      If no block exists, appends to end of file.

      Args:
          rc_path: Path to the shell RC file.
          endpoint: API endpoint URL.
          model: Model/deployment name.
          api_key: API key value.
          shell: Shell type for syntax selection.
      """
      block = self.generate_config_block(endpoint, model, api_key, shell)

      if not rc_path.exists():
          rc_path.parent.mkdir(parents=True, exist_ok=True)
          rc_path.write_text(block, encoding="utf-8")
          return

      content = rc_path.read_text(encoding="utf-8")
      new_content = self._replace_or_append_block(content, block)
      rc_path.write_text(new_content, encoding="utf-8")
  ```
- [x] 1.7: Add `_replace_or_append_block(content, block)` private method:
  ```python
  def _replace_or_append_block(self, content: str, block: str) -> str:
      """Replace existing config block or append new one.

      Args:
          content: Current file content.
          block: New config block to insert.

      Returns:
          Updated file content.
      """
      start_idx = content.find(BLOCK_START)
      end_idx = content.find(BLOCK_END)

      if start_idx != -1 and end_idx != -1:
          # Replace existing block (include the end marker + newline)
          end_of_block = end_idx + len(BLOCK_END)
          # Consume trailing newline if present
          if end_of_block < len(content) and content[end_of_block] == "\n":
              end_of_block += 1
          return content[:start_idx] + block + content[end_of_block:]

      # Append — ensure preceding newline
      if content and not content.endswith("\n"):
          content += "\n"
      return content + "\n" + block
  ```
- [x] 1.8: Add `remove_config(rc_path)` method that returns whether a block was found and removed:
  ```python
  def remove_config(self, rc_path: Path) -> bool:
      """Remove the Nest AI config block from the RC file.

      Args:
          rc_path: Path to the shell RC file.

      Returns:
          True if a block was found and removed, False if no block existed.
      """
      if not rc_path.exists():
          return False

      content = rc_path.read_text(encoding="utf-8")
      start_idx = content.find(BLOCK_START)
      end_idx = content.find(BLOCK_END)

      if start_idx == -1 or end_idx == -1:
          return False

      end_of_block = end_idx + len(BLOCK_END)
      if end_of_block < len(content) and content[end_of_block] == "\n":
          end_of_block += 1
      # Also remove preceding blank line if present
      if start_idx > 0 and content[start_idx - 1] == "\n":
          start_idx -= 1

      new_content = content[:start_idx] + content[end_of_block:]
      rc_path.write_text(new_content, encoding="utf-8")
      return True
  ```

### Task 2: Create Config CLI Command (`src/nest/cli/config_cmd.py`) (AC: 1, 2, 3, 6)

- [x] 2.1: Create `src/nest/cli/config_cmd.py` with a Typer sub-app for `config`:
  ```python
  """Config command for nest CLI.

  Handles the `nest config ai` subcommand for AI credential management.
  """

  import os
  from typing import Annotated

  import typer

  from nest.services.shell_rc_service import ShellRCService
  from nest.ui.messages import error, get_console, info, success, warning

  config_app = typer.Typer()
  ```
- [x] 2.2: Add `ai_command()` function registered as `config_app.command(name="ai")`:
  ```python
  @config_app.command(name="ai")
  def ai_command(
      remove: Annotated[
          bool,
          typer.Option(
              "--remove",
              help="Remove Nest AI configuration from shell RC file",
          ),
      ] = False,
  ) -> None:
      """Configure AI enrichment by writing API credentials to your shell RC file.

      Interactively prompts for API endpoint, model name, and API key,
      then writes them as environment variable exports to your shell RC file
      (e.g., ~/.zshrc, ~/.bashrc, ~/.config/fish/config.fish).

      Use --remove to remove the configuration block.

      Examples:
          nest config ai
          nest config ai --remove
      """
      console = get_console()
      service = ShellRCService()

      # Detect shell and RC file
      shell = service.detect_shell()
      rc_path = service.resolve_rc_path(shell)

      if remove:
          removed = service.remove_config(rc_path)
          if removed:
              success(f"AI configuration removed from {_display_path(rc_path)}")
          else:
              info(f"No Nest AI configuration found in {_display_path(rc_path)}")
          return

      # Show detected shell info
      console.print(f"  Shell: {shell}")
      console.print(f"  RC file: {_display_path(rc_path)}")
      console.print()

      # Prompt with smart defaults from existing env vars
      current_endpoint = (
          os.environ.get("NEST_BASE_URL")
          or os.environ.get("OPENAI_BASE_URL")
          or "https://api.openai.com/v1"
      )
      current_model = (
          os.environ.get("NEST_TEXT_MODEL")
          or os.environ.get("OPENAI_MODEL")
          or "gpt-4o-mini"
      )
      current_key = os.environ.get("NEST_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""

      endpoint = typer.prompt("  API endpoint", default=current_endpoint)
      model = typer.prompt("  Model", default=current_model)

      # Mask default display for API key
      key_display = _mask_key(current_key) if current_key else ""
      if current_key:
          raw_key = typer.prompt(f"  API key [{key_display}]", default="", show_default=False)
          api_key = raw_key if raw_key else current_key
      else:
          api_key = typer.prompt("  API key", hide_input=True)

      # Write config
      service.write_config(rc_path, endpoint, model, api_key, shell)

      console.print()
      success(f"Added to {_display_path(rc_path)}")
      warning(f"Run 'source {_display_path(rc_path)}' or open a new terminal to activate.")
  ```
- [x] 2.3: Add `_mask_key(key)` helper function:
  ```python
  def _mask_key(key: str) -> str:
      """Mask API key for display, showing last 4 characters.

      Args:
          key: Full API key string.

      Returns:
          Masked key like "••••sk-1234".
      """
      if len(key) <= 4:
          return "••••"
      return "••••" + key[-4:]
  ```
- [x] 2.4: Add `_display_path(path)` helper function:
  ```python
  def _display_path(path: "Path") -> str:
      """Display path with ~ for home directory.

      Args:
          path: Absolute path to display.

      Returns:
          Path string with ~ substituted for home directory.
      """
      from pathlib import Path as _Path

      home = _Path.home()
      try:
          return "~/" + str(path.relative_to(home))
      except ValueError:
          return str(path)
  ```

### Task 3: Register Config Subcommand in CLI Main (`src/nest/cli/main.py`) (AC: all)

- [x] 3.1: Import `config_app` from `config_cmd` and register as Typer sub-app:
  ```python
  from nest.cli.config_cmd import config_app

  app.add_typer(config_app, name="config")
  ```

### Task 4: Unit Tests for `ShellRCService` (`tests/services/test_shell_rc_service.py`) (AC: 1, 3, 4, 5, 6, 7, 8)

- [x] 4.1: Create `tests/services/test_shell_rc_service.py` with test classes:

  **Shell detection tests:**
  - `test_detect_shell_zsh()` — `$SHELL=/bin/zsh` → returns `"zsh"`
  - `test_detect_shell_bash()` — `$SHELL=/bin/bash` → returns `"bash"`
  - `test_detect_shell_fish()` — `$SHELL=/usr/local/bin/fish` → returns `"fish"`
  - `test_detect_shell_unknown()` — `$SHELL=/bin/csh` → returns `"unknown"`
  - `test_detect_shell_unset()` — `$SHELL` not set → returns `"unknown"`

  **RC path resolution tests:**
  - `test_resolve_rc_path_zsh()` — returns `~/.zshrc`
  - `test_resolve_rc_path_bash_linux()` — Linux → returns `~/.bashrc`
  - `test_resolve_rc_path_bash_macos_with_bash_profile(tmp_path)` — macOS + `.bash_profile` exists → returns `.bash_profile`
  - `test_resolve_rc_path_bash_macos_without_bash_profile()` — macOS + no `.bash_profile` → returns `~/.bashrc`
  - `test_resolve_rc_path_fish()` — returns `~/.config/fish/config.fish`
  - `test_resolve_rc_path_unknown()` — returns `~/.profile`

  **Config block generation tests:**
  - `test_generate_config_block_bash()` — uses `export VAR="val"` syntax
  - `test_generate_config_block_zsh()` — uses `export VAR="val"` syntax (same as bash)
  - `test_generate_config_block_fish()` — uses `set -gx VAR "val"` syntax
  - `test_generate_config_block_contains_all_vars()` — block contains `NEST_BASE_URL`, `NEST_TEXT_MODEL`, `NEST_API_KEY`
  - `test_generate_config_block_has_sentinel_comments()` — block starts with `BLOCK_START` and ends with `BLOCK_END`

  **Write config tests (using `tmp_path`):**
  - `test_write_config_creates_new_file()` — RC file doesn't exist → created with block
  - `test_write_config_creates_parent_dirs()` — parent dirs created (e.g., fish `~/.config/fish/`)
  - `test_write_config_appends_to_existing()` — existing RC content preserved, block appended
  - `test_write_config_replaces_existing_block()` — re-run replaces block, no duplication
  - `test_write_config_preserves_surrounding_content()` — content before and after block intact after replace
  - `test_write_config_idempotent_triple_run()` — run 3 times → only one block exists

  **Remove config tests (using `tmp_path`):**
  - `test_remove_config_removes_block()` — block removed, surrounding content preserved
  - `test_remove_config_returns_true_when_found()` — returns `True` when block existed
  - `test_remove_config_returns_false_when_not_found()` — returns `False` when no block
  - `test_remove_config_no_file()` — returns `False` when RC file doesn't exist
  - `test_remove_config_preserves_other_content()` — lines before/after block remain intact

### Task 5: Unit Tests for Config CLI Command (`tests/cli/test_config_cmd.py`) (AC: 2, 6, 8)

- [x] 5.1: Create `tests/cli/test_config_cmd.py` with test classes:

  **Help tests:**
  - `test_config_ai_help_shows_usage()` — `nest config ai --help` displays help text
  - `test_config_help_shows_ai_subcommand()` — `nest config --help` lists `ai` subcommand

  **Remove flag tests:**
  - `test_config_ai_remove_flag_accepted()` — `nest config ai --remove` is parsed correctly

  **Integration sanity (CliRunner):**
  - `test_config_ai_displays_shell_info()` — command outputs detected shell and RC file path (using mocked service + input)

### Task 6: Run Full Test Suite (AC: 8)

- [x] 6.1: Run `pytest -m "not e2e"` — all tests pass (803 passed, 54 deselected)
- [x] 6.2: Run `make lint` — clean (Ruff)
- [x] 6.3: Run `make typecheck` — clean (Pyright strict mode, 0 errors)

## Dev Notes

### Architecture Compliance

- **Service layer**: `ShellRCService` encapsulates all RC file I/O logic — pure service, no CLI coupling. Methods are deterministic given inputs (except `detect_shell()` which reads `$SHELL`).
- **CLI layer**: `config_cmd.py` handles user interaction (prompts, display) and calls the service. This follows the established pattern where `sync_cmd.py` handles display and delegates to `SyncService`.
- **Composition root**: `main.py` registers the `config` Typer sub-app. This is a new pattern (sub-app vs flat command) because `nest config ai` is a subcommand — Typer `add_typer()` is the correct mechanism.
- **No protocol needed**: `ShellRCService` has no external dependencies that need mocking. It reads/writes files directly (like `UserConfigAdapter`). Tests use `tmp_path` for isolation.
- **Global command**: Unlike `sync`/`doctor`/`status`, this command does NOT require being inside a Nest project. It operates on the user's home directory shell RC files. No `manifest_path.exists()` check needed.

### Critical Implementation Details

**Typer Sub-App Registration:**

Nest currently registers all commands flat on `app`. The `nest config ai` command introduces the first subcommand level. Typer handles this via `add_typer()`:

```python
# Current pattern (flat):
app.command(name="sync")(sync_command)

# New pattern (subcommand):
from nest.cli.config_cmd import config_app
app.add_typer(config_app, name="config")
```

This gives `nest config ai`, `nest config --help`, etc. If future config subcommands are needed (`nest config show`, etc.), they can be added to `config_app`.

**Shell Detection Logic:**

The `$SHELL` env var contains the user's login shell path (e.g., `/bin/zsh`, `/usr/local/bin/fish`). `Path(shell_path).name` extracts just the shell name. This is standard Unix — works on macOS and Linux. On Windows (not currently supported), `$SHELL` is typically not set, so fallback to `~/.profile`.

**Bash RC File Selection (macOS vs Linux):**

macOS bash uses `~/.bash_profile` for login shells (Terminal.app opens login shells). Linux bash uses `~/.bashrc` for interactive shells. The logic:
1. If macOS (`sys.platform == "darwin"`): prefer `~/.bash_profile` if it exists, else `~/.bashrc`
2. If Linux: use `~/.bashrc`

This matches the convention that users on macOS with bash have typically been configuring `~/.bash_profile`.

**Idempotent Block Replacement Algorithm:**

```
1. Read RC file content
2. Search for BLOCK_START marker
3. Search for BLOCK_END marker
4. If both found:
   a. Calculate exact character range (start_idx to end_of_block including trailing newline)
   b. Replace that range with new block
5. If not found:
   a. Append block to end of file (with preceding blank line for readability)
6. Write complete file back
```

This is simpler and more robust than regex-based replacement. The sentinel comments are unique enough to avoid false matches in user RC files.

**API Key Masking in Prompts:**

When existing env vars are detected, the API key is displayed masked: `••••sk-1234` (showing last 4 chars). If the user presses Enter without typing, the existing key is kept. If they type a new key, it replaces the old one. Typer's `prompt()` with `hide_input=True` is used only when no existing key is available (first-time setup).

**File Encoding:**

All RC file reads and writes use `encoding="utf-8"` explicitly, matching the project's cross-platform UTF-8 encoding standard (Story 2.14).

**`--remove` Flag:**

The `--remove` flag strips the sentinel-delimited block from the RC file. If no block is found, an informational message is shown (not an error). This follows the principle that `--remove` is idempotent.

### Existing Codebase Patterns to Follow

**CLI command file pattern** (from `sync_cmd.py`, `init_cmd.py`):
```python
"""Config command for nest CLI.

Handles the `nest config ai` subcommand.
"""

import typer
from nest.ui.messages import success, error, warning, info, get_console
```

**Message output pattern** (from `ui/messages.py`):
```python
success("Added to ~/.zshrc")        # ✓ green
warning("Run 'source ~/.zshrc'...")  # ⚠ yellow
info("No Nest AI configuration...")  # • blue
error("Failed to write RC file")     # ✗ red
```

**Service class pattern** (from `services/`):
```python
class ShellRCService:
    """Service for managing shell RC file AI configuration blocks."""
    # No __init__ dependencies — operates on filesystem directly
    # Methods are stateless operations
```

**Test naming pattern** (from project-context.md):
```python
def test_detect_shell_returns_zsh_from_shell_env():  # behavior_when_condition
def test_write_config_replaces_existing_block():
def test_remove_config_returns_false_when_not_found():
```

**Test structure** (Arrange-Act-Assert from project-context.md):
```python
def test_write_config_creates_new_file(tmp_path: Path) -> None:
    # Arrange
    rc_path = tmp_path / ".zshrc"
    service = ShellRCService()

    # Act
    service.write_config(rc_path, "https://api.openai.com/v1", "gpt-4o-mini", "sk-test", "zsh")

    # Assert
    content = rc_path.read_text()
    assert BLOCK_START in content
    assert 'export NEST_BASE_URL="https://api.openai.com/v1"' in content
```

**Typer CliRunner test pattern** (from `tests/cli/test_sync_cmd.py`):
```python
from typer.testing import CliRunner
from nest.cli.main import app

runner = CliRunner()

def test_config_ai_help():
    result = runner.invoke(app, ["config", "ai", "--help"])
    assert result.exit_code == 0
    assert "--remove" in result.output
```

### Project Structure Notes

- All changes follow the existing `src/nest/` src-layout
- **New files:** `src/nest/services/shell_rc_service.py`, `src/nest/cli/config_cmd.py`
- **Modified files:** `src/nest/cli/main.py` (add `config` sub-app registration)
- **New test files:** `tests/services/test_shell_rc_service.py`, `tests/cli/test_config_cmd.py`
- No new dependencies — all stdlib (`os`, `sys`, `pathlib`)
- No adapter files needed — RC file I/O is simple enough for the service layer (like `UserConfigAdapter`)

### What This Story Does NOT Include (Scope Boundaries)

- **No `nest config show`** — Only `nest config ai` is implemented. Future subcommands can be added to `config_app`.
- **No project-scoped config** — This manages global user shell RC files, not per-project `.nest/` config.
- **No agent removal** — That's Story 6.6.
- **No changes to `create_llm_provider()`** — The env var detection in `llm_provider.py` is unchanged. This story just makes it easier to SET those env vars.
- **No PowerShell/Windows support** — The project targets macOS/Linux per architecture constraints. `$SHELL` fallback to `~/.profile` covers edge cases.
- **No E2E tests** — RC file modification is too system-invasive for E2E. Comprehensive unit tests with `tmp_path` cover all paths.
- **No encryption of API keys** — Keys are written as plaintext exports, matching standard `.bashrc`/`.zshrc` convention for API keys.

### Dependencies

- **Upstream:** Story 6.1 (LLM Provider Adapter) — defines the `NEST_BASE_URL`, `NEST_TEXT_MODEL`, `NEST_API_KEY` env var names
- **Upstream:** Story 6.4 (Parallel AI Execution) — first-run message references `nest config ai`
- **Downstream:** Story 6.6 (Remove Agents) — may reference `nest config ai` in updated messaging

### Previous Story Intelligence (6.4)

Key learnings from Story 6.4 that apply:

1. **Sequential AI paths lacked exception handling**: Code review caught that error handling was only in the parallel path. **Lesson for this story:** Ensure all code paths have proper error handling, including file I/O operations in `write_config` and `remove_config`.

2. **Missing docstrings for new parameters**: Code review caught this. **Lesson for this story:** All public methods and their parameters must have complete Google-style docstrings from the start.

3. **Unicode escape sequences vs emoji literals**: Code review caught `\U0001f916` instead of `🤖`. **Lesson for this story:** Use emoji characters directly in string literals, not escape sequences.

4. **Baseline test count**: 819 tests (765 from 6.4 + subsequent additions). This story should not regress any.

### Git Intelligence

Recent commits (last 5):
- `3a26220 chore(release): v0.3.1` — latest tag
- `57dca4b fix: doctor version check uses git tags instead of PyPI` — doctor command fix
- `f9fcdaa chore: update version to 0.3.0` — version bump
- `d467b8c chore(release): v0.3.0` — release
- `9eb837e fix: resolve pyright strict type errors in services` — type fixes

No breaking changes or architectural shifts. All CLI command files follow consistent patterns.

### Testing Strategy

- **Shell detection**: Use `monkeypatch.setenv("SHELL", ...)` and `monkeypatch.delenv("SHELL")` to test all shell types
- **RC path resolution**: Use `monkeypatch` for `sys.platform` and `tmp_path` for file existence checks
- **Config block generation**: Pure string comparison — assert exact output for bash/zsh/fish
- **Write/replace/remove**: Use `tmp_path` fixture for isolated file operations. Pre-populate RC files with existing content and verify preservation.
- **Idempotency**: Write 3 times, verify only one block exists
- **CLI tests**: Use Typer `CliRunner` with mocked service or `monkeypatch` to avoid touching real RC files
- **No real home directory modification**: ALL tests use `tmp_path` — never touch `~/.zshrc` or any real RC file

### File Inventory

| File | Action | Purpose |
|------|--------|---------|
| `src/nest/services/shell_rc_service.py` | CREATE | Shell RC file management service — detect shell, resolve RC path, generate/write/remove config blocks |
| `src/nest/cli/config_cmd.py` | CREATE | `nest config ai` command — interactive prompts, `--remove` flag, display messaging |
| `src/nest/cli/main.py` | MODIFY | Register `config` Typer sub-app via `app.add_typer()` |
| `tests/services/test_shell_rc_service.py` | CREATE | Unit tests for ShellRCService — detection, resolution, generation, write, replace, remove |
| `tests/cli/test_config_cmd.py` | CREATE | CLI tests for `nest config ai` — help, flags, integration |

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.5] — AC, story description, dependencies
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6] — Epic scope and design principles
- [Source: _bmad-output/planning-artifacts/architecture.md#Layer Boundaries] — Service/adapter/core layer rules
- [Source: _bmad-output/planning-artifacts/architecture.md#Conventional Commits] — Commit format requirements
- [Source: _bmad-output/project-context.md#Architecture & Dependency Injection] — Protocol-based DI pattern
- [Source: _bmad-output/project-context.md#CLI Output Patterns] — Rich console output rules, success/error/warning/info
- [Source: _bmad-output/project-context.md#Testing Rules] — Test naming, AAA pattern, `tmp_path` usage
- [Source: _bmad-output/project-context.md#Python Language Rules] — PEP 8 naming, type hints, docstrings
- [Source: _bmad-output/project-context.md#Path Handling] — `pathlib.Path` only, `/` operator for joining
- [Source: _bmad-output/project-context.md#Error Handling] — Custom exception hierarchy
- [Source: _bmad-output/implementation-artifacts/6-4-parallel-ai-execution-and-token-reporting.md] — Previous story learnings, code review findings
- [Source: src/nest/cli/main.py] — Current command registration pattern
- [Source: src/nest/cli/sync_cmd.py] — CLI command pattern, create_sync_service composition root
- [Source: src/nest/adapters/llm_provider.py#create_llm_provider] — Env var names and fallback chain
- [Source: src/nest/adapters/user_config.py] — UserConfigAdapter pattern for file I/O in service layer
- [Source: src/nest/ui/messages.py] — success/error/warning/info output helpers
- [Source: src/nest/core/paths.py] — Path constants
- [Source: tests/cli/test_sync_cmd.py] — CliRunner test pattern

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None — clean implementation with no debugging needed.

### Completion Notes List

- All 6 tasks completed with 38 new tests (27 service + 11 CLI)
- Full suite: 803 passed, 0 failures, 54 deselected (e2e)
- Lint: clean (fixed one unused import in test file)
- Typecheck: 0 errors, 0 warnings (Pyright strict)
- Story baseline from 6.4 was 819 tests; current count is 803 selected (857 collected, 54 e2e deselected) — test count difference is due to deselection logic, no regressions
- First Typer sub-app in the project (`app.add_typer(config_app, name="config")`)
- No new dependencies — all stdlib (`os`, `sys`, `pathlib`)

### Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 — Adversarial Code Review  
**Date:** 2026-03-05

**Issues Found:** 1 High, 3 Medium, 2 Low  
**Issues Fixed:** 4 (1 High + 3 Medium)  
**Action Items Created:** 0

**Findings & Fixes Applied:**

1. **[HIGH] Missing file I/O error handling** — `write_config()` and `remove_config()` did bare `read_text`/`write_text` without catching `PermissionError`/`OSError`. Story's own 6.4 retrospective called this out but the lesson was not applied. **Fixed:** Added try/except in both service methods with descriptive error messages; added error handling in CLI layer with user-friendly `error()` output and `typer.Exit(code=1)`.

2. **[MEDIUM] Shell value escaping** — `generate_config_block()` interpolated values into shell strings without escaping `"`, `\`, `` ` ``, `$`. A value like `sk-ab"cd` would corrupt the RC file. **Fixed:** Added `_escape_shell_value()` static method that escapes `\`, `"`, `` ` ``, and `$`; called before all value interpolation.

3. **[MEDIUM] No sentinel order validation** — `_replace_or_append_block()` didn't check `start_idx < end_idx`. Corrupted file with `BLOCK_END` before `BLOCK_START` could cause data loss. **Fixed:** Added `start_idx < end_idx` guard to both `_replace_or_append_block()` and `remove_config()`.

4. **[MEDIUM] Missing tests for edge cases** — No tests for shell special chars, sentinel corruption, or permission errors. **Fixed:** Added 9 new tests across 3 test classes: `TestEscapeShellValue` (5 tests), `TestSentinelOrderValidation` (2 tests), `TestWriteConfigErrorHandling` (2 tests).

**Remaining (Low — accepted):**
- L1: Added `help` parameter to `config_app = typer.Typer(help="Commands for managing Nest configuration.")`
- L2: AC2 mask format minor deviation (cosmetic, self-consistent)

**Post-Review Validation:**
- 812 passed, 54 deselected, 0 failures
- Lint: clean (Ruff)
- Typecheck: 0 errors, 0 warnings (Pyright strict)

### File List

| File | Action |
|------|--------|
| `src/nest/services/shell_rc_service.py` | CREATE |
| `src/nest/cli/config_cmd.py` | CREATE |
| `src/nest/cli/main.py` | MODIFY |
| `tests/services/test_shell_rc_service.py` | CREATE |
| `tests/cli/test_config_cmd.py` | CREATE |

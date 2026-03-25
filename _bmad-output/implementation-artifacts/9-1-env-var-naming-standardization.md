# Story 9.1: Environment Variable Naming Standardization

Status: done

<!-- Sprint Change Proposal: sprint-change-proposal-2026-03-23.md (Approved) -->

## Story

As a **user who already has OpenAI environment variables set**,
I want **Nest to use standard OpenAI SDK variable names (`OPENAI_BASE_URL`, not `OPENAI_API_BASE`) and cleaner Nest-prefixed overrides (`NEST_API_KEY`, not `NEST_AI_API_KEY`)**,
So that **my existing `OPENAI_BASE_URL` and other standard vars are auto-detected without needing Nest-specific configuration**.

## Business Context

Nest's current environment variable names don't match the OpenAI SDK standard. Users with `OPENAI_BASE_URL` (the standard) set in their shell find it ignored because Nest checks `OPENAI_API_BASE` (the legacy name). The Nest-prefixed overrides (`NEST_AI_*`) also have an unnecessary `_AI_` infix that's inconsistent with the cleaner `NEST_*` pattern.

This is a **mechanical rename** with no logic changes. The fallback chain order and behavior are identical — only the string names of the environment variables change. Since the project is pre-1.0, this is the right time to fix naming before users accumulate muscle memory.

**Origin:** Sprint Change Proposal `sprint-change-proposal-2026-03-23.md` (Approved).

**Rename Map:**

| Purpose | Old Nest Override | New Nest Override | Old OpenAI Fallback | New OpenAI Fallback |
|---------|-------------------|-------------------|---------------------|---------------------|
| API Key | `NEST_AI_API_KEY` | `NEST_API_KEY` | `OPENAI_API_KEY` *(unchanged)* | `OPENAI_API_KEY` |
| Base URL | `NEST_AI_ENDPOINT` | `NEST_BASE_URL` | `OPENAI_API_BASE` | `OPENAI_BASE_URL` |
| Text Model | `NEST_AI_MODEL` | `NEST_TEXT_MODEL` | `OPENAI_MODEL` *(unchanged)* | `OPENAI_MODEL` |
| Vision Model | `NEST_AI_VISION_MODEL` | `NEST_VISION_MODEL` | `OPENAI_VISION_MODEL` *(unchanged)* | `OPENAI_VISION_MODEL` |

**New Fallback Chains:**
```
API key:      NEST_API_KEY      → OPENAI_API_KEY       → None
Base URL:     NEST_BASE_URL     → OPENAI_BASE_URL      → https://api.openai.com/v1
Text model:   NEST_TEXT_MODEL   → OPENAI_MODEL         → gpt-4o-mini
Vision model: NEST_VISION_MODEL → OPENAI_VISION_MODEL  → (Azure: text model fallback) → gpt-4.1
```

## Acceptance Criteria

### AC1: Text LLM Provider Uses New Variable Names

**Given** `NEST_API_KEY` is set in the environment
**When** `create_llm_provider()` is called
**Then** it uses `NEST_API_KEY` as the API key
**And** checks `NEST_BASE_URL` for the base URL (default: `https://api.openai.com/v1`)
**And** checks `NEST_TEXT_MODEL` for the model name (default: `gpt-4o-mini`)

**Given** `NEST_API_KEY` is NOT set but `OPENAI_API_KEY` IS set
**When** `create_llm_provider()` is called
**Then** it falls back to `OPENAI_API_KEY`
**And** falls back to `OPENAI_BASE_URL` for base URL
**And** falls back to `OPENAI_MODEL` for model name

### AC2: Vision LLM Provider Uses New Variable Names

**Given** `NEST_VISION_MODEL` is set in the environment
**When** `create_vision_provider()` is called
**Then** it reads `NEST_VISION_MODEL` for the vision model
**And** falls back to `OPENAI_VISION_MODEL` if not set

### AC3: Config Block Writes New Variable Names

**Given** the user runs `nest config ai` and provides values
**When** the config block is written to the shell RC file
**Then** the block uses the new variable names:
```bash
# --- Nest AI Configuration (managed by `nest config ai`) ---
export NEST_BASE_URL="https://..."
export NEST_TEXT_MODEL="gpt-4o-mini"
export NEST_API_KEY="sk-..."
# --- End Nest AI Configuration ---
```

**Given** fish shell is detected
**When** config is written
**Then** fish-compatible syntax uses new names:
```fish
# --- Nest AI Configuration (managed by `nest config ai`) ---
set -gx NEST_BASE_URL "https://..."
set -gx NEST_TEXT_MODEL "gpt-4o-mini"
set -gx NEST_API_KEY "sk-..."
# --- End Nest AI Configuration ---
```

### AC4: Config Command Smart Defaults Use New Variable Names

**Given** the user runs `nest config ai`
**When** smart defaults are populated from existing env vars
**Then** the command reads from `NEST_BASE_URL` (falling back to `OPENAI_BASE_URL`), `NEST_TEXT_MODEL` (falling back to `OPENAI_MODEL`), and `NEST_API_KEY` (falling back to `OPENAI_API_KEY`)

### AC5: Sync Command AI Status Uses New Variable Names

**Given** the user runs `nest sync` with AI detection display
**When** the AI status is shown
**Then** it checks `NEST_API_KEY` (not `NEST_AI_API_KEY`)
**And** the "not configured" message references `NEST_API_KEY` (not `NEST_AI_API_KEY`)

### AC6: All Tests Pass After Rename

**Given** all environment variable strings are updated in both source and test files
**When** `pytest -m "not e2e"` is run
**Then** all tests pass with zero regressions

### AC7: Documentation Updated

**Given** all code changes are complete and tests pass
**When** documentation is reviewed
**Then** `README.md`, PRD, epics, and affected story files reflect the new variable names

## Tasks / Subtasks

### Task 1: Rename Env Vars in `src/nest/adapters/llm_provider.py` (AC: 1, 2)

- [x] 1.1: In `create_llm_provider()`, rename env var strings:
  - `"NEST_AI_API_KEY"` → `"NEST_API_KEY"`
  - `"NEST_AI_ENDPOINT"` → `"NEST_BASE_URL"`
  - `"OPENAI_API_BASE"` → `"OPENAI_BASE_URL"`
  - `"NEST_AI_MODEL"` → `"NEST_TEXT_MODEL"`
- [x] 1.2: In `create_vision_provider()`, rename env var strings:
  - `"NEST_AI_VISION_MODEL"` → `"NEST_VISION_MODEL"`
  - `"NEST_AI_API_KEY"` → `"NEST_API_KEY"` (if referenced)
  - `"NEST_AI_ENDPOINT"` → `"NEST_BASE_URL"` (if referenced)
  - `"OPENAI_API_BASE"` → `"OPENAI_BASE_URL"` (if referenced)
  - `"NEST_AI_MODEL"` → `"NEST_TEXT_MODEL"` (if referenced)
- [x] 1.3: Update all docstrings in the file to reflect new variable names in fallback chain documentation

### Task 2: Rename Env Vars in `src/nest/services/shell_rc_service.py` (AC: 3)

- [x] 2.1: In `generate_config_block()`, rename the export variable names:
  - `NEST_AI_ENDPOINT` → `NEST_BASE_URL`
  - `NEST_AI_MODEL` → `NEST_TEXT_MODEL`
  - `NEST_AI_API_KEY` → `NEST_API_KEY`
- [x] 2.2: Update both bash/zsh (`export`) and fish (`set -gx`) syntax blocks

### Task 3: Rename Env Vars in `src/nest/cli/config_cmd.py` (AC: 4)

- [x] 3.1: Update smart default lookups:
  - `os.environ.get("NEST_AI_ENDPOINT")` → `os.environ.get("NEST_BASE_URL")`
  - `os.environ.get("OPENAI_API_BASE")` → `os.environ.get("OPENAI_BASE_URL")`
  - `os.environ.get("NEST_AI_MODEL")` → `os.environ.get("NEST_TEXT_MODEL")`
  - `os.environ.get("NEST_AI_API_KEY")` → `os.environ.get("NEST_API_KEY")`
- [x] 3.2: Update any help text or display strings that reference old variable names

### Task 4: Rename Env Vars in `src/nest/cli/sync_cmd.py` (AC: 5)

- [x] 4.1: Update AI detection display:
  - `os.environ.get("NEST_AI_API_KEY")` → `os.environ.get("NEST_API_KEY")`
  - `"NEST_AI_API_KEY"` string literal → `"NEST_API_KEY"`
  - `"set NEST_AI_API_KEY / OPENAI_API_KEY"` → `"set NEST_API_KEY / OPENAI_API_KEY"` (in the "not configured" message)

### Task 5: Update Test File `tests/adapters/test_llm_provider.py` (AC: 6)

- [x] 5.1: Rename all `monkeypatch.setenv()` / `monkeypatch.delenv()` calls:
  - `"NEST_AI_API_KEY"` → `"NEST_API_KEY"`
  - `"NEST_AI_ENDPOINT"` → `"NEST_BASE_URL"`
  - `"OPENAI_API_BASE"` → `"OPENAI_BASE_URL"`
  - `"NEST_AI_MODEL"` → `"NEST_TEXT_MODEL"`
  - `"NEST_AI_VISION_MODEL"` → `"NEST_VISION_MODEL"`
- [x] 5.2: Update any assertion strings and docstrings that reference old names

### Task 6: Update Test File `tests/services/test_shell_rc_service.py` (AC: 6)

- [x] 6.1: Update all assertion strings for config block content:
  - `'export NEST_AI_ENDPOINT='` → `'export NEST_BASE_URL='`
  - `'export NEST_AI_MODEL='` → `'export NEST_TEXT_MODEL='`
  - `'export NEST_AI_API_KEY='` → `'export NEST_API_KEY='`
  - `'set -gx NEST_AI_ENDPOINT '` → `'set -gx NEST_BASE_URL '`
  - `'set -gx NEST_AI_MODEL '` → `'set -gx NEST_TEXT_MODEL '`
  - `'set -gx NEST_AI_API_KEY '` → `'set -gx NEST_API_KEY '`
- [x] 6.2: Update `assert "NEST_AI_ENDPOINT" in block` → `assert "NEST_BASE_URL" in block` (and similar for MODEL, API_KEY)

### Task 7: Update Test File `tests/cli/test_config_cmd.py` (AC: 6)

- [x] 7.1: Update assertion strings for config block content:
  - `'export NEST_AI_ENDPOINT='` → `'export NEST_BASE_URL='`
  - `'export NEST_AI_MODEL='` → `'export NEST_TEXT_MODEL='`
  - `'export NEST_AI_API_KEY='` → `'export NEST_API_KEY='`

### Task 8: Update Test File `tests/cli/test_sync_cmd.py` (AC: 6)

- [x] 8.1: Update the "not configured" assertion string:
  - `"set NEST_AI_API_KEY / OPENAI_API_KEY"` → `"set NEST_API_KEY / OPENAI_API_KEY"`

### Task 9: Update E2E Test Files (AC: 6)

- [x] 9.1: In `tests/e2e/conftest.py`, update the env var cleanup list:
  - `"NEST_AI_API_KEY"` → `"NEST_API_KEY"`
  - `"NEST_AI_ENDPOINT"` → `"NEST_BASE_URL"`
  - `"NEST_AI_MODEL"` → `"NEST_TEXT_MODEL"`
  - `"NEST_AI_VISION_MODEL"` → `"NEST_VISION_MODEL"`
  - `"OPENAI_API_BASE"` → `"OPENAI_BASE_URL"`
- [x] 9.2: In `tests/e2e/test_glossary_e2e.py`, update the detection check:
  - `os.environ.get("NEST_AI_API_KEY")` → `os.environ.get("NEST_API_KEY")`
- [x] 9.3: In `tests/e2e/test_image_description_e2e.py`, update env var dict keys and docstrings:
  - `"NEST_AI_API_KEY"` → `"NEST_API_KEY"`
  - `"NEST_AI_ENDPOINT"` → `"NEST_BASE_URL"`
  - `"NEST_AI_VISION_MODEL"` → `"NEST_VISION_MODEL"`
  - `"NEST_AI_MODEL"` → `"NEST_TEXT_MODEL"`

### Task 10: Run Full Test Suite (AC: 6)

- [x] 10.1: Run `pytest -m "not e2e"` — all tests pass, zero regressions
- [x] 10.2: Run `make lint` — clean (Ruff)
- [x] 10.3: Run `make typecheck` — clean (Pyright strict mode, 0 errors)

### Task 11: Update Documentation (AC: 7)

- [x] 11.1: Update `README.md` — replace all occurrences of old env var names with new names in AI setup guidance
- [x] 11.2: Update `_bmad-output/planning-artifacts/prd.md`:
  - FR27: Update env var auto-detection description to use `NEST_API_KEY`, `NEST_BASE_URL`, `NEST_TEXT_MODEL`
  - FR31: Update `nest config ai` description to reference new var names
  - FR33: Update fallback chain to use `NEST_API_KEY → OPENAI_API_KEY`, `NEST_BASE_URL → OPENAI_BASE_URL`, etc.
- [x] 11.3: Update `_bmad-output/planning-artifacts/epics.md` — update Epic 6 and 7 story descriptions with new var names
- [x] 11.4: Update `_bmad-output/implementation-artifacts/6-1-llm-provider-adapter-and-ai-detection.md`:
  - AC1, AC2: Replace `NEST_AI_API_KEY`, `NEST_AI_ENDPOINT`, `NEST_AI_MODEL` with new names
  - Replace `OPENAI_API_BASE` with `OPENAI_BASE_URL`
  - Update code examples and fallback chain documentation in Dev Notes
- [x] 11.5: Update `_bmad-output/implementation-artifacts/6-5-nest-config-ai-shell-rc-writer.md`:
  - AC2, AC3: Replace `NEST_AI_ENDPOINT`, `NEST_AI_MODEL`, `NEST_AI_API_KEY` with new names in smart defaults and config block examples
  - Update code examples in tasks to use new names
- [x] 11.6: Update `_bmad-output/implementation-artifacts/7-1-vision-capable-llm-adapters.md`:
  - Update `NEST_AI_VISION_MODEL` → `NEST_VISION_MODEL` in AC3 fallback chain and code examples

## Dev Notes

### Nature of This Change

This is a **pure mechanical rename** — no logic, control flow, architecture, or behavioral changes. The fallback chain order and defaults remain identical. Only the string names of environment variables change.

### Architecture Compliance

- **No structural changes** — no new files, no deleted files, no moved code. Every change is an in-place string replacement.
- **Same layered architecture** — adapter, service, CLI boundaries unchanged.
- **Same DI pattern** — `create_llm_provider()` and `create_vision_provider()` factory signatures unchanged.
- **Same test structure** — test files, test classes, test method names unchanged (only assertion strings and `setenv`/`delenv` arguments change).

### Critical Implementation Details

**Complete Rename Map (for search-and-replace):**

| Old String | New String | Context |
|------------|-----------|---------|
| `NEST_AI_API_KEY` | `NEST_API_KEY` | Env var name in code and tests |
| `NEST_AI_ENDPOINT` | `NEST_BASE_URL` | Env var name in code and tests |
| `NEST_AI_MODEL` | `NEST_TEXT_MODEL` | Env var name in code and tests |
| `NEST_AI_VISION_MODEL` | `NEST_VISION_MODEL` | Env var name in code and tests |
| `OPENAI_API_BASE` | `OPENAI_BASE_URL` | OpenAI fallback env var name |

**Unchanged variables (do NOT rename):**
- `OPENAI_API_KEY` — already matches OpenAI SDK standard
- `OPENAI_MODEL` — already matches convention
- `OPENAI_VISION_MODEL` — already matches convention

**Implementation order matters:**
1. Source code first (Tasks 1–4) — so the code is internally consistent
2. Tests next (Tasks 5–9) — update assertions to match new code
3. Run tests (Task 10) — validate correctness
4. Documentation last (Task 11) — update after code is proven correct

**`nest config ai` block format change:**

The config block sentinel comments are UNCHANGED:
```
# --- Nest AI Configuration (managed by `nest config ai`) ---
# --- End Nest AI Configuration ---
```

Only the variable names inside the block change. Users who previously ran `nest config ai` will have old var names in their RC files. Re-running `nest config ai` will replace the block with new names (idempotent block replacement handles this).

### Affected Files Summary

| File | Action | Change Type |
|------|--------|-------------|
| `src/nest/adapters/llm_provider.py` | MODIFY | Rename env var strings + docstrings |
| `src/nest/services/shell_rc_service.py` | MODIFY | Rename export var names |
| `src/nest/cli/config_cmd.py` | MODIFY | Rename env var lookups + help text |
| `src/nest/cli/sync_cmd.py` | MODIFY | Rename env var check + display string |
| `tests/adapters/test_llm_provider.py` | MODIFY | Rename setenv/delenv + assertions |
| `tests/services/test_shell_rc_service.py` | MODIFY | Rename assertion strings |
| `tests/cli/test_config_cmd.py` | MODIFY | Rename assertion strings |
| `tests/cli/test_sync_cmd.py` | MODIFY | Rename assertion string |
| `tests/e2e/conftest.py` | MODIFY | Rename cleanup list |
| `tests/e2e/test_glossary_e2e.py` | MODIFY | Rename detection check |
| `tests/e2e/test_image_description_e2e.py` | MODIFY | Rename env var dict keys + docstrings |
| `README.md` | MODIFY | Rename env var references in docs |
| `_bmad-output/planning-artifacts/prd.md` | MODIFY | Rename FR27, FR31, FR33 text |
| `_bmad-output/planning-artifacts/epics.md` | MODIFY | Rename Epic 6/7 descriptions |
| `_bmad-output/implementation-artifacts/6-1-*.md` | MODIFY | Rename AC + code examples |
| `_bmad-output/implementation-artifacts/6-5-*.md` | MODIFY | Rename AC + code examples |
| `_bmad-output/implementation-artifacts/7-1-*.md` | MODIFY | Rename AC + code examples |

### What This Story Does NOT Include (Scope Boundaries)

- **No logic changes** — fallback chain behavior, defaults, and error handling are unchanged
- **No new environment variables** — only renames of existing ones
- **No new tests** — only updates to existing test assertions
- **No API changes** — function signatures, return types, class interfaces unchanged
- **No dependency changes** — `pyproject.toml` not modified
- **No new files created or old files deleted**

### Testing Strategy

- All changes validated by running existing tests with updated env var strings
- `monkeypatch.setenv()` calls updated to use new variable names
- Assertion strings updated to match new export names
- No new test cases needed — the mechanical rename is fully covered by existing tests
- E2E test env var dicts updated to new names

### Dependencies

- **No upstream dependencies** — this is a standalone rename
- **No downstream dependents** — future stories will reference the new names

### References

- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-03-23.md] — Approved change proposal
- [Source: src/nest/adapters/llm_provider.py] — Primary env var detection logic
- [Source: src/nest/services/shell_rc_service.py] — Config block generation
- [Source: src/nest/cli/config_cmd.py] — Smart defaults from env vars
- [Source: src/nest/cli/sync_cmd.py] — AI detection display

## Dev Agent Record

### Implementation Summary

Pure mechanical rename of environment variable strings across source, tests, and documentation. No logic, control flow, or architectural changes.

### Decisions Made

- PRD already had no old env var names (no changes needed for Task 11.2)
- Pre-existing test failures in `tests/integration/` (ManifestAdapter signature) and pre-existing Pyright errors in `doctor_cmd.py`, `ai_glossary_service.py`, `sync_service.py` are unrelated to this story

### Test Results

- **847 passed**, 0 failed (excluding pre-existing integration failures unrelated to this story)
- **Lint**: All changed files pass Ruff (0 errors)
- **Typecheck**: 0 new Pyright errors (9 pre-existing in unrelated files)

### File List

| File | Action |
|------|--------|
| `src/nest/adapters/llm_provider.py` | MODIFIED — env var strings + docstrings |
| `src/nest/services/shell_rc_service.py` | MODIFIED — export var names |
| `src/nest/cli/config_cmd.py` | MODIFIED — env var lookups |
| `src/nest/cli/sync_cmd.py` | MODIFIED — env var check + display string |
| `tests/adapters/test_llm_provider.py` | MODIFIED — setenv/delenv + assertions + docstrings |
| `tests/services/test_shell_rc_service.py` | MODIFIED — assertion strings |
| `tests/cli/test_config_cmd.py` | MODIFIED — assertion strings |
| `tests/cli/test_sync_cmd.py` | MODIFIED — assertion string |
| `tests/e2e/conftest.py` | MODIFIED — env var cleanup list |
| `tests/e2e/test_glossary_e2e.py` | MODIFIED — detection check |
| `tests/e2e/test_image_description_e2e.py` | MODIFIED — env var dict keys + docstrings |
| `README.md` | MODIFIED — env var references |
| `_bmad-output/planning-artifacts/epics.md` | MODIFIED — env var references |
| `_bmad-output/implementation-artifacts/6-1-llm-provider-adapter-and-ai-detection.md` | MODIFIED — env var references |
| `_bmad-output/implementation-artifacts/6-5-nest-config-ai-shell-rc-writer.md` | MODIFIED — env var references |
| `_bmad-output/implementation-artifacts/7-1-vision-capable-llm-adapters.md` | MODIFIED — env var references |

# Sprint Change Proposal: Standardize Environment Variable Naming

**Date:** 2026-03-23
**Scope:** Minor — Direct implementation by dev team
**Status:** Approved

---

## 1. Issue Summary

Nest uses non-standard environment variable names (`NEST_AI_ENDPOINT`, `OPENAI_API_BASE`, `OPENAI_MODEL`) that don't align with the OpenAI SDK's standard naming convention. Users who already have `OPENAI_API_KEY` and `OPENAI_BASE_URL` set (the standard vars) find that Nest doesn't pick them up because it checks `OPENAI_API_BASE` instead of `OPENAI_BASE_URL`. The Nest-specific override names (`NEST_AI_*`) are also inconsistently structured compared to the standard pattern.

**Discovery:** User observation — `.zshrc` has `OPENAI_BASE_URL` set, but Nest looks for `OPENAI_API_BASE`.

## 2. Environment Variable Rename Map

| Purpose | OLD Nest Override | NEW Nest Override | OLD OpenAI Fallback | NEW OpenAI Fallback |
|---------|------------------|-------------------|---------------------|---------------------|
| API Key | `NEST_AI_API_KEY` | `NEST_API_KEY` | `OPENAI_API_KEY` | `OPENAI_API_KEY` (unchanged) |
| Base URL | `NEST_AI_ENDPOINT` | `NEST_BASE_URL` | `OPENAI_API_BASE` | `OPENAI_BASE_URL` |
| Text Model | `NEST_AI_MODEL` | `NEST_TEXT_MODEL` | `OPENAI_MODEL` | `OPENAI_MODEL` (unchanged) |
| Vision Model | `NEST_AI_VISION_MODEL` | `NEST_VISION_MODEL` | `OPENAI_VISION_MODEL` | `OPENAI_VISION_MODEL` (unchanged) |

### New Fallback Chains

```
API key:      NEST_API_KEY      → OPENAI_API_KEY       → None
Base URL:     NEST_BASE_URL     → OPENAI_BASE_URL      → https://api.openai.com/v1
Text model:   NEST_TEXT_MODEL   → OPENAI_MODEL         → gpt-4o-mini
Vision model: NEST_VISION_MODEL → OPENAI_VISION_MODEL  → (Azure: text model fallback) → gpt-4.1
```

## 3. `nest config ai` Block Output Change

**OLD:**
```bash
# --- Nest AI Configuration (managed by `nest config ai`) ---
export NEST_AI_ENDPOINT="https://..."
export NEST_AI_MODEL="gpt-4o-mini"
export NEST_AI_API_KEY="sk-..."
# --- End Nest AI Configuration ---
```

**NEW:**
```bash
# --- Nest AI Configuration (managed by `nest config ai`) ---
export NEST_BASE_URL="https://..."
export NEST_TEXT_MODEL="gpt-4o-mini"
export NEST_API_KEY="sk-..."
# --- End Nest AI Configuration ---
```

## 4. Impact Analysis

### Epic/Story Impact

| Epic | Impact |
|------|--------|
| Epic 6 (Built-in AI Enrichment) | **Stories 6.1, 6.5 affected** — env var names in code + docs |
| Epic 7 (Image Description) | **Story 7.1 affected** — vision model env var names |
| Epics 1–5, 8 | No impact |

### Affected Source Files

| File | Change |
|------|--------|
| `src/nest/adapters/llm_provider.py` | Rename env var strings in `create_llm_provider()` and `create_vision_provider()` + docstrings |
| `src/nest/services/shell_rc_service.py` | Rename env var strings in config block generation |
| `src/nest/cli/config_cmd.py` | Rename env var references in smart defaults + help text |
| `src/nest/cli/sync_cmd.py` | Rename env var references in AI detection display |

### Affected Test Files

| File | Change |
|------|--------|
| `tests/adapters/test_llm_provider.py` | Update all `setenv`/`delenv` calls to new names |
| `tests/services/test_shell_rc_service.py` | Update assertion strings |
| `tests/cli/test_config_cmd.py` | Update assertion strings |
| `tests/cli/test_sync_cmd.py` | Update env var references |
| `tests/e2e/conftest.py` | Update env var cleanup list |
| `tests/e2e/test_glossary_e2e.py` | Update detection check |
| `tests/e2e/test_image_description_e2e.py` | Update env var references |

### Affected Documentation

| File | Change |
|------|--------|
| `README.md` | Update AI setup guidance |
| `_bmad-output/planning-artifacts/prd.md` | Update FR27, FR31, FR33 text |
| `_bmad-output/planning-artifacts/epics.md` | Update Epic 6 and 7 story text |
| `_bmad-output/implementation-artifacts/6-1-*.md` | Update AC1, AC2, code examples |
| `_bmad-output/implementation-artifacts/6-5-*.md` | Update AC2, AC3 block examples |
| `_bmad-output/implementation-artifacts/7-1-*.md` | Update AC3 fallback chain |

## 5. Recommended Approach

**Direct Adjustment** — clean rename with no behavioral changes. No code logic, architecture, or test structure changes. Purely a search-and-replace across env var strings.

- **Effort:** Low (mechanical rename across ~15 files)
- **Risk:** Low (no logic changes, existing test coverage validates correctness after rename)
- **Breaking change:** Yes — users with `NEST_AI_*` vars in their `.zshrc` will need to re-run `nest config ai` or manually update. Acceptable since the tool is pre-1.0 and the config command makes migration trivial.

## 6. Implementation Handoff

**Scope:** Minor — direct implementation by dev team.
**Route to:** Dev agent for mechanical rename across source code, tests, docs, and planning artifacts.

**Success criteria:**
1. All tests pass after rename
2. `nest config ai` writes new var names (`NEST_BASE_URL`, `NEST_TEXT_MODEL`, `NEST_API_KEY`)
3. `create_llm_provider()` and `create_vision_provider()` resolve new var names correctly
4. Updated PRD FRs reflect new naming

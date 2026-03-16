# Story 6.6: Remove Enricher & Glossary Agents

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want **the separate enricher and glossary agents removed from the project**,
So that **I'm not confused by multiple agents and all AI enrichment happens automatically during sync**.

## Business Context

This is the **sixth and final story in Epic 6** (Built-in AI Enrichment). Stories 6.1–6.4 built the complete built-in AI pipeline: LLM provider adapter (6.1), AI index enrichment during sync (6.2), AI glossary generation during sync (6.3), and parallel execution with token reporting (6.4). Story 6.5 added `nest config ai` for credential setup.

With AI enrichment now happening automatically during `nest sync`, the separate `nest-enricher.agent.md` and `nest-glossary.agent.md` agent files are **obsolete**. They were designed for manual invocation via VS Code Copilot Chat — a workflow that has been fully replaced by the built-in AI pipeline. Keeping them causes user confusion (which agent to use?) and code maintenance burden.

This story is a **cleanup/removal story** — it deletes templates, removes writer methods, strips init/sync references, and updates tests. There is **zero new functionality** to build; this is purely about removing dead code and obsolete user-facing prompts.

**Key principle:** After this story, the only agent file is `nest.agent.md` (the primary Nest agent for VS Code Copilot Chat). AI enrichment is invisible — it just happens during sync when API keys are present.

## Acceptance Criteria

### AC1: Init Only Creates Primary Agent

**Given** `nest init` runs to create a new project
**When** agent files are generated
**Then** only `.github/agents/nest.agent.md` is created
**And** `nest-enricher.agent.md` is NOT created
**And** `nest-glossary.agent.md` is NOT created

### AC2: Agent Template Files Deleted

**Given** the codebase is updated
**When** agent template files are reviewed
**Then** `src/nest/agents/templates/enricher.md.jinja` is deleted
**And** `src/nest/agents/templates/glossary.md.jinja` is deleted
**And** only `src/nest/agents/templates/vscode.md.jinja` remains

### AC3: VSCodeAgentWriter Methods Removed

**Given** `VSCodeAgentWriter` in `src/nest/agents/vscode_writer.py`
**When** the class is reviewed
**Then** `render_enricher()` method is removed
**And** `generate_enricher()` method is removed
**And** `render_glossary()` method is removed
**And** `generate_glossary()` method is removed
**And** only `render()` and `generate()` methods remain (for the primary nest agent)

### AC4: Init Command Cleaned Up

**Given** `init_cmd.py` wires up agent generation
**When** init runs
**Then** the loop calling `generate_enricher()` and `generate_glossary()` is removed
**And** only the primary `nest.agent.md` is generated (via `InitService.execute()` which calls `agent_writer.generate()`)

### AC5: Sync Summary Messages Removed

**Given** sync completes and AI is NOT configured
**When** the sync summary is displayed
**Then** NO message about running `@nest-enricher` or `@nest-glossary` agents is shown
**And** the old prompt messages are removed from `_display_sync_summary` in `sync_cmd.py`

**Given** sync completes and AI IS configured
**When** the sync summary is displayed
**Then** enrichment results are shown inline (descriptions generated, glossary terms defined, token usage — already implemented by 6.2–6.4)
**And** no reference to agent invocation is made

### AC6: Doctor/ProjectChecker Unchanged

**Given** `ProjectChecker` validates project state
**When** agent file checks run
**Then** only `nest.agent.md` presence is checked (already the case — no changes needed)
**And** no checks for `nest-enricher.agent.md` or `nest-glossary.agent.md` exist

### AC7: E2E Tests Updated

**Given** all existing E2E tests reference enricher or glossary agents
**When** tests are updated
**Then** `test_enricher_agent_created_on_init` in `test_enrichment_e2e.py` is removed
**And** `test_glossary_agent_created_on_init` in `test_glossary_e2e.py` is removed
**And** `test_sync_output_shows_glossary_prompt` in `test_glossary_e2e.py` is updated to NOT assert `@nest-glossary` in output
**And** all remaining tests pass with no regressions

### AC8: All Tests Pass

**Given** all code changes are complete
**When** the full test suite runs (`pytest -m "not e2e"`)
**Then** all tests pass with zero failures
**And** lint (Ruff) and typecheck (Pyright strict) are clean

## Tasks / Subtasks

### Task 1: Delete Agent Template Files (AC: 2)

- [x] 1.1: Delete `src/nest/agents/templates/enricher.md.jinja`
- [x] 1.2: Delete `src/nest/agents/templates/glossary.md.jinja`
- [x] 1.3: Verify `src/nest/agents/templates/vscode.md.jinja` is the only remaining template

### Task 2: Remove VSCodeAgentWriter Methods (AC: 3)

- [x] 2.1: Open `src/nest/agents/vscode_writer.py`
- [x] 2.2: Remove `render_enricher()` method (lines ~56–66)
- [x] 2.3: Remove `generate_enricher()` method (lines ~68–84)
- [x] 2.4: Remove `render_glossary()` method (lines ~86–96)
- [x] 2.5: Remove `generate_glossary()` method (lines ~98–113)
- [x] 2.6: Verify only `__init__()`, `render()`, and `generate()` remain

### Task 3: Clean Up Init Command (AC: 1, 4)

- [x] 3.1: Open `src/nest/cli/init_cmd.py`
- [x] 3.2: Remove the `for gen_method, filename in [...]` loop (lines ~90–97) that calls `generate_enricher` and `generate_glossary`
- [x] 3.3: Remove the standalone `agent_writer = VSCodeAgentWriter(...)` instantiation (line ~89) — the primary agent is already generated by `InitService.execute()` via the injected `agent_writer`
- [x] 3.4: Verify `nest init` still generates `nest.agent.md` (handled by `InitService`)

### Task 4: Remove Sync Summary Agent Prompts (AC: 5)

- [x] 4.1: Open `src/nest/cli/sync_cmd.py`
- [x] 4.2: Remove the enricher prompt block (~lines 446–451):
  ```python
  if result.enrichment_needed > 0:
      console.print()
      n = result.enrichment_needed
      console.print(f"  [cyan]ℹ {n} file(s) need descriptions ...")
      console.print("    Run the @nest-enricher agent ...")
  ```
- [x] 4.3: Remove the glossary prompt block (~lines 454–460):
  ```python
  if result.glossary_terms_discovered > 0 and result.ai_glossary_terms_added == 0:
      console.print()
      g = result.glossary_terms_discovered
      console.print(f"  [cyan]ℹ {g} candidate glossary term(s) ...")
      console.print("    Run the @nest-glossary agent ...")
  ```
- [x] 4.4: Note: The `enrichment_needed` and `glossary_terms_discovered` fields on `SyncResult` model can remain — they track real data used by the AI pipeline. Only the user-facing "run the agent" prompts are removed.

### Task 5: Update E2E Tests (AC: 7)

- [x] 5.1: Open `tests/e2e/test_enrichment_e2e.py`
- [x] 5.2: Remove `test_enricher_agent_created_on_init` method (~lines 208–227)
- [x] 5.3: Open `tests/e2e/test_glossary_e2e.py`
- [x] 5.4: Remove `test_glossary_agent_created_on_init` method (~lines 97–115)
- [x] 5.5: Update `test_sync_output_shows_glossary_prompt` method (~lines 150–167):
  - Change the assertion: instead of asserting `@nest-glossary` in output, assert that the output does NOT contain `@nest-glossary`
  - The test should still verify that `candidate glossary term` appears in output (the count info is still valid)
  - Actually, since the prompt messages are being removed entirely, this test should be updated to verify the prompt is NOT shown, or removed if the sync output no longer mentions candidate terms at all
  - **Decision:** Remove this test entirely since the "candidate glossary term" message is being deleted in Task 4

### Task 6: Delete Shipped Agent Files from Repo (AC: 1)

- [x] 6.1: Delete `.github/agents/nest-enricher.agent.md` from the repository
- [x] 6.2: Delete `.github/agents/nest-glossary.agent.md` from the repository
- [x] 6.3: These are the development repo's own agent files — they should also be cleaned up

### Task 7: Update Comments and Documentation References (AC: cleanup)

- [x] 7.1: In `src/nest/services/glossary_hints_service.py`, update docstring (line 4) from "Produces hints for the glossary agent" to "Produces hints for AI glossary generation"
- [x] 7.2: In `src/nest/services/glossary_hints_service.py`, update comment (line ~164) from "The glossary agent performs deeper domain-term analysis via LLM" to "The AI glossary service performs deeper domain-term analysis via LLM"
- [x] 7.3: Update `_bmad-output/project-context.md` Project Paths section (lines ~393–395): remove `nest-enricher.agent.md` and `nest-glossary.agent.md` from the directory tree, keeping only `nest.agent.md`

### Task 8: Run Full Validation (AC: 8)

- [x] 8.1: Run `python -m pytest -m "not e2e"` — all tests pass
- [x] 8.2: Run `ruff check src/ tests/` — clean lint
- [x] 8.3: Run `pyright` (or `npx pyright`) — 0 errors, 0 warnings
- [x] 8.4: Verify test count is close to 812 (6.5 baseline), minus removed E2E test methods

## Dev Notes

### Summary of Changes

This is a **deletion/cleanup story**. No new services, adapters, models, or protocols are created. The scope is:

1. **Delete files:** 2 Jinja templates, 2 shipped agent `.md` files
2. **Remove methods:** 4 methods from `VSCodeAgentWriter`
3. **Remove code blocks:** enricher/glossary generation loop in `init_cmd.py`, agent prompt blocks in `sync_cmd.py`
4. **Remove tests:** 3 E2E test methods that validated the now-removed agent file creation and agent prompt output
5. **Update comments:** 2 docstring/comment references in `glossary_hints_service.py`, 1 path tree in `project-context.md`

### Architecture Impact

- **No protocol changes** — `AgentWriterProtocol` in `adapters/protocols.py` only defines `render()` and `generate()` (the enricher/glossary methods are on the concrete class, not the protocol)
- **No service layer changes** — `InitService` already only calls `agent_writer.generate()` for the primary agent; the enricher/glossary generation was done at the CLI layer in `init_cmd.py`
- **No model changes** — `SyncResult.enrichment_needed` and `SyncResult.glossary_terms_discovered` fields remain (used internally by AI pipeline logic, just no longer displayed as "run agent" prompts)
- **`ProjectChecker`** already only validates `nest.agent.md` — no changes needed
- **`DoctorService.regenerate_agent_file()`** already only regenerates `nest.agent.md` — no changes needed

### Files to Modify/Delete

| File | Action | What Changes |
|------|--------|--------------|
| `src/nest/agents/templates/enricher.md.jinja` | DELETE | Remove enricher agent template |
| `src/nest/agents/templates/glossary.md.jinja` | DELETE | Remove glossary agent template |
| `src/nest/agents/vscode_writer.py` | MODIFY | Remove `render_enricher()`, `generate_enricher()`, `render_glossary()`, `generate_glossary()` methods |
| `src/nest/cli/init_cmd.py` | MODIFY | Remove enricher/glossary generation loop and standalone `agent_writer` instantiation |
| `src/nest/cli/sync_cmd.py` | MODIFY | Remove `@nest-enricher` and `@nest-glossary` prompt blocks from `_display_sync_summary()` |
| `src/nest/services/glossary_hints_service.py` | MODIFY | Update 2 comments referencing "glossary agent" |
| `.github/agents/nest-enricher.agent.md` | DELETE | Remove shipped enricher agent from repo |
| `.github/agents/nest-glossary.agent.md` | DELETE | Remove shipped glossary agent from repo |
| `tests/e2e/test_enrichment_e2e.py` | MODIFY | Remove `test_enricher_agent_created_on_init` |
| `tests/e2e/test_glossary_e2e.py` | MODIFY | Remove `test_glossary_agent_created_on_init` and `test_sync_output_shows_glossary_prompt` |
| `_bmad-output/project-context.md` | MODIFY | Remove enricher/glossary agent paths from directory tree |

### What NOT to Change

- **Do NOT remove** `GlossaryHintsService` — it extracts candidate terms (Phase 1) still used by `AIGlossaryService`
- **Do NOT remove** `AIGlossaryService` or `AIEnrichmentService` — these ARE the replacement (built-in AI)
- **Do NOT remove** `SyncResult.enrichment_needed` or `SyncResult.glossary_terms_discovered` — used internally by sync pipeline logic
- **Do NOT remove** `00_GLOSSARY_HINTS.yaml` or `00_INDEX_HINTS.yaml` generation — these hints files power the AI pipeline
- **Do NOT modify** `adapters/protocols.py` — `AgentWriterProtocol` only has `render()` and `generate()`
- **Do NOT modify** `services/doctor_service.py` — already only checks `nest.agent.md`
- **Do NOT modify** `services/init_service.py` — already only calls `agent_writer.generate()` for primary agent

### Project Structure Notes

- Template directory `src/nest/agents/templates/` will go from 3 files to 1 (`vscode.md.jinja`)
- `.github/agents/` directory in the repo will go from 3 files to 1 (`nest.agent.md` or `bmad-agent-epic-runner.md` + `nest.agent.md`)
- The `VSCodeAgentWriter` class becomes significantly smaller (~55 → ~25 lines of code)

### Previous Story Intelligence

From Story 6.5 (code review):
- **Error handling pattern:** Use try/except with descriptive messages; the 6.4 retrospective flagged missing I/O error handling — but this story only deletes code, so no new error handling needed
- **Test baseline:** 812 passed (post-6.5 code review), 54 deselected (e2e). After this story, expect ~812 non-e2e tests (no non-e2e tests are being removed) and ~51 e2e tests (3 e2e tests removed)
- **Lint/typecheck:** 6.5 was clean on Ruff + Pyright strict — maintain this standard
- **Commit convention:** `chore(agent)` scope for cleanup, or `feat(agent)!` if considered breaking (removing public methods)
- **Recommended commit:** `chore(agent): remove enricher and glossary agent templates and references`

### Git Intelligence

Recent commits show the project is on `main` at v0.3.1. Most recent work (6.1–6.5) built the AI pipeline. The codebase is stable with all tests passing. No conflicts expected from this cleanup story.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.6] — Full acceptance criteria and story statement
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6] — Epic scope: removal of enricher/glossary agent templates
- [Source: _bmad-output/project-context.md#Project Paths] — Current directory tree showing agent files to remove
- [Source: _bmad-output/project-context.md#Architecture & Dependency Injection] — Protocol-based DI (confirms AgentWriterProtocol is clean)
- [Source: _bmad-output/project-context.md#Testing Rules] — Test naming, E2E isolation requirements
- [Source: _bmad-output/project-context.md#Python Language Rules] — PEP 8, docstring style
- [Source: _bmad-output/project-context.md#Git Workflow] — Conventional commit format
- [Source: _bmad-output/implementation-artifacts/6-5-nest-config-ai-shell-rc-writer.md] — Previous story learnings, test baseline (812 passed)
- [Source: src/nest/agents/vscode_writer.py] — Methods to remove: render_enricher, generate_enricher, render_glossary, generate_glossary
- [Source: src/nest/cli/init_cmd.py#L89-97] — Enricher/glossary generation loop to remove
- [Source: src/nest/cli/sync_cmd.py#L446-460] — Agent prompt messages to remove
- [Source: src/nest/adapters/project_checker.py] — Confirms only nest.agent.md is checked (no changes needed)
- [Source: src/nest/services/doctor_service.py#L586-623] — Confirms only nest.agent.md is regenerated (no changes needed)
- [Source: tests/e2e/test_enrichment_e2e.py#L208-227] — E2E test to remove
- [Source: tests/e2e/test_glossary_e2e.py#L97-115] — E2E test to remove
- [Source: tests/e2e/test_glossary_e2e.py#L150-167] — E2E test to remove

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None — clean execution, no issues.

### Completion Notes List

- All 8 tasks completed. Pure deletion/cleanup story — no new code.
- 812 tests pass (same as 6.5 baseline — removed tests were E2E-marked, not counted in `not e2e` run).
- Ruff: all checks passed. Pyright: 0 errors, 0 warnings.
- `SyncResult.enrichment_needed` and `glossary_terms_discovered` fields intentionally retained (used by AI pipeline internals).

### File List

| File | Action |
|------|--------|
| `src/nest/agents/templates/enricher.md.jinja` | DELETED |
| `src/nest/agents/templates/glossary.md.jinja` | DELETED |
| `src/nest/agents/vscode_writer.py` | MODIFIED — removed 4 methods (`render_enricher`, `generate_enricher`, `render_glossary`, `generate_glossary`) |
| `src/nest/cli/init_cmd.py` | MODIFIED — removed enricher/glossary generation loop and standalone `agent_writer` instantiation |
| `src/nest/cli/sync_cmd.py` | MODIFIED — removed `@nest-enricher` and `@nest-glossary` prompt blocks from `_display_sync_summary()` |
| `src/nest/services/glossary_hints_service.py` | MODIFIED — updated 2 comments referencing "glossary agent" → "AI glossary" |
| `.github/agents/nest-enricher.agent.md` | DELETED |
| `.github/agents/nest-glossary.agent.md` | DELETED |
| `tests/e2e/test_enrichment_e2e.py` | MODIFIED — removed `test_enricher_agent_created_on_init`, updated module docstring |
| `tests/e2e/test_glossary_e2e.py` | MODIFIED — removed `test_glossary_agent_created_on_init` and `test_sync_output_shows_glossary_prompt`, updated module docstring |
| `_bmad-output/project-context.md` | MODIFIED — removed enricher/glossary from directory tree |
| `src/nest/core/models.py` | MODIFIED — updated `GlossaryHints` docstring "glossary agent" → "AI glossary generation" (code review fix) |

## Senior Developer Review (AI)

### Review Date
2026-03-05

### Reviewer
Claude Opus 4.6 (adversarial code review)

### Review Result
**APPROVED** — all ACs verified, 3 medium issues found and auto-fixed.

### Findings

| # | Severity | File | Description | Status |
|---|----------|------|-------------|--------|
| M1 | MEDIUM | `src/nest/core/models.py:243` | Stale docstring: `GlossaryHints` said "for the glossary agent" — updated to "for AI glossary generation" | FIXED |
| M2 | MEDIUM | `tests/e2e/test_enrichment_e2e.py:4` | Module docstring referenced "enricher agent creation" — removed stale phrase | FIXED |
| M3 | MEDIUM | `tests/e2e/test_glossary_e2e.py:1-5` | Module docstring referenced "glossary agent integration" and "agent template creation during init" — rewritten | FIXED |

### Validation
- 812 tests passed, 51 deselected (e2e)
- Ruff: all checks passed
- Pyright: 0 errors, 0 warnings, 0 informations
- All 8 ACs verified against implementation
- No remaining `nest-enricher`/`nest-glossary`/`enricher agent`/`glossary agent` references in src/ or tests/

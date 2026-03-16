# Story 6.8: Unified LLM Glossary Pipeline

Status: done

## Story

As a **user who syncs project documents**,
I want **Nest to extract and define glossary terms in a single LLM pass per document (instead of regex extraction → per-term LLM calls)**,
So that **the glossary captures all term types (not just abbreviations and proper nouns), the pipeline is simpler, and ~400 lines of regex/merge/threshold code are eliminated**.

## Business Context

This is the **eighth story in Epic 6** (Built-in AI Enrichment). It replaces the two-stage glossary pipeline introduced across Stories 5.2 and 6.3:

**Current flow (two-stage):**
```
changed files → GlossaryHintsService.extract_all() [regex: abbreviations + proper nouns]
             → merge_with_previous() [carry forward terms from unchanged files]
             → write_hints() [persist 00_GLOSSARY_HINTS.yaml]
             → AIGlossaryService.generate() [one LLM call per candidate term]
             → write glossary.md
```

**New flow (single-stage):**
```
changed files → AIGlossaryService.generate() [one LLM call per document/chunk]
             → dedup extracted terms against existing glossary.md rows
             → append new rows to glossary.md (sorted alphabetically)
```

**Why this is the right move:**
1. **Term coverage gap.** The regex approach only catches `[A-Z]{2,}` (abbreviations) and `CapitalizedMultiWord` (proper nouns). It structurally cannot discover lowercase domain terms like "sprint velocity", "runbook", "blast radius", or "change order". The LLM has no such blind spot.
2. **Accidental complexity.** `GlossaryHintsService` (416 lines), `CandidateTerm`/`GlossaryHints` models, `00_GLOSSARY_HINTS.yaml` intermediate file, occurrence thresholds, merge logic, and a hardcoded `GENERIC_TERM_FILTER` set of 40+ terms — all exist solely to pre-filter terms before the LLM. The LLM can make these decisions itself.
3. **Cost is acceptable.** Current flow: ~30 LLM calls × ~200 input tokens = ~6K tokens. New flow: ~50 calls × ~10K input tokens = ~500K tokens. On gpt-4o-mini at $0.15/1M input tokens, that's ~$0.08 per full sync. Incremental syncs (only changed files) are much cheaper.

**Key design principles:**
- **Source(s) column preserved.** Each term row in `glossary.md` gets the filename that produced it. No schema migration needed.
- **Incremental.** Only changed/new files (already tracked by checksum engine) are sent to the LLM. Existing glossary rows are never modified or deleted.
- **Human-edit safe.** Existing definitions in `glossary.md` are preserved verbatim.
- **Chunking for large documents.** Documents exceeding ~40K tokens (~160K chars) are split on paragraph boundaries.
- **Backward compatible.** On first sync after upgrade, if `00_GLOSSARY_HINTS.yaml` exists, it is deleted (it was an intermediate cache, not user-facing).
- **`--no-ai` flag** continues to skip all AI work including glossary generation.
- **Graceful degradation.** No API key → no glossary generated, no error.

## Acceptance Criteria

### AC1: Single-Pass Document-Based Glossary Extraction

**Given** sync completes processing and AI is configured (API key detected)
**When** changed/new context files exist
**Then** `AIGlossaryService.generate()` is called with the list of changed file paths and the context directory
**And** for each file (or chunk), a single LLM call extracts AND defines all glossary-worthy terms
**And** results are parsed from Markdown table row format: `| Term | Category | Definition |`
**And** new terms are appended to `glossary.md` with Source(s) populated from the filename

### AC2: Source(s) Column Preserved

**Given** the current `glossary.md` uses a 4-column schema `| Term | Category | Definition | Source(s) |`
**When** new terms are extracted from a file
**Then** the Source(s) column is populated with the filename that produced the term
**And** existing rows retain their original Source(s) values
**And** no schema migration is needed

### AC3: Human Edits Preserved

**Given** `glossary.md` already exists with human-edited definitions
**When** AI glossary generation runs
**Then** existing definitions are preserved verbatim (never modified or deleted)
**And** only new terms (not already in the glossary, case-insensitive) are added
**And** the table remains sorted alphabetically by Term

### AC4: Incremental Processing — Only Changed Files

**Given** some files have changed since last sync and others have not
**When** AI glossary generation runs
**Then** only changed/new files are sent to the LLM
**And** terms from unchanged files that are already in `glossary.md` are preserved
**And** no unnecessary LLM calls are made

### AC5: No Changes = No LLM Calls

**Given** no files have changed since last sync
**When** AI glossary generation runs
**Then** no LLM calls are made
**And** `glossary.md` is not modified

### AC6: Large Document Chunking

**Given** a context file exceeds ~40K tokens (~160K characters)
**When** the file is processed for glossary extraction
**Then** it is split into chunks on paragraph boundaries (double-newline)
**And** each chunk is sent as a separate LLM call
**And** terms extracted from multiple chunks of the same file are deduplicated (keep first definition seen)

### AC7: Cross-Chunk and Cross-File Dedup

**Given** the same term appears in multiple files or chunks
**When** all extraction results are collected
**Then** the term appears only once in the glossary
**And** the first definition seen is used
**And** dedup is case-insensitive

### AC8: Graceful Per-File Failure

**Given** the LLM call fails for a specific file or chunk
**When** the error is caught
**Then** that file/chunk is skipped
**And** a warning is logged
**And** other files continue processing
**And** the `terms_failed` count is incremented

### AC9: No AI = No Glossary Generation (No Error)

**Given** AI is NOT configured (no API key in environment)
**When** sync runs
**Then** no `glossary.md` is generated or modified
**And** no `00_GLOSSARY_HINTS.yaml` is generated (the deterministic Phase 1 is removed)
**And** no error is raised

### AC10: `--no-ai` Flag Skips Glossary Generation

**Given** the `--no-ai` flag is passed to `nest sync`
**When** sync runs
**Then** AI glossary generation is skipped
**And** existing `glossary.md` is not modified

### AC11: Legacy Hints File Cleanup

**Given** `00_GLOSSARY_HINTS.yaml` exists from a previous sync
**When** the first new-style sync runs
**Then** `00_GLOSSARY_HINTS.yaml` is deleted
**And** no error is raised if the file does not exist

### AC12: Unified Prompt Design

**Given** the system prompt for glossary extraction
**When** constructing each LLM call
**Then** the prompt instructs the model to extract every project-specific term from the document
**And** the prompt specifies categories: Acronym, Organization, Product/Platform, Domain Term, Role, Standard, System
**And** the prompt requires output in `| Term | Category | Definition |` table row format (no header, no extra text)
**And** the prompt excludes universally known terms (the LLM decides, no hardcoded filter list)
**And** the prompt forbids pipe characters within cell values
**And** the prompt supports an optional project context block (prepended when available)

### AC13: First-Run Glossary Creation

**Given** `glossary.md` does not yet exist
**When** AI glossary generation runs for the first time
**Then** the file is created with the standard header and table markers
**And** all qualifying terms from the first run are added

### AC14: GlossaryHintsService Fully Removed

**Given** all code changes are complete
**When** searching the codebase for `GlossaryHintsService`, `glossary_hints_service`, `GLOSSARY_HINTS_FILE`, `CandidateTerm`, or `GlossaryHints`
**Then** zero matches exist in `src/`
**And** zero matches exist in `tests/`

### AC15: Token Usage Preserved

**Given** AI glossary generation runs
**When** the sync summary is displayed
**Then** glossary token usage continues to be reported in the aggregated `AI tokens:` line
**And** `ai_glossary_terms_added`, `ai_glossary_prompt_tokens`, `ai_glossary_completion_tokens` fields are populated in `SyncResult`

### AC16: All Tests Pass

**Given** all unit, integration, and E2E tests
**When** the changes are complete
**Then** `pytest -m "not e2e"` passes with zero failures
**And** `ruff check src/ tests/` is clean
**And** `pyright` reports zero errors

## Tasks / Subtasks

### Phase 1: New AI Glossary Service

#### Task 1: Update `AIGlossaryService.generate()` Signature (AC: 1, 4, 5)

- [x] 1.1: Change `generate()` signature from `generate(terms: GlossaryHints, glossary_path: Path)` to `generate(changed_files: list[Path], context_dir: Path, glossary_path: Path) -> AIGlossaryResult`
- [x] 1.2: The service reads file content directly from `changed_files` via `self._fs.read_text()`
- [x] 1.3: If `changed_files` is empty, return `AIGlossaryResult()` immediately (AC5)
- [x] 1.4: Remove the import of `CandidateTerm` and `GlossaryHints` from the service
- **File:** `src/nest/services/ai_glossary_service.py`

#### Task 2: Add Document Chunking (AC: 6)

- [x] 2.1: Add private method `_chunk_content(content: str, max_chars: int = 160_000) -> list[str]` that splits on double-newline paragraph boundaries
- [x] 2.2: If content length ≤ `max_chars`, return `[content]` (single chunk, no split)
- [x] 2.3: Accumulate paragraphs until adding the next would exceed `max_chars`, then start a new chunk
- [x] 2.4: Never split mid-paragraph — a single paragraph larger than `max_chars` goes in its own chunk
- **File:** `src/nest/services/ai_glossary_service.py`

#### Task 3: Replace Prompt Constants (AC: 12)

- [x] 3.1: Replace `GLOSSARY_SYSTEM_PROMPT` with the unified extraction+definition prompt:
  ```python
  GLOSSARY_SYSTEM_PROMPT = (
      "You are a technical glossary assistant. Given a project document (or a section "
      "of one), extract every term that a consultant or developer joining this project "
      "would need to look up.\n\n"
      "{PROJECT_CONTEXT_BLOCK}\n\n"
      "Extract terms into this EXACT format, one per line, no header row, no other text:\n"
      "| <Term> | <Category> | <Definition> |\n\n"
      "Categories: Acronym, Organization, Product/Platform, Domain Term, Role, "
      "Standard, System\n\n"
      "Rules:\n"
      "- INCLUDE: project-specific acronyms, client/vendor/partner names, named "
      "products and platforms, industry-specific standards, regulatory bodies, "
      "custom roles, integration systems, and any term whose meaning in THIS "
      "project would not be obvious.\n"
      "- EXCLUDE: universally known technical terms (e.g., API, HTTP, JSON, Agile, "
      "CI/CD). The test: would a senior technical consultant already know this "
      "without project context? If yes, exclude it.\n"
      "- Definitions must be one sentence, referencing the project context where possible.\n"
      "- For acronyms, include the expansion in the definition.\n"
      "- Do NOT use pipe characters (|) within any cell value.\n"
      "- If no glossary-worthy terms are found, output nothing."
  )
  ```
- [x] 3.2: Add `_build_system_prompt(project_context: str | None = None) -> str` that inserts or removes the project context block
- [x] 3.3: The user prompt becomes the document content (or chunk content) — no more `_build_user_prompt(CandidateTerm)`
- [x] 3.4: Remove the old `_build_user_prompt()` method entirely
- [x] 3.5: Update `VALID_CATEGORIES` to the new set: `{"Acronym", "Organization", "Product/Platform", "Domain Term", "Role", "Standard", "System"}`
- **File:** `src/nest/services/ai_glossary_service.py`

#### Task 4: Update Response Parsing (AC: 1, 7)

- [x] 4.1: Replace `_parse_response()` (currently parses 3 key-value lines) with `_parse_table_rows(text: str) -> list[tuple[str, str, str]]` that returns list of (term, category, definition) tuples
- [x] 4.2: Split each line on `|`, extract columns 1/2/3 (Term/Category/Definition), strip whitespace
- [x] 4.3: Skip lines that don't have at least 4 pipe-delimited segments (malformed)
- [x] 4.4: Skip lines where first column is "Term" or starts with "---" (header/separator rows)
- [x] 4.5: Validate category against `VALID_CATEGORIES` — if invalid, default to "Domain Term"
- [x] 4.6: Sanitize definitions via existing `_sanitize_definition()` method
- [x] 4.7: Remove the old `_parse_response()` method
- **File:** `src/nest/services/ai_glossary_service.py`

#### Task 5: Update Core Generate Loop (AC: 1, 2, 7, 8, 15)

- [x] 5.1: Implement the new `generate()` body:
  ```
  For each file in changed_files:
    1. Read content via self._fs.read_text(file_path)
    2. Chunk content via _chunk_content()
    3. For each chunk:
       a. Call self._llm.complete(system_prompt, chunk_content)
       b. If result is None → log warning, increment terms_failed, continue
       c. Parse response via _parse_table_rows()
       d. For each (term, category, definition):
          - If term.lower() already in existing_terms or already_extracted → skip
          - Build row: f"| {term} | {category} | {definition} | {filename} |"
          - Add to new_rows, add term.lower() to already_extracted set
       e. Accumulate token counts
    4. Increment files_processed, chunks_processed
  ```
- [x] 5.2: Load existing glossary once at start via `_load_existing_glossary()` (method already exists, no change needed)
- [x] 5.3: Write glossary at end via `_write_glossary()` (method already exists, no change needed)
- [x] 5.4: Build `AIGlossaryResult` with updated fields and return
- **File:** `src/nest/services/ai_glossary_service.py`

#### Task 6: Update `AIGlossaryResult` Model (AC: 15)

- [x] 6.1: Remove `terms_skipped_generic: int = 0` (LLM handles exclusion implicitly)
- [x] 6.2: Add `files_processed: int = 0`
- [x] 6.3: Add `chunks_processed: int = 0`
- [x] 6.4: Keep `terms_added`, `terms_skipped_existing`, `terms_failed`, `prompt_tokens`, `completion_tokens`
- **File:** `src/nest/core/models.py` (lines 208-220)

### Phase 2: Update Sync Orchestration

#### Task 7: Simplify `sync_service.py` Glossary Flow (AC: 1, 4, 11)

- [x] 7.1: Remove steps 9-13 from `sync()` method (lines 258-280):
  - Step 9: Load old glossary hints
  - Step 10: Determine changed context files for glossary
  - Step 11: Extract candidate glossary terms
  - Step 12: Merge with previous glossary hints
  - Step 13: Write new glossary hints
- [x] 7.2: Replace with: collect changed file paths from `new_metadata` (files whose content_hash differs from `old_hints`)
- [x] 7.3: Pass changed file paths to `AIGlossaryService.generate()` via the updated `_run_glossary()` helper
- [x] 7.4: Add legacy hints cleanup: if `.nest/00_GLOSSARY_HINTS.yaml` exists, delete it (AC11)
- [x] 7.5: Update `has_glossary_work` check from `len(merged_glossary.terms) > 0` to `len(changed_context_files) > 0`
- **File:** `src/nest/services/sync_service.py`

#### Task 8: Remove `GlossaryHintsService` Dependency from SyncService (AC: 14)

- [x] 8.1: Remove `glossary: GlossaryHintsService` parameter from `SyncService.__init__()`
- [x] 8.2: Remove `self._glossary` attribute
- [x] 8.3: Remove `from nest.services.glossary_hints_service import GlossaryHintsService` import
- [x] 8.4: Remove `GlossaryHints` from TYPE_CHECKING imports
- [x] 8.5: Remove `GLOSSARY_HINTS_FILE` from paths import
- **File:** `src/nest/services/sync_service.py`

#### Task 9: Update `_run_glossary()` Helper (AC: 1)

- [x] 9.1: Change signature from `_run_glossary(self, merged_glossary: GlossaryHints, context_dir: Path)` to `_run_glossary(self, changed_files: list[Path], context_dir: Path)`
- [x] 9.2: Call `self._ai_glossary.generate(changed_files, context_dir, glossary_file_path)` with updated signature
- **File:** `src/nest/services/sync_service.py`

#### Task 10: Update `SyncResult` Model (AC: 15)

- [x] 10.1: Remove `glossary_terms_discovered: int = 0` from `SyncResult` (terms are no longer "discovered" separately)
- [x] 10.2: Remove the `glossary_terms_discovered=glossary_terms_discovered` assignment in `sync()` return
- **File:** `src/nest/core/models.py` (line 175)
- **File:** `src/nest/services/sync_service.py` (line 380, 394)

#### Task 11: Update DI Factory in `sync_cmd.py` (AC: 14)

- [x] 11.1: Remove `from nest.services.glossary_hints_service import GlossaryHintsService` import (line 28)
- [x] 11.2: Remove `GlossaryHintsService(filesystem=..., project_root=...)` instantiation (lines 155-158)
- [x] 11.3: Remove `glossary=...` kwarg from `SyncService(...)` constructor call
- **File:** `src/nest/cli/sync_cmd.py`

### Phase 3: Remove Dead Code

#### Task 12: Delete `GlossaryHintsService` (AC: 14)

- [x] 12.1: Delete `src/nest/services/glossary_hints_service.py` (416 lines)
- **File:** `src/nest/services/glossary_hints_service.py` — DELETE

#### Task 13: Remove `CandidateTerm` and `GlossaryHints` Models (AC: 14)

- [x] 13.1: Delete `CandidateTerm` class from `src/nest/core/models.py` (lines 224-240)
- [x] 13.2: Delete `GlossaryHints` class from `src/nest/core/models.py` (lines 243-249)
- [x] 13.3: Remove any imports of these models across the codebase
- **File:** `src/nest/core/models.py`

#### Task 14: Remove `GLOSSARY_HINTS_FILE` Path Constant (AC: 14)

- [x] 14.1: Remove `GLOSSARY_HINTS_FILE = "00_GLOSSARY_HINTS.yaml"` from `src/nest/core/paths.py` (line 16)
- [x] 14.2: Remove any remaining imports of `GLOSSARY_HINTS_FILE` across the codebase
- **File:** `src/nest/core/paths.py`

#### Task 15: Clean Up Remaining Imports (AC: 14)

- [x] 15.1: Search `src/` for any remaining references to `GlossaryHintsService`, `CandidateTerm`, `GlossaryHints`, `GLOSSARY_HINTS_FILE`, `glossary_hints_service`
- [x] 15.2: Remove all found references
- [x] 15.3: Verify with: `grep -r "GlossaryHintsService\|glossary_hints_service\|GLOSSARY_HINTS_FILE\|CandidateTerm\|GlossaryHints" src/` → zero matches

### Phase 4: Update Tests

#### Task 16: Rewrite `test_ai_glossary_service.py` (AC: 1, 2, 3, 5, 6, 7, 8, 12, 13)

- [x] 16.1: Rewrite tests for new `generate()` signature — accepts `list[Path]` of changed files
- [x] 16.2: Test: single file extraction (mock LLM returns table rows, verify glossary rows created)
- [x] 16.3: Test: multiple files (each file → separate LLM call, all terms merged)
- [x] 16.4: Test: chunked large file (verify file split into chunks, each chunk → LLM call, terms deduplicated across chunks)
- [x] 16.5: Test: dedup against existing glossary (existing terms skipped, new terms added)
- [x] 16.6: Test: malformed LLM output (lines without enough pipes skipped gracefully)
- [x] 16.7: Test: empty document (no LLM call made for empty content)
- [x] 16.8: Test: LLM call failure (returns None → terms_failed incremented, other files continue)
- [x] 16.9: Test: Source(s) column populated with filename
- [x] 16.10: Test: categories validated and defaulted to "Domain Term" for unknown
- [x] 16.11: Test: system prompt construction with and without project context
- [x] 16.12: Test: _chunk_content() boundary conditions (under limit, exact limit, over limit, single huge paragraph)
- [x] 16.13: Test: token counts accumulated correctly across files and chunks
- [x] 16.14: Test: no changed files → immediate return with empty result
- **File:** `tests/services/test_ai_glossary_service.py` — REWRITE

#### Task 17: Delete `test_glossary_hints_service.py` (AC: 14)

- [x] 17.1: Delete `tests/services/test_glossary_hints_service.py` (461 lines)
- **File:** `tests/services/test_glossary_hints_service.py` — DELETE

#### Task 18: Update `test_sync_service.py` (AC: 14, 16)

- [x] 18.1: Remove `from nest.services.glossary_hints_service import GlossaryHintsService` import
- [x] 18.2: Remove `Mock(spec=GlossaryHintsService)` from `mock_deps` fixture (line 54)
- [x] 18.3: Remove `glossary=...` kwarg from SyncService construction in fixture
- [x] 18.4: Update or remove `test_glossary_terms_discovered_in_sync_result` (line 200) — field no longer exists
- [x] 18.5: Update `test_glossary_hints_service_called_during_sync` (line 233) — replace with test that changed files are passed to `AIGlossaryService.generate()`
- [x] 18.6: Update any other tests that assert on `glossary_terms_discovered` in SyncResult
- [x] 18.7: Update glossary-related sync tests to mock `AIGlossaryService` instead of `GlossaryHintsService`
- **File:** `tests/services/test_sync_service.py`

#### Task 19: Update `test_sync_flags.py` (AC: 14, 16)

- [x] 19.1: Remove `from nest.services.glossary_hints_service import GlossaryHintsService` import
- [x] 19.2: Update all 9 fixtures that create `Mock(spec=GlossaryHintsService)`:
  - Remove `glossary_mock` or rename to reflect new architecture
  - Remove `glossary=mock_glossary` kwarg from `SyncService(...)` constructor calls
- [x] 19.3: Verify all existing sync flag tests still pass with the fixture changes
- **File:** `tests/integration/test_sync_flags.py`

#### Task 20: Update `test_sync_index_integration.py` (AC: 14, 16)

- [x] 20.1: Remove `from nest.services.glossary_hints_service import GlossaryHintsService` import
- [x] 20.2: Remove or update `GlossaryHintsService(...)` instantiation at line 83
- [x] 20.3: Remove `glossary=...` kwarg from `SyncService(...)` constructor call
- **File:** `tests/integration/test_sync_index_integration.py`

#### Task 21: Update E2E Glossary Test (AC: 1, 11, 14)

- [x] 21.1: Rewrite `test_sync_generates_glossary_hints` → `test_sync_glossary_hints_file_not_generated`:
  - After sync, assert `.nest/00_GLOSSARY_HINTS.yaml` does NOT exist
  - This verifies the old hints pipeline is fully removed
- [x] 21.2: Rewrite `test_glossary_hints_excluded_from_index` → keep or remove (hints file no longer generated, so the exclusion test is moot)
- [x] 21.3: Update `test_glossary_hints_incremental` → `test_glossary_incremental_file_based`:
  - Verify that only changed files trigger LLM calls on second sync
  - (This test requires AI env vars — gate with `skip_without_ai` marker, or test with mock)
- [x] 21.4: Add `test_legacy_glossary_hints_deleted_on_first_sync`:
  - Manually create `.nest/00_GLOSSARY_HINTS.yaml` before sync
  - Run sync
  - Assert the file no longer exists (AC11)
- **File:** `tests/e2e/test_glossary_e2e.py` — REWRITE

### Phase 5: Verification

#### Task 22: Full Verification (AC: 16)

- [x] 22.1: Run `pytest tests/services/test_ai_glossary_service.py -v` — all new tests pass
- [x] 22.2: Run `pytest tests/services/test_sync_service.py -v` — all sync tests pass
- [x] 22.3: Run `pytest tests/integration/ -v` — all integration tests pass
- [x] 22.4: Run `pytest tests/ -m "not e2e" -v` — full non-E2E suite passes
- [x] 22.5: Run `ruff check src/ tests/` — zero lint errors
- [x] 22.6: Run `pyright` — zero type errors
- [x] 22.7: Run `grep -r "GlossaryHintsService\|glossary_hints_service\|GLOSSARY_HINTS_FILE\|CandidateTerm\|GlossaryHints" src/ tests/` — zero matches (AC14)

## Dev Notes

### Architecture Compliance

- **Adapter layer**: `LLMProviderProtocol` interface unchanged. `OpenAIAdapter` (and future `AzureOpenAIAdapter` from Story 6.7) continue to work identically — the protocol takes `system_prompt` and `user_prompt` strings.
- **Protocol-based DI**: `AIGlossaryService` constructor unchanged — still takes `LLMProviderProtocol` and `FileSystemProtocol`.
- **DI factory**: `create_sync_service()` in `src/nest/cli/sync_cmd.py` is the composition root. `GlossaryHintsService` wiring is removed; `AIGlossaryService` wiring stays as-is.
- **Threading**: The `ThreadPoolExecutor(max_workers=2)` pattern in `sync_service.py` for parallel enrichment+glossary is preserved. The glossary task now receives file paths instead of `GlossaryHints`.

### File Impact Summary

| File | Action | Estimated Lines Changed |
|------|--------|------------------------|
| `src/nest/services/ai_glossary_service.py` | Rewrite | ~200 (of 268) |
| `src/nest/services/glossary_hints_service.py` | **DELETE** | -416 |
| `src/nest/services/sync_service.py` | Modify | ~50 |
| `src/nest/cli/sync_cmd.py` | Modify | ~10 |
| `src/nest/core/models.py` | Modify | ~40 (remove 3 classes/fields, update 1) |
| `src/nest/core/paths.py` | Modify | -1 line |
| `tests/services/test_ai_glossary_service.py` | Rewrite | ~500 |
| `tests/services/test_glossary_hints_service.py` | **DELETE** | -461 |
| `tests/services/test_sync_service.py` | Modify | ~100 |
| `tests/integration/test_sync_flags.py` | Modify | ~30 |
| `tests/integration/test_sync_index_integration.py` | Modify | ~10 |
| `tests/e2e/test_glossary_e2e.py` | Rewrite | ~80 |

**Net code reduction: ~400+ lines removed** (mostly `glossary_hints_service.py` and its tests)

### Token Cost Analysis

| Scenario | Current (per-term) | New (per-document) |
|----------|-------------------|-------------------|
| First sync, 10 files, ~30 terms | 30 calls × ~200 tokens = 6K | 10 calls × ~10K tokens = 100K |
| First sync, 50 files, ~100 terms | 100 calls × ~200 tokens = 20K | 50 calls × ~10K tokens = 500K |
| Incremental sync, 3 changed files | ~8 calls × ~200 tokens = 1.6K | 3 calls × ~10K tokens = 30K |
| gpt-4o-mini cost (50 files) | ~$0.003 | ~$0.075 |

Token usage is higher but well within acceptable range for cheap models.

### Decisions Made

1. **Source(s) column**: Kept. Populated with filename. No migration.
2. **Project context**: Optional. If `project-context.md` or similar exists, prepend to prompt. Don't block on this mechanism.
3. **Chunk size**: ~40K tokens (~160K chars), split on `\n\n` paragraph boundaries.
4. **Incremental strategy**: Only changed/new files sent to LLM (tracked by checksum engine). Dedup post-hoc against existing glossary.md.
5. **Term removal policy**: Append-only. Terms from deleted files remain in glossary.
6. **`00_GLOSSARY_HINTS.yaml` cleanup**: Delete on first sync if exists.
7. **Category set update**: `Abbreviation, Stakeholder, Domain Term, Project Name, Tool/System, Other` → `Acronym, Organization, Product/Platform, Domain Term, Role, Standard, System` (richer taxonomy for LLM-based extraction).

### Relationship to Story 6.7

Story 6.7 (Azure OpenAI Support & AI E2E Tests) is at `ready-for-dev`. If 6.7 is developed first:
- 6.7's E2E tests (`test_ai_glossary_e2e.py`) will test the old per-term pipeline
- After 6.8 lands, those E2E tests need updating to match the new per-document flow

If 6.8 is developed first:
- 6.7's E2E tests can be written against the new pipeline directly
- Recommended approach to avoid rework

### Dependencies

- **Story 6.3** (AI Glossary Generation in Sync) — code being replaced
- **Story 5.2** (Glossary Agent Integration) — `GlossaryHintsService` and models being deleted
- **No dependency on 6.7** — can be developed in parallel

## Dev Agent Record

### Implementation Plan

Story 6.8 unified the two-stage glossary pipeline (regex extraction → per-term LLM) into a single-stage per-document LLM pipeline. The bulk of implementation was already in place from prior work sessions. This session resolved:

1. **Syntax error fix** in `tests/services/test_ai_glossary_service.py` — literal `\x27` escape sequences (line 586) replaced with proper Python single-quote strings.
2. **Chunking test fix** — `test_chunked_file_dedup_across_chunks` was producing 202 chars of content against a 160,000 char limit so no chunking occurred. Patched `_chunk_content` via `unittest.mock.patch.object` to force two-chunk behavior.
3. **Stale metadata test fix** — `test_excludes_master_index_and_hints` in `test_metadata_service.py` still expected `00_GLOSSARY_HINTS.yaml` exclusion from `extract_all()`, but the metadata service no longer filters that file (correctly, since it's been removed from the system). Updated test to match current exclusion set (`00_MASTER_INDEX.md`, `00_INDEX_HINTS.yaml` only). Also updated `test_glossary_md_included_in_index` to remove stale hints file reference.
4. **Lint cleanup** — removed unused imports (`DEFAULT_MAX_CHARS`, `GLOSSARY_SYSTEM_PROMPT`) from test file.

### Completion Notes

- All 22 tasks (82 subtasks) complete across 5 phases
- `pytest tests/ -m "not e2e"`: 788 passed, 0 failed
- `ruff check src/ tests/`: All checks passed
- `pyright`: 0 errors, 0 warnings, 0 informations
- Dead code grep (`GlossaryHintsService`, `CandidateTerm`, `GlossaryHints`, `GLOSSARY_HINTS_FILE`): zero matches in `src/` and `tests/`
- Senior review remediation pass completed:
  - Change detection hardened by incorporating full file content into metadata hash
  - `glossary.md` excluded from metadata scan to prevent self-triggered glossary AI work
  - Optional project context now passed through sync into glossary prompt construction
  - Added missing incremental glossary E2E coverage (AI-key gated)

## Senior Developer Review (AI)

### Outcome

Changes Requested items addressed. All previously reported HIGH and MEDIUM findings were fixed in code and tests.

### Verification

- Focused regression suite passed: `pytest tests/services/test_metadata_service.py tests/services/test_sync_service.py tests/e2e/test_glossary_e2e.py -q`
- Result: `96 passed, 1 skipped`

## File List

- `src/nest/services/metadata_service.py` — Content hash now includes full file body; excludes `glossary.md` from metadata extraction
- `src/nest/services/ai_glossary_service.py` — `generate()` now accepts optional project context for prompt composition
- `src/nest/services/sync_service.py` — Loads optional project context and passes to AI glossary service
- `tests/services/test_metadata_service.py` — Updated hash tests for content-aware hashing; added glossary exclusion assertion
- `tests/services/test_sync_service.py` — Added regression test for project-context forwarding to glossary generation
- `tests/e2e/test_glossary_e2e.py` — Added incremental glossary behavior test (AI-key gated)

## Change Log

- 2026-03-10: Fixed test failures and lint issues to complete story 6.8 (syntax error in test_ai_glossary_service.py, stale test in test_metadata_service.py, unused imports)
- 2026-03-10: Applied code review fixes for Story 6.8 (change-detection hardening, glossary self-trigger prevention, project-context prompt wiring, missing incremental E2E coverage)

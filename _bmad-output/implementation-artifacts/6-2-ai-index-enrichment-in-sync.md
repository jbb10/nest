# Story 6.2: AI Index Enrichment in Sync

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user who has synced project documents**,
I want **Nest to automatically generate short descriptions for each file in the master index during sync**,
So that **the index is immediately useful for finding relevant documents without manually running an agent**.

## Business Context

This is the **second story in Epic 6** (Built-in AI Enrichment). Story 6.1 created the `LLMProviderProtocol`, `OpenAIAdapter`, and `create_llm_provider()` factory. This story uses that foundation to perform AI-powered index enrichment during `nest sync`.

Today, after sync, users must manually invoke `@nest-enricher` in VS Code Copilot Chat to populate file descriptions in `00_MASTER_INDEX.md`. This story automates that — if API keys are detected in the environment, Nest generates ≤15-word descriptions for each file during sync, writing them directly into the index table.

**Key design principles:**
- AI is **opportunistic, never mandatory**. If no API key → index is produced without descriptions (same behavior as pre-Epic-6).
- **Incremental**: only files with changed or missing `content_hash` trigger LLM calls. Unchanged files carry forward their existing descriptions.
- **Graceful degradation**: if an LLM call fails for one file, that file gets an empty description. Sync continues, remaining files still get enriched.
- The `--no-ai` flag lets users skip AI enrichment entirely while still carrying forward previously-generated descriptions.

## Acceptance Criteria

### AC1: AI Enrichment During Sync

**Given** sync completes processing and AI is configured (API key detected in environment)
**When** the index generation phase runs
**Then** an `AIEnrichmentService` is called with the metadata hints (`00_INDEX_HINTS.yaml` data) for files needing descriptions
**And** for each file with an empty or changed description, a single LLM call generates a ≤15-word description
**And** the generated descriptions are written into the `00_MASTER_INDEX.md` table

### AC2: Incremental — Unchanged Files Skip LLM

**Given** a file's `content_hash` has NOT changed since last sync
**When** AI enrichment runs
**Then** the existing description is carried forward (no LLM call made)
**And** tokens are not wasted on unchanged files

### AC3: Changed Files Get Fresh Descriptions

**Given** a file's `content_hash` HAS changed since last sync
**When** AI enrichment runs
**Then** the old description is discarded
**And** a new LLM call generates a fresh description based on updated hints

### AC4: New Files Get Descriptions

**Given** a file is brand new (not in previous index)
**When** AI enrichment runs
**Then** an LLM call generates a description for the new file

### AC5: Graceful Per-File Failure

**Given** the LLM call fails for a specific file
**When** the error is caught
**Then** the description for that file remains empty (same as unenriched state)
**And** a warning is logged
**And** sync continues processing remaining files

### AC6: No AI = No Enrichment (No Error)

**Given** AI is NOT configured (no API key in environment)
**When** sync runs
**Then** the index is generated without descriptions (same behavior as before Epic 6)
**And** no error or warning about AI is shown

### AC7: `--no-ai` Flag Skips Enrichment

**Given** the `--no-ai` flag is passed to `nest sync`
**When** sync runs with AI configured
**Then** AI enrichment is skipped entirely
**And** existing descriptions from previous syncs are still carried forward via content hash logic

### AC8: Prompt Design

**Given** the system prompt for index enrichment
**When** constructing the LLM call
**Then** the prompt instructs the model to write a description of at most 15 words
**And** the prompt provides the file's headings, first paragraph, and line count from the hints
**And** the prompt forbids pipe characters in the output (Markdown table safety)

### AC9: All Tests Pass

**Given** all unit and integration tests
**When** the changes are complete
**Then** all tests pass with LLM calls mocked via `LLMProviderProtocol` test doubles
**And** no regressions in existing test suite

## Tasks / Subtasks

### Task 1: Create `AIEnrichmentService` (AC: 1, 2, 3, 4, 5, 8)
- [x] 1.1: Create `src/nest/services/ai_enrichment_service.py` with `AIEnrichmentService` class
- [x] 1.2: Constructor takes `llm_provider: LLMProviderProtocol`
- [x] 1.3: Implement `enrich(files: list[FileMetadata], old_descriptions: dict[str, str], old_hints: dict[str, str]) -> AIEnrichmentResult`:
  - For each file, determine if LLM call is needed:
    - If `file.path` exists in `old_hints` AND `old_hints[file.path] == file.content_hash` AND `old_descriptions.get(file.path, "")` is non-empty → carry forward (no LLM call)
    - Otherwise → LLM call needed
  - For files needing LLM call: call `llm_provider.complete(system_prompt, user_prompt)`
  - Build `user_prompt` from `FileMetadata`: path, headings, first_paragraph, lines, table_columns
  - If LLM returns `None` → empty description for that file, log warning
  - If LLM returns text → sanitize (strip pipe chars, strip whitespace, truncate to 15 words max)
  - Aggregate token usage across all calls
  - Return `AIEnrichmentResult` with `descriptions: dict[str, str]` and `prompt_tokens: int`, `completion_tokens: int`, `files_enriched: int`
- [x] 1.4: Define system prompt constant:
  ```python
  ENRICHMENT_SYSTEM_PROMPT = (
      "You are a technical documentation assistant. "
      "Write a concise description of the given document in at most 15 words. "
      "Output ONLY the description text, nothing else. "
      "Do NOT use pipe characters (|) in your output. "
      "Do NOT include quotes around the description."
  )
  ```
- [x] 1.5: Build user prompt per file:
  ```python
  def _build_user_prompt(self, file: FileMetadata) -> str:
      parts = [f"File: {file.path}", f"Lines: {file.lines}"]
      if file.headings:
          headings_text = ", ".join(h.text for h in file.headings[:5])
          parts.append(f"Headings: {headings_text}")
      if file.first_paragraph:
          parts.append(f"Content preview: {file.first_paragraph}")
      if file.table_columns:
          parts.append(f"Table columns: {', '.join(file.table_columns)}")
      return "\n".join(parts)
  ```
- [x] 1.6: Sanitize LLM output — strip pipe chars, strip quotes/whitespace, limit to 15 words:
  ```python
  def _sanitize_description(self, text: str) -> str:
      sanitized = text.replace("|", "-").strip().strip('"').strip("'").strip()
      words = sanitized.split()
      if len(words) > 15:
          sanitized = " ".join(words[:15])
      return sanitized
  ```

### Task 2: Add `AIEnrichmentResult` Model (AC: 1)
- [x] 2.1: Add `AIEnrichmentResult` to `src/nest/core/models.py`:
  ```python
  class AIEnrichmentResult(BaseModel):
      """Result of AI index enrichment.

      Attributes:
          descriptions: Dict mapping file path to generated description.
          prompt_tokens: Total prompt tokens used across all LLM calls.
          completion_tokens: Total completion tokens used across all LLM calls.
          files_enriched: Number of files that received AI descriptions.
          files_skipped: Number of files that carried forward existing descriptions.
          files_failed: Number of files where LLM call failed.
      """

      descriptions: dict[str, str] = Field(default_factory=dict)
      prompt_tokens: int = 0
      completion_tokens: int = 0
      files_enriched: int = 0
      files_skipped: int = 0
      files_failed: int = 0
  ```

### Task 3: Update `SyncResult` Model (AC: 1)
- [x] 3.1: Add AI token fields to `SyncResult` in `src/nest/core/models.py`:
  ```python
  # Add to existing SyncResult:
  ai_prompt_tokens: int = 0
  ai_completion_tokens: int = 0
  ai_files_enriched: int = 0
  ```

### Task 4: Integrate AI Enrichment into `SyncService` (AC: 1, 2, 3, 4, 6)
- [x] 4.1: Add optional `ai_enrichment: AIEnrichmentService | None = None` parameter to `SyncService.__init__()`:
  ```python
  def __init__(
      self,
      discovery: DiscoveryService,
      output: OutputMirrorService,
      manifest: ManifestService,
      orphan: OrphanService,
      index: IndexService,
      metadata: MetadataExtractorService,
      glossary: GlossaryHintsService,
      project_root: Path,
      error_logger: logging.Logger | logging.LoggerAdapter[logging.Logger] | None = None,
      ai_enrichment: "AIEnrichmentService | None" = None,
  ) -> None:
  ```
  Store as `self._ai_enrichment = ai_enrichment`
- [x] 4.2: In `sync()` method, after step 6 (load old descriptions) and step 8 (write new hints), but before step 14 (generate index), insert AI enrichment:
  ```python
  # AI enrichment (between steps 8 and 14 in current flow)
  ai_prompt_tokens = 0
  ai_completion_tokens = 0
  ai_files_enriched = 0
  
  if self._ai_enrichment is not None:
      ai_result = self._ai_enrichment.enrich(
          new_metadata, old_descriptions, old_hints
      )
      # Merge AI descriptions into old_descriptions for index generation
      old_descriptions.update(ai_result.descriptions)
      ai_prompt_tokens = ai_result.prompt_tokens
      ai_completion_tokens = ai_result.completion_tokens
      ai_files_enriched = ai_result.files_enriched
  ```
- [x] 4.3: Pass AI token counts into `SyncResult`:
  ```python
  return SyncResult(
      # ... existing fields ...
      ai_prompt_tokens=ai_prompt_tokens,
      ai_completion_tokens=ai_completion_tokens,
      ai_files_enriched=ai_files_enriched,
  )
  ```
- [x] 4.4: **IMPORTANT** — The AI enrichment must merge descriptions into `old_descriptions` BEFORE `self._index.generate_content()` is called, so the index table includes AI descriptions. The current `IndexService.generate_content()` already carries forward descriptions via `old_descriptions` — we just need to add AI-generated ones to that dict.

### Task 5: Add `--no-ai` Flag to Sync Command (AC: 7)
- [x] 5.1: Add `--no-ai` flag to `sync_command()` in `src/nest/cli/sync_cmd.py`:
  ```python
  no_ai: Annotated[
      bool,
      typer.Option(
          "--no-ai",
          help="Skip AI enrichment even when API key is configured",
      ),
  ] = False,
  ```
- [x] 5.2: Pass `no_ai` to `create_sync_service()` or handle it in the CLI layer

### Task 6: Wire AI Enrichment in Composition Root (AC: 1, 6, 7)
- [x] 6.1: In `create_sync_service()` in `src/nest/cli/sync_cmd.py`, add AI enrichment wiring:
  ```python
  from nest.adapters.llm_provider import create_llm_provider
  from nest.services.ai_enrichment_service import AIEnrichmentService

  def create_sync_service(
      project_root: Path,
      error_logger: ...,
      no_ai: bool = False,
  ) -> SyncService:
      # ... existing wiring ...
      
      # AI enrichment (optional)
      ai_enrichment: AIEnrichmentService | None = None
      if not no_ai:
          llm_provider = create_llm_provider()
          if llm_provider is not None:
              ai_enrichment = AIEnrichmentService(llm_provider=llm_provider)
      
      return SyncService(
          # ... existing params ...
          ai_enrichment=ai_enrichment,
      )
  ```
- [x] 6.2: Pass `no_ai` from `sync_command()` into `create_sync_service()`

### Task 7: Update Sync Summary Display (AC: 1, 6)
- [x] 7.1: Update `_display_sync_summary()` in `sync_cmd.py` to show AI enrichment info:
  ```python
  # After existing summary lines, before enrichment prompt:
  if result.ai_files_enriched > 0:
      total_tokens = result.ai_prompt_tokens + result.ai_completion_tokens
      console.print(
          f"  AI enriched: {result.ai_files_enriched} descriptions "
          f"({total_tokens:,} tokens)"
      )
  ```
- [x] 7.2: When AI is active and files were enriched, suppress the old `@nest-enricher` agent prompt for those files (adjust `enrichment_needed` count to exclude AI-enriched files)

### Task 8: Unit Tests for `AIEnrichmentService` (AC: 1-8)
- [x] 8.1: Create `tests/services/test_ai_enrichment_service.py`:
  - **Test enrichment with all files needing descriptions:**
    - `test_enrich_generates_descriptions_for_new_files()` — all files new → LLM called for each
    - `test_enrich_returns_descriptions_and_token_counts()` — verify result shape
  - **Test incremental logic (AC2, AC3, AC4):**
    - `test_enrich_skips_unchanged_files()` — file with same content_hash and existing description → no LLM call
    - `test_enrich_calls_llm_for_changed_files()` — content_hash changed → LLM called
    - `test_enrich_calls_llm_for_missing_descriptions()` — same content_hash but empty description → LLM called
    - `test_enrich_calls_llm_for_new_files()` — file not in old_hints → LLM called
  - **Test graceful failure (AC5):**
    - `test_enrich_handles_llm_failure_gracefully()` — LLM returns None → empty description, count incremented
    - `test_enrich_continues_after_failure()` — failure on file 1, success on file 2
  - **Test prompt construction (AC8):**
    - `test_build_user_prompt_includes_all_metadata()` — verify prompt includes path, lines, headings, first_paragraph
    - `test_build_user_prompt_handles_missing_headings()` — no headings → not included
    - `test_build_user_prompt_handles_csv_columns()` — table_columns included
  - **Test sanitization:**
    - `test_sanitize_removes_pipe_chars()` — `|` replaced with `-`
    - `test_sanitize_truncates_to_15_words()` — long description capped
    - `test_sanitize_strips_quotes()` — leading/trailing quotes removed
  - **Test edge cases:**
    - `test_enrich_empty_file_list()` — no files → empty result, zero tokens
    - `test_enrich_all_files_cached()` — all unchanged → zero LLM calls, zero tokens
- [x] 8.2: Create mock LLM provider fixture:
  ```python
  class MockLLMProvider:
      def __init__(self, responses: dict[str, LLMCompletionResult | None]):
          self.responses = responses
          self.calls: list[tuple[str, str]] = []
      
      def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletionResult | None:
          self.calls.append((system_prompt, user_prompt))
          # Return response based on call index or file path in user_prompt
          ...
      
      @property
      def model_name(self) -> str:
          return "test-model"
  ```
- [x] 8.3: Use `LLMCompletionResult` from `nest.core.models` — never construct raw dicts

### Task 9: Update `SyncService` Tests (AC: 1, 6)
- [x] 9.1: Add tests in `tests/services/test_sync_service.py`:
  - `test_sync_with_ai_enrichment_merges_descriptions()` — AI descriptions appear in index content
  - `test_sync_without_ai_generates_unenriched_index()` — `ai_enrichment=None` → same behavior as before
  - `test_sync_returns_ai_token_counts()` — token counts propagated to `SyncResult`
- [x] 9.2: Ensure all existing `SyncService` tests still pass (no regressions — `ai_enrichment` defaults to `None`)

### Task 10: Run Full Test Suite (AC: 9)
- [x] 10.1: Run `pytest -m "not e2e"` — all pass (no regressions)
- [x] 10.2: Run `./scripts/ci-lint.sh` — clean (Ruff)
- [x] 10.3: Run `./scripts/ci-typecheck.sh` — clean (Pyright strict mode)

## Dev Notes

### Architecture Compliance

- **Service layer**: `AIEnrichmentService` lives in `src/nest/services/` — it orchestrates LLM calls, which is service-layer business logic.
- **Protocol-based DI**: `AIEnrichmentService` depends on `LLMProviderProtocol` (from `adapters/protocols.py`), **never** on `OpenAIAdapter` directly. Tests inject a mock.
- **Composition root**: AI wiring happens in `sync_cmd.py::create_sync_service()`. The service layer never imports `create_llm_provider()` or `OpenAIAdapter`.
- **Optional dependency**: `ai_enrichment=None` is the default — SyncService works identically to pre-6.2 when no AI is available. No code paths change for users without API keys.

### Critical Implementation Details

**Integration Point in SyncService Flow:**

The AI enrichment must be inserted into the existing sync flow carefully. Here is the current step ordering and where AI fits:

```
Current sync flow:
  5. Load old hints (content_hash map)
  6. Load old index + parse descriptions
  7. Extract new metadata for all context files
  8. Write new hints file
  9-13. Glossary hints processing
  14. Generate index content (uses old_descriptions + old_hints for carry-forward)
  15. Write index
  16. Count empty descriptions → enrichment_needed

Modified flow:
  5. Load old hints
  6. Load old index + parse descriptions
  7. Extract new metadata
  8. Write new hints
  9-13. Glossary hints processing
  *** AI ENRICHMENT INSERT POINT ***
  - Call ai_enrichment.enrich(new_metadata, old_descriptions, old_hints)
  - Merge AI descriptions into old_descriptions dict
  14. Generate index content (now has AI descriptions merged into old_descriptions)
  15. Write index
  16. Count empty descriptions (reduced by AI enrichment count)
```

**Why before `generate_content()` and not after:** The `IndexService.generate_content()` method already reads from `old_descriptions` to carry forward descriptions. By merging AI-generated descriptions into `old_descriptions` before calling `generate_content()`, we reuse the existing carry-forward logic cleanly without modifying `IndexService`.

**`enrich()` Method Incremental Logic:**

For each file in `new_metadata`:
1. Check if `file.path` is in `old_hints` AND `old_hints[file.path] == file.content_hash`:
   - YES (unchanged content) + existing non-empty description → **skip** (carry forward)
   - YES (unchanged content) + empty/missing description → **call LLM** (was never enriched)
   - NO (changed or new) → **call LLM** (content has changed, old description invalid)

```python
def _needs_enrichment(
    self,
    file: FileMetadata,
    old_descriptions: dict[str, str],
    old_hints: dict[str, str],
) -> bool:
    if file.path in old_hints and old_hints[file.path] == file.content_hash:
        existing = old_descriptions.get(file.path, "")
        if existing.strip():
            return False  # Unchanged + has description → skip
    return True  # Changed, new, or missing description → enrich
```

**`--no-ai` Flag Behavior:**

When `--no-ai` is passed:
- `create_llm_provider()` is **never called** (don't even check env vars)
- `ai_enrichment` parameter to `SyncService` is `None`
- Existing description carry-forward still works (via `old_descriptions` in `IndexService`)
- Previously AI-generated descriptions are preserved through the content_hash mechanism

**Prompt Design (AC8):**

System prompt:
```
You are a technical documentation assistant.
Write a concise description of the given document in at most 15 words.
Output ONLY the description text, nothing else.
Do NOT use pipe characters (|) in your output.
Do NOT include quotes around the description.
```

User prompt (per file):
```
File: contracts/2024/alpha.md
Lines: 142
Headings: Alpha Contract Overview, Payment Terms, Deliverables Schedule
Content preview: This document outlines the contractual agreement between...
```

**Sanitization Pipeline:**

LLM output may contain problematic characters. Apply:
1. Strip leading/trailing whitespace
2. Replace `|` with `-` (Markdown table safety)
3. Strip surrounding quotes (`"description"` → `description`)
4. Truncate to 15 words max (defensive — LLM may exceed)
5. Strip again after truncation

**Token Aggregation:**

Each `LLMCompletionResult` has `prompt_tokens` and `completion_tokens`. Sum across all calls:
```python
total_prompt = sum(r.prompt_tokens for r in results if r)
total_completion = sum(r.completion_tokens for r in results if r)
```

These flow through `AIEnrichmentResult` → `SyncResult` → `_display_sync_summary()`.

### Existing Codebase Patterns to Follow

**Service constructor pattern** (from `sync_service.py`):
```python
class AIEnrichmentService:
    def __init__(self, llm_provider: LLMProviderProtocol) -> None:
        self._llm = llm_provider
```

**Result model pattern** (from `models.py`):
```python
class AIEnrichmentResult(BaseModel):
    descriptions: dict[str, str] = Field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    files_enriched: int = 0
    files_skipped: int = 0
    files_failed: int = 0
```

**Logging pattern** (from all services):
```python
import logging
logger = logging.getLogger(__name__)
```

**Test mock pattern** (from `tests/conftest.py` — uses protocol-compatible classes):
```python
class MockLLMProvider:
    """Mock LLM provider for testing AI enrichment."""
    
    def __init__(self, responses: list[LLMCompletionResult | None] | None = None):
        self._responses = responses or []
        self._call_index = 0
        self.calls: list[tuple[str, str]] = []
    
    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletionResult | None:
        self.calls.append((system_prompt, user_prompt))
        if self._call_index < len(self._responses):
            result = self._responses[self._call_index]
            self._call_index += 1
            return result
        return None
    
    @property
    def model_name(self) -> str:
        return "mock-model"
```

**Sync command flag pattern** (from existing `sync_cmd.py`):
```python
no_ai: Annotated[
    bool,
    typer.Option("--no-ai", help="Skip AI enrichment even when API key is configured"),
] = False,
```

### Project Structure Notes

- All new files follow the `src/nest/` src-layout
- Service in `src/nest/services/ai_enrichment_service.py` — consistent with other services
- Model in `src/nest/core/models.py` — extends existing model collection
- Tests in `tests/services/test_ai_enrichment_service.py` — mirrors source structure
- No new adapter files needed — reuses `LLMProviderProtocol` from Story 6.1
- No new core files needed — `FileMetadata` already has all necessary fields

### Dependencies

- **Upstream:** Story 6.1 (LLM Provider Adapter) — provides `LLMProviderProtocol`, `OpenAIAdapter`, `create_llm_provider()`, `LLMCompletionResult`
- **Downstream:** Story 6.3 (AI Glossary) shares the same AI integration pattern. Story 6.4 (Parallel Execution) will run 6.2 and 6.3 in parallel threads + add token aggregation. Story 6.6 (Remove Agents) will remove `@nest-enricher` agent (replaced by this story's built-in enrichment).

### Testing Strategy

- All tests use mock `LLMProviderProtocol` — **zero real API calls ever**
- `FileMetadata` objects are constructed directly in tests (no filesystem needed)
- `old_descriptions` and `old_hints` are plain dicts — easy to construct
- Incremental logic tested exhaustively: unchanged+described, unchanged+undescribed, changed, new
- Edge cases: empty file list, all cached, all failures, mixed success/failure
- Integration into `SyncService`: verify AI descriptions appear in generated index content
- Existing `SyncService` tests must not break (`ai_enrichment=None` is default)
- No E2E tests changed — E2E for AI enrichment can be added in Story 6.4 or after

### What This Story Does NOT Include (Scope Boundaries)

- **No parallel execution** — LLM calls are sequential in this story. Parallelism is Story 6.4.
- **No glossary generation** — That's Story 6.3.
- **No token usage display in summary** — Token reporting in sync summary is minimal here (count only). Full reporting with `AI tokens: X (prompt: Y, completion: Z)` formatting is Story 6.4.
- **No `nest config ai` command** — That's Story 6.5.
- **No agent removal** — Removing `@nest-enricher` agent template is Story 6.6. Both the old agent and new built-in enrichment coexist during 6.2-6.5.
- **No changes to `InitService`** — Agent templates remain until Story 6.6.
- **No `--no-ai` flag for other commands** — Only `nest sync` gets this flag.

### File Inventory

| File | Action | Purpose |
|------|--------|---------|
| `src/nest/services/ai_enrichment_service.py` | **CREATE** | `AIEnrichmentService` class with `enrich()` method |
| `src/nest/core/models.py` | MODIFY | Add `AIEnrichmentResult` model; add `ai_*` fields to `SyncResult` |
| `src/nest/services/sync_service.py` | MODIFY | Accept optional `ai_enrichment` param; call enrichment before index generation |
| `src/nest/cli/sync_cmd.py` | MODIFY | Add `--no-ai` flag; wire `AIEnrichmentService` in composition root; update summary display |
| `tests/services/test_ai_enrichment_service.py` | **CREATE** | Unit tests for AI enrichment service |
| `tests/services/test_sync_service.py` | MODIFY | Add tests for AI integration path |

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.2] — AC, story description, dependencies
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6] — Epic scope and design principles
- [Source: _bmad-output/planning-artifacts/architecture.md#Layer Boundaries] — Service/adapter/core layer rules
- [Source: _bmad-output/planning-artifacts/architecture.md#Protocol Boundaries] — DI via protocols
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Flow: Sync Command] — Sync execution flow
- [Source: _bmad-output/planning-artifacts/prd.md#FR28] — Incremental AI enrichment using content hashes
- [Source: _bmad-output/planning-artifacts/prd.md#FR30] — Token usage reporting + `--no-ai` flag
- [Source: _bmad-output/project-context.md#Architecture & Dependency Injection] — Protocol-based DI pattern
- [Source: _bmad-output/project-context.md#Testing Rules] — Test naming, AAA pattern, mock strategy
- [Source: _bmad-output/project-context.md#CLI Output Patterns] — Rich console output rules
- [Source: _bmad-output/implementation-artifacts/6-1-llm-provider-adapter-and-ai-detection.md] — Foundation story, adapter API, protocol contract
- [Source: src/nest/services/sync_service.py] — Current sync flow (steps 5-16)
- [Source: src/nest/services/index_service.py] — Index generation with description carry-forward
- [Source: src/nest/services/metadata_service.py] — FileMetadata extraction, hints YAML format
- [Source: src/nest/core/models.py#FileMetadata] — Metadata fields available for prompts
- [Source: src/nest/core/models.py#SyncResult] — Result model to extend with AI fields
- [Source: src/nest/adapters/protocols.py#LLMProviderProtocol] — Protocol for LLM calls
- [Source: src/nest/adapters/llm_provider.py] — `OpenAIAdapter`, `create_llm_provider()` factory
- [Source: src/nest/cli/sync_cmd.py#create_sync_service] — Composition root to modify

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (GitHub Copilot)

### Debug Log References

N/A — all tests passed on first run.

### Completion Notes List

- AIEnrichmentService created with incremental logic: unchanged files with existing descriptions are skipped (no LLM call).
- AI enrichment inserted into SyncService flow after glossary processing, before index generation. AI descriptions merged into `old_descriptions` dict so `IndexService.generate_content()` picks them up via existing carry-forward logic.
- `--no-ai` flag added to `nest sync` — prevents `create_llm_provider()` from being called at all.
- Composition root in `sync_cmd.py` creates `AIEnrichmentService` only when `no_ai=False` AND `create_llm_provider()` returns a provider (API key detected).
- Summary display shows "AI enriched: N descriptions (X tokens)" when AI was active.
- 21 unit tests for AIEnrichmentService covering: enrichment, incremental logic, failure handling, prompt construction, sanitization, edge cases.
- 3 integration tests added to SyncService tests for AI path.
- 713 total tests pass (0 failures), Ruff clean, Pyright clean.

### File List

| File | Action |
|------|--------|
| `src/nest/services/ai_enrichment_service.py` | CREATED |
| `src/nest/core/models.py` | MODIFIED — added `AIEnrichmentResult` model, added `ai_prompt_tokens`, `ai_completion_tokens`, `ai_files_enriched` to `SyncResult` |
| `src/nest/services/sync_service.py` | MODIFIED — added optional `ai_enrichment` param, inserted AI enrichment call before index generation, propagated AI token counts to `SyncResult` |
| `src/nest/cli/sync_cmd.py` | MODIFIED — added `--no-ai` flag, wired `AIEnrichmentService` in composition root, updated summary display |
| `tests/services/test_ai_enrichment_service.py` | CREATED — 21 unit tests |
| `tests/services/test_sync_service.py` | MODIFIED — added 3 AI enrichment integration tests |

## Senior Developer Review (AI)

### Review Date
2026-03-05

### Reviewer Model
Claude Opus 4.6 (GitHub Copilot)

### Findings Summary

| Severity | Count | Fixed |
|----------|-------|-------|
| CRITICAL | 1 | 1 |
| MEDIUM   | 3 | 3 |
| LOW      | 1 | 0 (not applicable — Story 6.1 uncommitted files) |

### CRITICAL Issues Found & Fixed

1. **AI descriptions silently dropped for changed/new files** — `IndexService.generate_content()` only reads from `old_descriptions` when `old_hints[path] == content_hash`. AI generates descriptions for changed/new files (mismatching hashes), so descriptions are merged into `old_descriptions` but never written to the index. **Broke AC1, AC3, AC4.**
   - **Fix**: After AI enrichment merges descriptions, also update `old_hints` for AI-enriched files so `generate_content()`'s carry-forward hash check passes. (`sync_service.py`)

### MEDIUM Issues Found & Fixed

2. **Missing newline sanitization** — `_sanitize_description()` didn't replace `\n` with space. Multi-line LLM output would break the Markdown index table.
   - **Fix**: Added `.replace("\n", " ")` before pipe replacement. Added `test_sanitize_replaces_newlines` test. (`ai_enrichment_service.py`)

3. **Sync test didn't verify merge content** — `test_sync_with_ai_enrichment_merges_descriptions` only asserted two methods were called; didn't verify descriptions were actually in `old_descriptions` or that `old_hints` was updated.
   - **Fix**: Enhanced test to inspect `generate_content` call args, asserting AI description in `old_descriptions` and updated hash in `old_hints`. (`test_sync_service.py`)

4. **`AIEnrichmentService` import outside `no_ai` guard** — Import ran even when `--no-ai` was set.
   - **Fix**: Moved import inside the `if not no_ai` + `if llm_provider is not None` guard. (`sync_cmd.py`)

### LOW Issues (Not Fixed)

5. **`protocols.py` changed in git but not in story File List** — Part of Story 6.1, uncommitted. Not a 6.2 defect.

### Post-Review Test Results

- 714 tests pass (was 713 — +1 new sanitization test)
- Ruff: All checks passed
- Pyright: 0 errors, 0 warnings, 0 informations

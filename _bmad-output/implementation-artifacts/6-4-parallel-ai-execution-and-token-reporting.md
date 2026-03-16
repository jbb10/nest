# Story 6.4: Parallel AI Execution & Token Reporting

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user running `nest sync` with AI enrichment**,
I want **the index enrichment and glossary generation to run in parallel and see how many tokens were used**,
So that **sync completes faster and I can track AI usage costs**.

## Business Context

This is the **fourth story in Epic 6** (Built-in AI Enrichment). Story 6.1 created the `LLMProviderProtocol`, `OpenAIAdapter`, and `create_llm_provider()` factory. Story 6.2 created `AIEnrichmentService` for generating file descriptions. Story 6.3 created `AIGlossaryService` for AI-powered glossary generation. Both AI services currently run **sequentially** in `SyncService.sync()`.

This story **parallelizes** the two AI tasks using `concurrent.futures.ThreadPoolExecutor`, aggregates their token usage into a single summary line, adds first-run AI discovery messaging, and adds an AI progress indicator.

**Key design principles:**
- **Parallel execution** — index enrichment and glossary generation run concurrently when both have work. If only one has work, no unnecessary thread spawning.
- **Independent failure handling** — if one task fails, the other completes normally. Failures degrade gracefully with logged errors.
- **Aggregated token reporting** — a single `AI tokens: X (prompt: Y, completion: Z)` line replaces the current separate per-service token lines.
- **First-run discovery** — the first time AI is detected in a project, a one-time informational message is shown. Tracked via `.nest/.ai_seen` marker file.
- **Progress indicator** — an AI phase indicator shows during the parallel execution phase.

## Acceptance Criteria

### AC1: Parallel Execution of AI Tasks

**Given** AI is configured and both index enrichment and glossary generation have work to do
**When** sync reaches the AI phase (after document processing, manifest commit, and orphan cleanup)
**Then** index enrichment and glossary generation run concurrently via `concurrent.futures.ThreadPoolExecutor` with `max_workers=2`
**And** both tasks complete before the sync summary is displayed

### AC2: Independent Failure Handling

**Given** one AI task fails (e.g., glossary times out) while the other succeeds
**When** parallel execution completes
**Then** the successful task's results are applied normally
**And** the failed task degrades gracefully (partial results or empty)
**And** errors are logged

### AC3: Single-Task Optimization

**Given** only one AI task has work (e.g., no new glossary terms but index needs enrichment)
**When** sync reaches the AI phase
**Then** only the task with work runs (no unnecessary thread spawning)

### AC4: Aggregated Token Usage Display

**Given** AI enrichment runs (either or both tasks)
**When** sync summary is displayed
**Then** token usage is reported as a single aggregated line:
```
  AI tokens:    1,247 (prompt: 983, completion: 264)
```
**And** the token counts are aggregated across both enrichment and glossary calls

### AC5: Zero Tokens = No Token Line

**Given** AI enrichment runs but generates zero descriptions and zero glossary terms (all cached)
**When** sync summary is displayed
**Then** no token usage line is shown (nothing to report)

### AC6: First-Run AI Discovery Message

**Given** the first time AI is detected during sync for a project
**When** sync summary is displayed
**Then** a one-time informational tip is shown:
```
  🤖 AI enrichment enabled (found OPENAI_API_KEY)
```
**And** a tip is shown: `💡 Run 'nest config ai' to change AI settings. Use --no-ai to skip.`

### AC7: Subsequent Syncs Suppress Discovery Message

**Given** AI has been used in previous syncs for this project
**When** subsequent syncs run
**Then** the "AI enrichment enabled" discovery message is NOT repeated
**And** only token usage is reported (if tokens were consumed)

### AC8: AI Phase Progress Indicator

**Given** progress display is active during sync
**When** the AI phase runs
**Then** a progress indicator shows AI activity: `🤖 AI enrichment...`
**And** completion shows counts: `4 descriptions, 3 glossary terms`

### AC9: All Tests Pass

**Given** all unit and integration tests
**When** the changes are complete
**Then** parallel execution is tested with both tasks mocked
**And** token aggregation is tested
**And** all tests pass with no regressions

## Tasks / Subtasks

### Task 1: Refactor `SyncService.sync()` for Parallel AI Execution (AC: 1, 2, 3)
- [x] 1.1: Add `from concurrent.futures import ThreadPoolExecutor, Future` import to `sync_service.py`
- [x] 1.2: Replace sequential AI enrichment + glossary code in `sync()` with parallel executor:
  ```python
  # Parallel AI execution (after step 13, before index generation)
  ai_prompt_tokens = 0
  ai_completion_tokens = 0
  ai_files_enriched = 0
  ai_glossary_terms_added = 0
  ai_glossary_prompt_tokens = 0
  ai_glossary_completion_tokens = 0

  has_enrichment_work = self._ai_enrichment is not None
  has_glossary_work = (
      self._ai_glossary is not None and len(merged_glossary.terms) > 0
  )

  if has_enrichment_work and has_glossary_work:
      # Both tasks have work — run in parallel
      with ThreadPoolExecutor(max_workers=2) as executor:
          enrichment_future = executor.submit(
              self._ai_enrichment.enrich,  # type: ignore[union-attr]
              new_metadata, old_descriptions, old_hints,
          )
          glossary_future = executor.submit(
              self._run_glossary,
              merged_glossary, context_dir,
          )
          # Collect results (exceptions caught per-task)
          ai_result = self._collect_enrichment_result(enrichment_future)
          glossary_result = self._collect_glossary_result(glossary_future)
  elif has_enrichment_work:
      # Only enrichment — run directly (no thread overhead)
      ai_result = self._ai_enrichment.enrich(  # type: ignore[union-attr]
          new_metadata, old_descriptions, old_hints,
      )
      glossary_result = None
  elif has_glossary_work:
      # Only glossary — run directly
      ai_result = None
      glossary_result = self._run_glossary(merged_glossary, context_dir)
  else:
      ai_result = None
      glossary_result = None

  # Apply enrichment results
  if ai_result is not None:
      old_descriptions.update(ai_result.descriptions)
      for file_meta in new_metadata:
          if file_meta.path in ai_result.descriptions:
              old_hints[file_meta.path] = file_meta.content_hash
      ai_prompt_tokens = ai_result.prompt_tokens
      ai_completion_tokens = ai_result.completion_tokens
      ai_files_enriched = ai_result.files_enriched

  # Apply glossary results
  if glossary_result is not None:
      ai_glossary_terms_added = glossary_result.terms_added
      ai_glossary_prompt_tokens = glossary_result.prompt_tokens
      ai_glossary_completion_tokens = glossary_result.completion_tokens
  ```
- [x] 1.3: Add `_run_glossary()` helper method to `SyncService`:
  ```python
  def _run_glossary(
      self, merged_glossary: GlossaryHints, context_dir: Path
  ) -> AIGlossaryResult:
      """Run AI glossary generation.

      Extracted to a method for ThreadPoolExecutor.submit() compatibility.

      Args:
          merged_glossary: Merged glossary hints.
          context_dir: Path to _nest_context directory.

      Returns:
          AIGlossaryResult with counts and token usage.
      """
      glossary_file_path = context_dir / GLOSSARY_FILE
      return self._ai_glossary.generate(  # type: ignore[union-attr]
          merged_glossary, glossary_file_path
      )
  ```
- [x] 1.4: Add `_collect_enrichment_result()` method for safe future result collection:
  ```python
  def _collect_enrichment_result(
      self, future: Future[AIEnrichmentResult]
  ) -> AIEnrichmentResult | None:
      """Safely collect enrichment result from a future.

      Args:
          future: Future from ThreadPoolExecutor.

      Returns:
          AIEnrichmentResult or None if the task raised an exception.
      """
      try:
          return future.result()
      except Exception:
          logger.exception("AI enrichment failed during parallel execution")
          return None
  ```
- [x] 1.5: Add `_collect_glossary_result()` method for safe future result collection:
  ```python
  def _collect_glossary_result(
      self, future: Future[AIGlossaryResult]
  ) -> AIGlossaryResult | None:
      """Safely collect glossary result from a future.

      Args:
          future: Future from ThreadPoolExecutor.

      Returns:
          AIGlossaryResult or None if the task raised an exception.
      """
      try:
          return future.result()
      except Exception:
          logger.exception("AI glossary generation failed during parallel execution")
          return None
  ```
- [x] 1.6: Add required imports to `sync_service.py`:
  ```python
  from concurrent.futures import Future, ThreadPoolExecutor
  ```
  And add `GlossaryHints` to the TYPE_CHECKING block (if not already imported):
  ```python
  if TYPE_CHECKING:
      from nest.core.models import AIEnrichmentResult, AIGlossaryResult, GlossaryHints
      from nest.services.ai_enrichment_service import AIEnrichmentService
      from nest.services.ai_glossary_service import AIGlossaryService
  ```

### Task 2: Add AI Progress Callback Support (AC: 8)
- [x] 2.1: Add optional `ai_progress_callback` parameter to `SyncService.sync()`:
  ```python
  def sync(
      self,
      no_clean: bool = False,
      on_error: Literal["skip", "fail"] = "skip",
      dry_run: bool = False,
      force: bool = False,
      progress_callback: ProgressCallback | None = None,
      ai_progress_callback: Callable[[str], None] | None = None,
      changes: DiscoveryResult | None = None,
  ) -> SyncResult | DryRunResult:
  ```
- [x] 2.2: Call `ai_progress_callback` before and after AI phase in `sync()`:
  ```python
  # Before AI phase
  if ai_progress_callback is not None and (has_enrichment_work or has_glossary_work):
      ai_progress_callback("start")

  # ... parallel/sequential AI execution ...

  # After AI phase
  if ai_progress_callback is not None and (has_enrichment_work or has_glossary_work):
      parts = []
      if ai_files_enriched > 0:
          parts.append(f"{ai_files_enriched} descriptions")
      if ai_glossary_terms_added > 0:
          parts.append(f"{ai_glossary_terms_added} glossary terms")
      summary = ", ".join(parts) if parts else "cached"
      ai_progress_callback(summary)
  ```

### Task 3: Aggregated Token Display in `sync_cmd.py` (AC: 4, 5)
- [x] 3.1: Replace the current separate AI enrichment and glossary token lines in `_display_sync_summary()` with a single aggregated line:
  ```python
  # Remove the current separate blocks:
  # - "AI enriched: X descriptions (Y tokens)"
  # - "AI glossary: X terms defined (Y tokens)"

  # Replace with aggregated display:
  total_prompt = result.ai_prompt_tokens + result.ai_glossary_prompt_tokens
  total_completion = result.ai_completion_tokens + result.ai_glossary_completion_tokens
  total_tokens = total_prompt + total_completion

  if total_tokens > 0:
      console.print(
          f"  AI tokens:    {total_tokens:,} "
          f"(prompt: {total_prompt:,}, completion: {total_completion:,})"
      )

  # Show AI activity counts (enrichment + glossary) on separate detail lines
  if result.ai_files_enriched > 0:
      console.print(f"  AI enriched:  {result.ai_files_enriched} descriptions")

  if result.ai_glossary_terms_added > 0:
      console.print(f"  AI glossary:  {result.ai_glossary_terms_added} terms defined")
  ```

### Task 4: First-Run AI Discovery Message (AC: 6, 7)
- [x] 4.1: Add `AI_SEEN_MARKER` constant to `src/nest/core/paths.py`:
  ```python
  AI_SEEN_MARKER = ".ai_seen"
  ```
- [x] 4.2: ~~Add `ai_detected_key` field to `SyncResult`~~ — passed via CLI layer instead (simpler, presentation-only concern):
  ```python
  # Add to SyncResult:
  ai_detected_key: str = ""  # Name of env var that triggered AI (e.g., "OPENAI_API_KEY")
  ```
- [x] 4.3: Detect `ai_detected_key` in `sync_cmd.py` and pass to `_display_sync_summary()`:
  ```python
  # In sync_command(), after create_sync_service():
  ai_detected_key = ""
  if not no_ai:
      import os
      if os.environ.get("NEST_AI_API_KEY"):
          ai_detected_key = "NEST_AI_API_KEY"
      elif os.environ.get("OPENAI_API_KEY"):
          ai_detected_key = "OPENAI_API_KEY"
  ```
- [x] 4.4: Update `_display_sync_summary()` signature to accept `ai_detected_key` and `project_root`:
  ```python
  def _display_sync_summary(
      result: SyncResult,
      console: "Console",
      error_log_path: Path,
      ai_detected_key: str = "",
      project_root: Path | None = None,
  ) -> None:
  ```
- [x] 4.5: Add first-run detection and marker file logic in `_display_sync_summary()`:
  ```python
  # First-run AI discovery message
  ai_was_used = (
      result.ai_files_enriched > 0
      or result.ai_glossary_terms_added > 0
      or (result.ai_prompt_tokens + result.ai_glossary_prompt_tokens) > 0
  )

  if ai_was_used and ai_detected_key and project_root is not None:
      ai_marker = project_root / NEST_META_DIR / AI_SEEN_MARKER
      if not ai_marker.exists():
          console.print()
          console.print(f"  🤖 AI enrichment enabled (found {ai_detected_key})")
          console.print(
              "  💡 Run 'nest config ai' to change AI settings. Use --no-ai to skip."
          )
          # Create marker file
          ai_marker.touch()
  ```

### Task 5: AI Phase Progress Indicator in `sync_cmd.py` (AC: 8)
- [x] 5.1: Add AI progress display in `sync_command()` using Rich console:
  ```python
  # After the SyncProgress context manager, add AI phase display:
  # Create an ai_progress_callback for the service
  def ai_progress_callback(message: str) -> None:
      if message == "start":
          console.print("  🤖 AI enrichment...", end="")
      else:
          console.print(f" {message}")

  result = service.sync(
      # ... existing params ...
      ai_progress_callback=ai_progress_callback,
      changes=changes,
  )
  ```
- [x] 5.2: Integrate the AI progress callback into the sync call inside the `SyncProgress` context manager (the callback is passed to `service.sync()`).

### Task 6: Unit Tests for Parallel Execution (AC: 1, 2, 3, 9)
- [x] 6.1: Add tests in `tests/services/test_sync_service.py`:
  - **Parallel execution tests:**
    - `test_sync_runs_ai_tasks_in_parallel_when_both_have_work()` — verify both enrichment and glossary execute and results merge correctly
    - `test_sync_runs_only_enrichment_when_no_glossary_terms()` — glossary has no candidates → no glossary thread spawned
    - `test_sync_runs_only_glossary_when_no_enrichment_service()` — enrichment is None, glossary has terms
    - `test_sync_skips_ai_entirely_when_both_none()` — both services None → no executor created
  - **Failure isolation tests:**
    - `test_sync_enrichment_failure_doesnt_block_glossary()` — enrichment raises exception → glossary still succeeds
    - `test_sync_glossary_failure_doesnt_block_enrichment()` — glossary raises exception → enrichment still succeeds
    - `test_sync_both_ai_tasks_fail_gracefully()` — both fail → sync completes, zero AI results
  - **Result aggregation tests:**
    - `test_sync_aggregates_tokens_from_both_ai_tasks()` — token counts from both tasks sum correctly in SyncResult
    - `test_sync_parallel_results_applied_to_descriptions()` — enrichment descriptions merged into old_descriptions correctly after parallel run
  - **AI progress callback tests:**
    - `test_sync_calls_ai_progress_callback_on_start()` — callback receives "start" when AI phase begins
    - `test_sync_calls_ai_progress_callback_with_summary()` — callback receives summary like "4 descriptions, 3 glossary terms"
    - `test_sync_no_ai_progress_callback_when_no_ai_work()` — callback not called when no AI tasks

### Task 7: Unit Tests for Aggregated Token Display (AC: 4, 5, 6, 7, 9)
- [x] 7.1: Add/update tests in `tests/cli/test_sync_cmd.py`:
  - **Aggregated token display:**
    - `test_display_sync_summary_shows_aggregated_tokens()` — combined prompt+completion from both services shown in single line
    - `test_display_sync_summary_hides_tokens_when_zero()` — all tokens zero → no AI tokens line
    - `test_display_sync_summary_shows_enrichment_count()` — "AI enriched: X descriptions" shown when > 0
    - `test_display_sync_summary_shows_glossary_count()` — "AI glossary: X terms defined" shown when > 0
  - **First-run detection:**
    - `test_display_sync_summary_shows_first_run_message()` — no `.ai_seen` marker → discovery message shown
    - `test_display_sync_summary_creates_marker_file()` — `.ai_seen` file created after first AI use
    - `test_display_sync_summary_suppresses_message_on_subsequent_runs()` — `.ai_seen` exists → no discovery message
    - `test_display_sync_summary_no_message_when_no_ai_used()` — AI not active → no discovery message even without marker

### Task 8: Run Full Test Suite (AC: 9)
- [x] 8.1: Run `pytest -m "not e2e"` — 763 passed (743 baseline + 20 new)
- [x] 8.2: Run `make lint` — clean (Ruff)
- [x] 8.3: Run `make typecheck` — clean (Pyright strict mode)

## Dev Notes

### Architecture Compliance

- **Service layer**: Parallelization lives in `SyncService.sync()` — it orchestrates the AI services. No architectural layer boundaries crossed.
- **Protocol-based DI**: Both `AIEnrichmentService` and `AIGlossaryService` continue to depend on `LLMProviderProtocol` via DI. The `ThreadPoolExecutor` is an internal implementation detail of `SyncService`.
- **Composition root unchanged**: `sync_cmd.py::create_sync_service()` wiring is unchanged — both AI services still created the same way. Parallelism happens inside the service, not in the CLI layer.
- **Optional dependencies**: Both AI services default to `None`. When both are `None`, no executor is created and sync behaves identically to pre-6.4.
- **Thread safety**: Both `AIEnrichmentService.enrich()` and `AIGlossaryService.generate()` are stateless operations that read shared data but write to independent outputs (descriptions dict vs glossary file). They share the `LLMProviderProtocol` instance, which uses the `openai` SDK — the `OpenAI` client is documented thread-safe. No mutex needed.

### Critical Implementation Details

**Integration Point in SyncService Flow:**

The parallel AI execution replaces the current sequential code between step 13 (write glossary hints) and step 14 (generate index). The current sequential flow:

```python
# Current (6.3):
# AI enrichment (sequential)
if self._ai_enrichment is not None:
    ai_result = self._ai_enrichment.enrich(...)
    old_descriptions.update(ai_result.descriptions)
    ...

# AI glossary (sequential, after enrichment)
if self._ai_glossary is not None and len(merged_glossary.terms) > 0:
    glossary_result = self._ai_glossary.generate(...)
    ...
```

Becomes:

```python
# New (6.4):
# Determine which tasks have work
has_enrichment_work = self._ai_enrichment is not None
has_glossary_work = self._ai_glossary is not None and len(merged_glossary.terms) > 0

if has_enrichment_work and has_glossary_work:
    # PARALLEL: both tasks run concurrently
    with ThreadPoolExecutor(max_workers=2) as executor:
        enrichment_future = executor.submit(...)
        glossary_future = executor.submit(...)
        ai_result = self._collect_enrichment_result(enrichment_future)
        glossary_result = self._collect_glossary_result(glossary_future)
elif has_enrichment_work:
    # SEQUENTIAL: only enrichment (no thread overhead)
    ai_result = self._ai_enrichment.enrich(...)
    glossary_result = None
elif has_glossary_work:
    # SEQUENTIAL: only glossary (no thread overhead)
    ai_result = None
    glossary_result = self._run_glossary(...)
else:
    ai_result = None
    glossary_result = None
```

**Why `ThreadPoolExecutor` (not `asyncio`):**
- Both AI services make external HTTP calls to the OpenAI API — I/O-bound, perfect for threading.
- `ThreadPoolExecutor` integrates cleanly with the existing synchronous codebase. No `async`/`await` refactoring needed.
- `max_workers=2` — exactly two tasks (enrichment + glossary). No thread pool sizing complexity.
- The `openai` Python SDK client is thread-safe (uses `httpx` internally with connection pooling).

**Result Application Order:**

After parallel execution, results are applied in the same order as the current sequential flow:
1. Enrichment descriptions merged into `old_descriptions` → consumed by step 14 (index generation)
2. Glossary results are independent (written directly to `_nest_context/glossary.md` by the service)
3. Token counts aggregated and stored in `SyncResult` fields

This ordering is important: enrichment results MUST be applied BEFORE step 14 (`generate_content()`), because `generate_content()` reads from `old_descriptions` and `old_hints`.

**Error Isolation:**

Each future's `result()` call is wrapped in `try/except Exception`:
- If enrichment throws: `ai_result = None` → descriptions are empty (same as no AI), glossary unaffected
- If glossary throws: `glossary_result = None` → no terms added, enrichment unaffected
- If both throw: both results None → sync completes normally without AI, all errors logged

**AI Progress Callback:**

The `ai_progress_callback` is a simple `Callable[[str], None]` that receives:
- `"start"` — when AI phase begins (before executor)
- A summary string — when AI phase completes (e.g., `"4 descriptions, 3 glossary terms"` or `"cached"`)

This is called in `sync()` around the parallel execution block. The CLI layer (`sync_cmd.py`) provides the implementation that prints to console.

**First-Run AI Discovery Tracking:**

Tracked via a marker file `.nest/.ai_seen`:
- **Check**: In `_display_sync_summary()`, if AI was used and marker doesn't exist → show discovery message and create marker
- **Why marker file?** Simpler than modifying the `Manifest` schema. The marker is a pure UX concern (when to show a one-time message), not business state.
- **Why in CLI layer?** First-run messaging is a CLI presentation concern, not business logic. Keeping it in `sync_cmd.py` keeps `SyncService` focused on orchestration.
- **Detected key name**: Determined in `sync_command()` by checking `NEST_AI_API_KEY` and `OPENAI_API_KEY` env vars directly. Passed to `_display_sync_summary()`.

**Aggregated Token Display:**

The current separate display:
```
  AI enriched: 4 descriptions (327 tokens)
  AI glossary: 3 terms defined (920 tokens)
```

Becomes:
```
  AI tokens:    1,247 (prompt: 983, completion: 264)
  AI enriched:  4 descriptions
  AI glossary:  3 terms defined
```

This gives cost-tracking users the total token breakdown on one line, plus activity counts on separate lines. If zero tokens were consumed (all cached), no AI lines appear.

**`--no-ai` Flag Behavior:**

The existing `--no-ai` guard in `sync_cmd.py::create_sync_service()` ensures both AI services are `None` when the flag is set. The parallelization logic in `SyncService` naturally handles this — when both are `None`, `has_enrichment_work` and `has_glossary_work` are both `False`, and no executor is created.

### Existing Codebase Patterns to Follow

**`concurrent.futures` usage pattern:**
```python
from concurrent.futures import Future, ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=2) as executor:
    future_a = executor.submit(func_a, arg1, arg2)
    future_b = executor.submit(func_b, arg3)
    result_a = future_a.result()  # blocks until complete
    result_b = future_b.result()
```

**Service method extraction pattern** (for `executor.submit()`):
```python
def _run_glossary(self, merged_glossary: GlossaryHints, context_dir: Path) -> AIGlossaryResult:
    """Extracted for ThreadPoolExecutor.submit() compatibility."""
    glossary_file_path = context_dir / GLOSSARY_FILE
    return self._ai_glossary.generate(merged_glossary, glossary_file_path)  # type: ignore[union-attr]
```

**Logging pattern** (from all services):
```python
import logging
logger = logging.getLogger(__name__)
logger.exception("AI enrichment failed during parallel execution")
```

**TYPE_CHECKING import pattern** (from `sync_service.py`):
```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nest.core.models import AIEnrichmentResult, AIGlossaryResult
    from nest.services.ai_enrichment_service import AIEnrichmentService
    from nest.services.ai_glossary_service import AIGlossaryService
```

**Test mock pattern** (from `tests/services/test_ai_enrichment_service.py`):
```python
class MockLLMProvider:
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

**Raising exceptions in mock services for failure tests:**
```python
class FailingAIEnrichmentService:
    """Mock that raises an exception when enrich() is called."""
    def enrich(self, files, old_descriptions, old_hints):
        raise RuntimeError("Enrichment network timeout")

class FailingAIGlossaryService:
    """Mock that raises an exception when generate() is called."""
    def generate(self, terms, glossary_path):
        raise RuntimeError("Glossary API rate limit exceeded")
```

### Project Structure Notes

- All changes follow the existing `src/nest/` src-layout
- No new service files — changes are in existing `sync_service.py` and `sync_cmd.py`
- One new constant in `src/nest/core/paths.py` (`AI_SEEN_MARKER`)
- Tests added/modified in existing files: `tests/services/test_sync_service.py`, `tests/cli/test_sync_cmd.py`
- No new adapter files — `concurrent.futures` is stdlib, no new dependency needed

### What This Story Does NOT Include (Scope Boundaries)

- **No `nest config ai` command** — That's Story 6.5
- **No agent removal** — That's Story 6.6
- **No changes to `AIEnrichmentService`** — Its API is unchanged, just called from a thread
- **No changes to `AIGlossaryService`** — Its API is unchanged, just called from a thread
- **No changes to `LLMProviderProtocol`** — The protocol is thread-safe as-is
- **No `async`/`await` refactoring** — Threads are sufficient for I/O-bound LLM calls
- **No changes to the `openai` dependency** — Already thread-safe
- **No E2E test changes** — E2E tests don't test AI (no API keys in CI)

### Dependencies

- **Upstream:** Story 6.2 (AI Index Enrichment) — provides `AIEnrichmentService` with `enrich()` method and `AIEnrichmentResult`
- **Upstream:** Story 6.3 (AI Glossary Generation) — provides `AIGlossaryService` with `generate()` method and `AIGlossaryResult`
- **Downstream:** Story 6.5 (`nest config ai`) — the first-run message references this command
- **Downstream:** Story 6.6 (Remove Agents) — will remove `@nest-enricher`/`@nest-glossary` references from summary

### Previous Story Intelligence (6.3)

Key learnings from Story 6.3 that apply:

1. **Case-sensitive category validation**: Fixed in code review — LLM output isn't guaranteed to match case. `VALID_CATEGORIES` uses title-case and `.title()` normalization is needed. **Not relevant to this story** (no parsing changes).

2. **Case-sensitive existing term matching**: Fixed in code review — term deduplication now case-insensitive. **Not relevant** (glossary service unchanged).

3. **Import guard pattern**: AI service imports inside `if not no_ai` guard. **Already in place** — no changes to import structure.

4. **All 743 tests pass**: Baseline test count is 743. This story should not regress.

### Git Intelligence

Recent commits (last 5):
- `3a26220 chore(release): v0.3.1` — latest tag
- `57dca4b fix: doctor version check uses git tags instead of PyPI` — doctor command fix
- `f9fcdaa chore: update version to 0.3.0` — version bump
- `d467b8c chore(release): v0.3.0` — release
- `9eb837e fix: resolve pyright strict type errors in services` — type fixes

No breaking changes or architectural shifts in recent work. All AI-related code (6.1-6.3) was merged prior to v0.3.0.

### Testing Strategy

- **Parallel execution**: Use mock AI services that track call order and timing. Verify both are called (evidence of parallelism is that both complete, not sequential ordering).
- **Failure isolation**: Use mock services that raise exceptions. Verify the other task's results are applied.
- **Token aggregation**: Set specific token values in mock results and verify the sum in `SyncResult`.
- **Progress callback**: Use a recording callback and verify it receives "start" and summary messages.
- **First-run detection**: Use `tmp_path` fixture to create project directory with/without `.ai_seen` marker. Verify message output and marker creation.
- **Display tests**: Use `io.StringIO` or mock console to capture Rich output and verify format.
- **No real threading needed in tests**: The futures and executor can be tested synchronously since mock services complete instantly.

### File Inventory

| File | Action | Purpose |
|------|--------|---------|
| `src/nest/services/sync_service.py` | MODIFY | Replace sequential AI with parallel executor; add `_run_glossary()`, `_collect_enrichment_result()`, `_collect_glossary_result()` methods; add `ai_progress_callback` param |
| `src/nest/cli/sync_cmd.py` | MODIFY | Aggregated token display; first-run detection with marker file; AI progress callback wiring; pass `ai_detected_key` and `project_root` to display |
| `src/nest/core/paths.py` | MODIFY | Add `AI_SEEN_MARKER` constant |
| `tests/services/test_sync_service.py` | MODIFY | Add parallel execution, failure isolation, token aggregation, progress callback tests |
| `tests/cli/test_sync_cmd.py` | MODIFY | Add aggregated display, first-run detection tests |

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.4] — AC, story description, dependencies
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6] — Epic scope and design principles
- [Source: _bmad-output/planning-artifacts/architecture.md#Layer Boundaries] — Service/adapter/core layer rules
- [Source: _bmad-output/planning-artifacts/architecture.md#Protocol Boundaries] — DI via protocols
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Flow: Sync Command] — Sync execution flow
- [Source: _bmad-output/project-context.md#Architecture & Dependency Injection] — Protocol-based DI pattern
- [Source: _bmad-output/project-context.md#Testing Rules] — Test naming, AAA pattern, mock strategy
- [Source: _bmad-output/project-context.md#CLI Output Patterns] — Rich console output rules
- [Source: _bmad-output/implementation-artifacts/6-1-llm-provider-adapter-and-ai-detection.md] — Foundation story, adapter API, thread safety of openai SDK
- [Source: _bmad-output/implementation-artifacts/6-2-ai-index-enrichment-in-sync.md] — AI enrichment pattern, SyncService integration, `--no-ai` flag
- [Source: _bmad-output/implementation-artifacts/6-3-ai-glossary-generation-in-sync.md] — AI glossary pattern, learnings from code review
- [Source: src/nest/services/sync_service.py] — Current sync flow with sequential AI execution
- [Source: src/nest/services/ai_enrichment_service.py] — AIEnrichmentService.enrich() API
- [Source: src/nest/services/ai_glossary_service.py] — AIGlossaryService.generate() API
- [Source: src/nest/cli/sync_cmd.py] — Composition root and display summary
- [Source: src/nest/core/models.py#SyncResult] — Result model with token fields
- [Source: src/nest/core/models.py#AIEnrichmentResult] — Enrichment result model
- [Source: src/nest/core/models.py#AIGlossaryResult] — Glossary result model
- [Source: src/nest/core/paths.py] — Path constants
- [Source: src/nest/adapters/llm_provider.py] — OpenAI adapter and factory function
- [Source: src/nest/ui/progress.py] — SyncProgress class for Rich progress display

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Pyright strict caught untyped `list` in progress callback summary builder → fixed with `list[str]` annotation.
- Ruff caught 9 lint issues (import sorting, line length, unused import `io`, ambiguous var name `l` → `line`). All auto-fixed or manually resolved.

### Completion Notes List

- Task 4.2 deviated from story: `ai_detected_key` NOT added to `SyncResult` model — it's a CLI presentation concern, detected in `sync_cmd.py` via `os.environ` and passed directly to `_display_sync_summary()`. Keeps `SyncResult` free of UX fields.
- All 20 new tests cover: parallel execution (both/either/neither), failure isolation (enrich fails, glossary fails, both fail), token aggregation, progress callback (start/summary/no-work), aggregated token display (with/without tokens, enrichment counts, glossary counts), first-run detection (message shown, marker created, subsequent suppressed, no-AI no-message).
- Baseline: 743 → Final: 763 tests. Zero regressions.

### Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 | **Date:** 2026-03-05
**Result:** Approved with fixes applied

**Findings (4 total, all fixed):**

1. **HIGH — Sequential AI paths lacked exception handling (AC2).** The `elif has_enrichment_work` and `elif has_glossary_work` branches called services directly without try/except, causing sync to crash on failure. Parallel paths correctly used `_collect_*_result()` wrappers. **Fix:** Wrapped both sequential paths in try/except with `logger.exception()`, matching the parallel path behavior. Added 2 new tests: `test_sync_sequential_enrichment_failure_degrades_gracefully`, `test_sync_sequential_glossary_failure_degrades_gracefully`.
2. **MEDIUM — Missing docstring for `ai_progress_callback` param in `SyncService.sync()`.** **Fix:** Added Args entry.
3. **MEDIUM — Missing docstring for `ai_detected_key` and `project_root` params in `_display_sync_summary()`.** **Fix:** Added Args entries.
4. **LOW — Unicode escape sequences (`\U0001f916`, `\U0001f4a1`) instead of emoji literals.** Rest of file uses emoji chars directly (e.g., `🔍`). **Fix:** Replaced with `🤖` and `💡` literals.

**Post-fix verification:** 765 passed (763 + 2 new), lint clean, pyright strict clean.

### File List

| File | Action |
|------|--------|
| `src/nest/services/sync_service.py` | MODIFIED — parallel AI executor, `_run_glossary()`, `_collect_enrichment_result()`, `_collect_glossary_result()`, `ai_progress_callback` param |
| `src/nest/cli/sync_cmd.py` | MODIFIED — aggregated token display, first-run detection with `.ai_seen` marker, AI progress callback wiring |
| `src/nest/core/paths.py` | MODIFIED — added `AI_SEEN_MARKER` constant |
| `tests/services/test_sync_service.py` | MODIFIED — 14 new tests in `TestSyncParallelAI` class (12 original + 2 from code review) |
| `tests/cli/test_sync_cmd.py` | MODIFIED — 8 new tests in `TestDisplaySyncSummaryAggregatedTokens` and `TestDisplaySyncSummaryFirstRun` classes |

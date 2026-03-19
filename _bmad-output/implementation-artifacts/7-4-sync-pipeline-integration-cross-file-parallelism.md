# Story 7.4: Sync Pipeline Integration & Cross-File Parallelism

Status: done

## Dev Agent Record

### Code Review Record

**Reviewer:** Amelia (Dev Agent, adversarial mode) | **Date:** 2026-03-19

#### Findings & Fixes

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | HIGH | Missing test: Phase 1 `convert()` failure (task 2.6 implemented but untested — no test validated `failed_count` increment, manifest failure, and `describe()` never called) | Fixed: added `test_vision_phase1_convert_failure_counted_as_failed` |
| 2 | HIGH | Missing test: `on_error="fail"` with Phase 2 describe failure (task 2.5 fail-mode code path existed but had zero test coverage) | Fixed: added `test_vision_describe_failure_raises_on_fail_mode` |
| 3 | MEDIUM | `progress_callback` not called on Phase 1 `convert()` failure — standard docling and passthrough failure paths both call it; vision convert exception handler did not | Fixed: added `progress_callback` call in Phase 1 exception handler before the `on_error=="fail"` raise |
| 4 | MEDIUM | `ThreadPoolExecutor()` in Phase 2 has no `max_workers` bound (sibling AI executor uses `max_workers=2`); many vision files could spawn 32+ threads and trigger API rate-limiting | Action item added below |
| 5 | LOW | Single commit `71ee67f` bundles all of Epic 7 source files (7.1–7.4); per-story `git blame`/`git bisect` granularity lost | Noted — no code change required |

#### Review Action Items

- [ ] [AI-Review][MEDIUM] Consider adding `max_workers` cap to Phase 2 `ThreadPoolExecutor` in `SyncService.sync()` to prevent API rate-limiting on large syncs. Suggested: `max_workers=min(4, len(deferred_vision))` or a configurable constant. [`src/nest/services/sync_service.py`]

#### Test Results After Fixes

- Vision pipeline tests: **18 passed** (16 original + 2 new)
- Full non-E2E suite: **887 passed**, 59 deselected (baseline was 885 — +2 new tests)

### Implementation Summary

**Agent:** Amelia (Dev Agent) | **Date:** 2026-03-19 | **Branch:** `feat/7-4-sync-pipeline-integration-cross-file-parallelism`

#### What was implemented

- **Task 1 — `SyncResult` vision fields** (`src/nest/core/models.py`): Added 5 new fields: `vision_prompt_tokens`, `vision_completion_tokens`, `images_described`, `images_mermaid`, `images_skipped`.

- **Task 2 — Two-phase sync loop** (`src/nest/services/sync_service.py`): Added `picture_description_service` and `vision_docling_processor` parameters to `__init__()` with TYPE_CHECKING guards. Replaced single-path processing loop with a three-branch Phase 1 (passthrough / vision-eligible / standard docling) + Phase 2 concurrent `ThreadPoolExecutor` for `PictureDescriptionService.describe()` across deferred files. Vision stats accumulated per future result.

- **Task 3 — Vision wiring** (`src/nest/cli/sync_cmd.py`): Extended `create_sync_service()` to call `create_vision_provider()` when `not no_ai`, create `ClassificationProcessor(enable_classification=True)` and `PictureDescriptionService`, passing both to `SyncService`.

- **Task 4 — Summary display** (`src/nest/cli/sync_cmd.py`): Updated `_display_sync_summary()` to aggregate `vision_prompt_tokens`/`vision_completion_tokens` into the existing `AI tokens:` line, added "Images described: N (M as Mermaid diagrams)" and "Images skipped: N" lines, and extended `ai_was_used` check to include vision activity.

- **Helper** (`src/nest/services/output_service.py`): Added public `compute_docling_output_path()` to `OutputMirrorService` to expose filesystem path computation without breaking encapsulation.

- **Task 5 — `test_sync_service.py`**: Added `TestSyncVisionPipeline` class (7 tests) covering vision pipeline triggered, standard path fallback, passthrough unaffected, token aggregation across files, describe failure handling, cross-file parallelism manifest recording, zero fields when no vision.

- **Task 6 — `test_sync_cmd.py`**: Added `TestDisplaySyncSummaryVisionStats` class (9 tests) covering mermaid note display, no-mermaid display, no images, skipped shown/hidden, vision tokens in total, vision-only tokens, vision triggers first-run message, no_ai disables vision.

#### Decisions

- Used **Option A** (public `compute_docling_output_path()` on `OutputMirrorService`) over Option B (inline replication) to preserve encapsulation.
- Fixed a structural bug during implementation where the `else:` (standard docling) try-except block was accidentally nested inside the vision path's `except Exception as e:` block. Detected via ruff B025/B904 — corrected before commit.
- Pre-existing ruff `F841` in `ai_glossary_service.py` and pyright `reportUnknownMemberType` in `sync_service.py` confirmed pre-existing via git stash test; not this story's scope.

#### Test Results

- `tests/services/test_sync_service.py tests/cli/test_sync_cmd.py`: **96 passed** (16 new)
- Full non-E2E suite: **885 passed**, 59 deselected (baseline was 869 — +16 new tests)

### File List

| File | Change |
|------|--------|
| `src/nest/core/models.py` | Added 5 vision fields to `SyncResult` |
| `src/nest/services/sync_service.py` | Two-phase loop, 2 new init params, vision stats; +`progress_callback` call in Phase 1 convert() failure handler (code review fix) |
| `src/nest/services/output_service.py` | Added `compute_docling_output_path()` |
| `src/nest/cli/sync_cmd.py` | Vision wiring in `create_sync_service()` + summary display |
| `tests/services/test_sync_service.py` | Added `TestSyncVisionPipeline` (7 tests); +2 tests for Phase 1 convert failure and on_error="fail" describe failure (code review additions) |
| `tests/cli/test_sync_cmd.py` | Added `TestDisplaySyncSummaryVisionStats` (9 tests) |

## Story

As a **user running `nest sync` on documents with images**,
I want **image descriptions generated during sync without blocking other files**,
So that **my sync completes as fast as possible**.

## Business Context

This is **story 4 of 5 in Epic 7** (Image Description via Vision LLM). Epic 7 delivers FR34–FR38.

- **Story 7.1** built the vision adapter layer (`VisionLLMProviderProtocol`, `OpenAIVisionAdapter`, `AzureOpenAIVisionAdapter`, `create_vision_provider()`).
- **Story 7.2** adapted `DoclingProcessor` to support `enable_classification=True` and `convert()` returning raw `ConversionResult`.
- **Story 7.3** implemented `PictureDescriptionService.describe()` — the Pass 2 service layer.
- **Story 7.4** (THIS STORY) wires `PictureDescriptionService` into the sync pipeline and adds **cross-file parallelism** so that description LLM calls for multiple files can overlap.
- **Story 7.5** adds E2E tests.

**Key design principle:** Docling conversion (Pass 1) remains sequential because the `DocumentConverter` instance should not be called concurrently on the same object. However, LLM API calls for image descriptions (Pass 2) are I/O-bound and CAN run concurrently across multiple files. Story 7.4 achieves this by adopting a **two-phase approach** in `SyncService`: convert files sequentially, then run descriptions across all converted files in a shared `ThreadPoolExecutor`.

**What this story does NOT touch** (locked by previous stories):
- `PictureDescriptionService` internals (Story 7.3 — complete)
- `DoclingProcessor.convert()` and the classification pipeline (Story 7.2 — complete)
- Vision adapter classes (`OpenAIVisionAdapter`, `AzureOpenAIVisionAdapter`) (Story 7.1 — complete)
- E2E tests (Story 7.5 scope)

## Acceptance Criteria

### AC1: Cross-File Parallelism

**Given** `nest sync` processes file A (10 images) and file B (5 images)
**When** both files are converted by Docling
**Then** image description for file A and file B can run concurrently
**And** file B's markdown output is written as soon as file B's descriptions complete (does not wait for file A)

### AC2: Single-File Vision Pipeline Flow

**Given** the sync loop processes a file with images
**When** AI is configured and vision provider is available
**Then** the flow is:
1. Docling converts document with classification + image extraction (Pass 1) via `DoclingProcessor.convert()`
2. `PictureDescriptionService.describe()` runs on the `ConversionResult` (Pass 2, parallel LLM calls within the file)
3. Descriptions stored in-place on `PictureItem` elements via `PictureDescriptionData`
4. `result.document.export_to_markdown()` produces final markdown with descriptions inline
5. Markdown written to output
6. Manifest updated

### AC3: `--no-ai` Disables Vision

**Given** `--no-ai` flag is passed
**When** sync runs
**Then** image extraction and classification are disabled (`enable_classification=False` on `DoclingProcessor`)
**And** `ImageRefMode.PLACEHOLDER` is used (existing behavior — `[Image: ...]` markers)
**And** no vision LLM calls are made

### AC4: Graceful Degradation (No Vision Config)

**Given** AI env vars are configured for text enrichment but `NEST_AI_VISION_MODEL` and `OPENAI_VISION_MODEL` env vars are absent or the vision model is unavailable
**When** `create_vision_provider()` returns `None`
**Then** sync continues normally with `ImageRefMode.PLACEHOLDER` for images
**And** text enrichment (AI enrichment + glossary) still runs normally

### AC5: Sync Summary — Image Description Output

**Given** sync completes with image descriptions
**When** summary is displayed
**Then** output includes: `"Images described: N (M as Mermaid diagrams)"` when M > 0
**And** when M == 0: `"Images described: N"`
**And** `"Images skipped: N (logos/signatures)"` when applicable (N > 0)
**And** vision tokens are aggregated into the existing `AI tokens:` line

### AC6: Token Aggregation

**Given** sync runs with vision descriptions that consumed tokens
**When** the sync summary is displayed
**Then** the existing `"AI tokens:"` line aggregates prompt/completion tokens from: text enrichment + glossary + vision
**And** a separate breakdown is NOT shown for vision (included in existing aggregated display)

### AC7: Existing Tests Pass

**Given** all existing tests
**When** this change is integrated
**Then** all unit, integration, and non-E2E tests pass without modification
**And** new tests cover: sync service vision aggregation, sync_cmd summary display with vision stats, DoclingProcessor two-pass path

## Tasks / Subtasks

### Task 1: Extend `SyncResult` with vision fields in `models.py` (AC: 5, 6)

- [x] 1.1: Add the following fields to `SyncResult` after `ai_glossary_completion_tokens`:
  ```python
  vision_prompt_tokens: int = 0
  vision_completion_tokens: int = 0
  images_described: int = 0
  images_mermaid: int = 0
  images_skipped: int = 0
  ```
- [x] 1.2: No new imports needed in `models.py` (all types already present)
- **File:** `src/nest/core/models.py`

### Task 2: Extend `SyncService` to orchestrate vision pipeline (AC: 1, 2, 3, 4, 6)

- [x] 2.1: Add `picture_description_service: PictureDescriptionService | None = None` parameter to `SyncService.__init__()` (use `TYPE_CHECKING` guard — see Dev Notes)
- [x] 2.2: Store as `self._picture_description_service` (typed as `PictureDescriptionService | None`)
- [x] 2.3: Add `_vision_docling_processor: DoclingProcessor | None = None` parameter to `__init__()` for the classification-enabled processor (used when vision is active; TYPE_CHECKING guard)
- [x] 2.4: In `SyncService.sync()`, replace the sequential processing loop with a **two-phase approach** when vision is active:
  - **Phase 1 (sequential):** For each file in `files_to_process`:
    - If it's a passthrough file: process immediately via `self._output.process_file()` (unchanged path)
    - If it's a docling file AND vision is active: call `self._vision_docling_processor.convert(file_info.path)` — collect `(file_info, ConversionResult, output_path)` into a deferred list
    - If it's a docling file AND vision is NOT active: process immediately via `self._output.process_file()` (unchanged path)
  - **Phase 2 (concurrent description):** Submit each deferred `(conv_result, output_dir)` to a `ThreadPoolExecutor` calling `self._picture_description_service.describe(conv_result)`. As each future completes via `as_completed`:
    - Export to markdown: `conv_result.document.export_to_markdown(image_mode=ImageRefMode.PLACEHOLDER)` — descriptions stored in-place produce inline text; images without descriptions produce `[Image: ...]` placeholders
    - Write markdown to output path (ensure parent dir exists first)
    - Record success in manifest
    - Accumulate vision token and image count totals
- [x] 2.5: Handle errors in Phase 2 (description exceptions): catch, log, count as `failed_count`, call `manifest.record_failure()`, continue with other files (respect `on_error` flag: raise `ProcessingError` on `fail` mode)
- [x] 2.6: Handle errors in Phase 1 Docling convert (exceptions from `convert()`): catch, log, count as `failed_count`, call `manifest.record_failure()`, continue
- [x] 2.7: Compute output path for vision-converted files using the existing output path computation. Use `self._output._filesystem.compute_output_path(source, raw_inbox, output_dir)` — or extract path logic consistently with how `OutputMirrorService` does it (see Dev Notes for exact pattern)
- [x] 2.8: Accumulate `images_described`, `images_mermaid`, `images_skipped`, `vision_prompt_tokens`, `vision_completion_tokens` from each `PictureDescriptionResult`
- [x] 2.9: Include accumulated vision fields in the returned `SyncResult`:
  ```python
  return SyncResult(
      ...  # existing fields
      vision_prompt_tokens=vision_prompt_tokens,
      vision_completion_tokens=vision_completion_tokens,
      images_described=images_described,
      images_mermaid=images_mermaid,
      images_skipped=images_skipped,
  )
  ```
- [x] 2.10: Progress callback still works — call `progress_callback(file_info.path.name)` after each file completes in either phase (passthrough immediately, vision files as their description future resolves)
- **File:** `src/nest/services/sync_service.py`

### Task 3: Update `create_sync_service()` in `sync_cmd.py` to wire vision (AC: 3, 4)

- [x] 3.1: In `create_sync_service()`, after existing AI enrichment setup, add vision setup:
  ```python
  vision_provider = None
  picture_description_service = None
  if not no_ai:
      from nest.adapters.llm_provider import create_vision_provider
      vision_provider = create_vision_provider()
      if vision_provider is not None:
          from nest.services.picture_description_service import PictureDescriptionService
          picture_description_service = PictureDescriptionService(vision_provider=vision_provider)
  ```
- [x] 3.2: Create the classification-enabled `DoclingProcessor` when vision is configured:
  ```python
  if vision_provider is not None:
      from nest.adapters.docling_processor import DoclingProcessor as VisionDoclingProcessor
      vision_docling_processor = VisionDoclingProcessor(enable_classification=True)
  else:
      vision_docling_processor = None
  ```
- [x] 3.3: Pass `picture_description_service=picture_description_service` and `vision_docling_processor=vision_docling_processor` to the `SyncService(...)` constructor
- [x] 3.4: The existing `DoclingProcessor()` (used in `OutputMirrorService`) remains (`enable_classification=False` — standard pipeline for non-vision files). When vision IS active, vision-eligible docling files bypass `OutputMirrorService` entirely (handled in `SyncService` Phase 2). Passthrough files still go through `OutputMirrorService`.
- **File:** `src/nest/cli/sync_cmd.py`

### Task 4: Update `_display_sync_summary()` in `sync_cmd.py` (AC: 5, 6)

- [x] 4.1: Include vision tokens in the existing aggregated token total:
  ```python
  total_prompt = (
      result.ai_prompt_tokens
      + result.ai_glossary_prompt_tokens
      + result.vision_prompt_tokens
  )
  total_completion = (
      result.ai_completion_tokens
      + result.ai_glossary_completion_tokens
      + result.vision_completion_tokens
  )
  ```
- [x] 4.2: After the existing `"AI enriched:"` and `"AI glossary:"` lines, add image description summary:
  ```python
  if result.images_described > 0:
      mermaid_note = f" ({result.images_mermaid} as Mermaid diagrams)" if result.images_mermaid > 0 else ""
      console.print(f"  Images described: {result.images_described}{mermaid_note}")
  if result.images_skipped > 0:
      console.print(f"  Images skipped:  {result.images_skipped} (logos/signatures)")
  ```
- [x] 4.3: `ai_was_used` check: add `images_described > 0` or `vision_prompt_tokens > 0` to the `ai_was_used` boolean so the first-run AI discovery marker is shown when vision is used even if text enrichment has no work
- **File:** `src/nest/cli/sync_cmd.py`

### Task 5: Write tests in `tests/services/test_sync_service.py` (AC: 1, 2, 6, 7)

- [x] 5.1: Add mock fixture for `PictureDescriptionService` and a mock `DoclingProcessor` that can `convert()`
- [x] 5.2: **Vision pipeline triggered** — when `picture_description_service` and `vision_docling_processor` are set AND a docling file is present: verify `vision_docling_processor.convert()` is called, then `pds.describe()` is called, `SyncResult.images_described > 0`, `SyncResult.vision_prompt_tokens > 0`
- [x] 5.3: **Token aggregation** — multiple docling files with images → `vision_prompt_tokens` and `vision_completion_tokens` are summed across all described files
- [x] 5.4: **No vision → existing path** — when `picture_description_service is None`: `output.process_file()` is called (unchanged path), `SyncResult.images_described == 0`
- [x] 5.5: **Passthrough files unaffected** — passthrough files always go through `output.process_file()` even when vision is active
- [x] 5.6: **Vision describe failure → file counted as failed** — when `pds.describe()` raises an exception: file counted in `failed_count`, manifest recorded as failure, other files continue
- [x] 5.7: **Cross-file parallelism** — two docling files: both description futures submitted to executor, their results aggregated correctly (verify by checking both files appear in manifest success calls)
- **File:** `tests/services/test_sync_service.py`

### Task 6: Write tests in `tests/cli/test_sync_cmd.py` (AC: 5, 6)

- [x] 6.1: **Summary shows "Images described"** — `_display_sync_summary()` with `images_described=3, images_mermaid=1` prints `"Images described: 3 (1 as Mermaid diagrams)"`
- [x] 6.2: **Summary shows "Images described" (no mermaid)** — `images_described=2, images_mermaid=0` prints `"Images described: 2"` (no Mermaid note)
- [x] 6.3: **No images → no image line** — `images_described=0, images_skipped=0` → no "Images described" line
- [x] 6.4: **Skipped images shown** — `images_skipped=4` → `"Images skipped:  4 (logos/signatures)"`
- [x] 6.5: **Vision tokens in total** — `vision_prompt_tokens=100, vision_completion_tokens=50` + existing AI tokens → `"AI tokens: N"` total includes vision
- [x] 6.6: **`create_sync_service` with no_ai=True** — vision provider NOT created, PDS NOT created, `picture_description_service` is `None`
- **File:** `tests/cli/test_sync_cmd.py`

### Task 7: CI checks

- [x] 7.1: `ruff check src/ tests/ --fix` — zero lint errors (pre-existing F841 in ai_glossary_service.py excluded)
- [x] 7.2: `pyright src/nest/services/sync_service.py src/nest/cli/sync_cmd.py src/nest/core/models.py` — zero type errors (pre-existing reportUnknownMemberType excluded) (strict mode)
- [x] 7.3: `pytest tests/services/test_sync_service.py tests/cli/test_sync_cmd.py -v` — all 96 tests green (16 new)
- [x] 7.4: `pytest -m "not e2e" -v` — full non-E2E suite green (885 passed, no regressions)

## Dev Notes

### Architecture: What is in scope vs. out of scope

| Component | File | This Story |
|-----------|------|------------|
| Vision model fields on `SyncResult` | `src/nest/core/models.py` | ✅ ADD 5 fields |
| Processing loop with two-phase vision | `src/nest/services/sync_service.py` | ✅ MODIFY |
| create_sync_service + display | `src/nest/cli/sync_cmd.py` | ✅ MODIFY |
| `PictureDescriptionService` | `src/nest/services/picture_description_service.py` | ❌ Do NOT touch |
| `DoclingProcessor` | `src/nest/adapters/docling_processor.py` | ❌ Do NOT touch (7.2 complete) |
| Vision adapters | `src/nest/adapters/llm_provider.py` | ❌ Do NOT touch |
| `VisionLLMProviderProtocol` | `src/nest/adapters/protocols.py` | ❌ Do NOT touch |
| E2E tests | `tests/e2e/` | ❌ Story 7.5 scope |

### Key Type Imports (TYPE_CHECKING pattern)

All story 7.x types follow this existing pattern:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nest.adapters.docling_processor import DoclingProcessor
    from nest.services.picture_description_service import PictureDescriptionService
```

At runtime, `DoclingProcessor` and `PictureDescriptionService` are only referenced as strings in annotations. The actual `DoclingProcessor` instance is passed in from `sync_cmd.py`'s `create_sync_service()`.

### SyncService Constructor Signature (after this story)

```python
def __init__(
    self,
    discovery: DiscoveryService,
    output: OutputMirrorService,
    manifest: ManifestService,
    orphan: OrphanService,
    index: IndexService,
    metadata: MetadataExtractorService,
    project_root: Path,
    error_logger: logging.Logger | logging.LoggerAdapter[logging.Logger] | None = None,
    ai_enrichment: AIEnrichmentService | None = None,
    ai_glossary: AIGlossaryService | None = None,
    picture_description_service: PictureDescriptionService | None = None,   # NEW
    vision_docling_processor: DoclingProcessor | None = None,               # NEW
) -> None:
```

Both new parameters are optional — no default callers break.

### Output Path Computation for Vision Files

When SyncService directly calls `DoclingProcessor.convert()` (bypassing `OutputMirrorService`), it must compute the output path manually. The pattern used by `OutputMirrorService` is:

```python
output_path = self._output._filesystem.compute_output_path(source, raw_inbox, output_dir)
```

However, accessing private members (`_filesystem`) breaks encapsulation. Instead, expose a helper on `OutputMirrorService`:

**Option A (preferred):** Add a public `compute_docling_output_path(source, raw_inbox, output_dir) -> Path` method to `OutputMirrorService` that delegates to `self._filesystem.compute_output_path()`. Then call `self._output.compute_docling_output_path(...)` from `SyncService`.

**Option B (simpler, acceptable):** Replicate the path computation inline in `SyncService` using `FileSystemAdapter.compute_output_path()`. Import `FileSystemAdapter` at the top of `sync_service.py`. NOTE: check how `OutputMirrorService` does it — `compute_output_path` replaces the suffix with `.md`.

Looking at `filesystem.py`, `compute_output_path()` handles the `raw_inbox → output_dir` mirror with `.md` suffix. You'll need access to a `FileSystemProtocol` instance. Since `SyncService` doesn't currently hold one, the cleanest approach is Option A (expose on `OutputMirrorService`).

### Two-Phase Sync Loop (Core implementation guidance)

```python
# Phase 1: Process all files, collecting vision-eligible docling files
deferred_vision: list[tuple[DiscoveredFile, Any, Path]] = []  # (file_info, conv_result, output_path)

for file_info in files_to_process:
    # Passthrough files: always go through standard path
    if is_passthrough_extension(file_info.path.suffix):
        result = self._output.process_file(file_info.path, raw_inbox, output_dir)
        # ... handle result immediately (existing logic)
        continue

    # Vision-eligible docling files
    if self._picture_description_service is not None and self._vision_docling_processor is not None:
        try:
            conv_result = self._vision_docling_processor.convert(file_info.path)
            output_path = self._output.compute_docling_output_path(file_info.path, raw_inbox, output_dir)
            deferred_vision.append((file_info, conv_result, output_path))
        except Exception as e:
            # Handle convert failure
            error_msg = str(e)
            self._manifest.record_failure(file_info.path, file_info.checksum, error_msg)
            failed_count += 1
            if self._error_logger:
                log_processing_error(self._error_logger, file_info.path, error_msg)
            if on_error == "fail":
                raise ProcessingError(f"Docling convert failed: {error_msg}", source_path=file_info.path)
        continue

    # Standard docling path (no vision)
    result = self._output.process_file(file_info.path, raw_inbox, output_dir)
    # ... handle result immediately (existing logic)

# Phase 2: Run descriptions concurrently, write results as they complete
if deferred_vision:
    from concurrent.futures import Future, ThreadPoolExecutor, as_completed
    from docling_core.types.doc.base import ImageRefMode

    with ThreadPoolExecutor() as executor:
        future_to_file: dict[Future[Any], tuple[DiscoveredFile, Any, Path]] = {
            executor.submit(self._picture_description_service.describe, conv_result): (file_info, conv_result, output_path)
            for file_info, conv_result, output_path in deferred_vision
        }
        for future in as_completed(future_to_file):
            file_info_, conv_result_, output_path_ = future_to_file[future]
            try:
                pds_result = future.result()
            except Exception as e:
                error_msg = str(e)
                self._manifest.record_failure(file_info_.path, file_info_.checksum, error_msg)
                failed_count += 1
                if self._error_logger:
                    log_processing_error(self._error_logger, file_info_.path, error_msg)
                if on_error == "fail":
                    raise ProcessingError(f"Vision describe failed: {error_msg}", source_path=file_info_.path)
                continue

            # Export markdown with descriptions embedded in-place
            markdown = conv_result_.document.export_to_markdown(
                image_mode=ImageRefMode.PLACEHOLDER,
            )
            # Write to disk
            output_path_.parent.mkdir(parents=True, exist_ok=True)
            output_path_.write_text(markdown, encoding="utf-8", newline="\n")
            # Manifest
            self._manifest.record_success(file_info_.path, file_info_.checksum, output_path_)
            processed_count += 1
            # Accumulate vision stats
            images_described += pds_result.images_described
            images_mermaid += pds_result.images_mermaid
            images_skipped += pds_result.images_skipped
            vision_prompt_tokens += pds_result.prompt_tokens
            vision_completion_tokens += pds_result.completion_tokens
            # Progress
            if progress_callback is not None:
                progress_callback(file_info_.path.name)
```

**NOTE on `export_to_markdown(image_mode=PLACEHOLDER)`:** When `PictureDescriptionData` is stored in `element.meta.description`, Docling's markdown exporter emits the description text instead of a `[Image: ...]` marker for described images. Undescribed images (skipped/failed) still get the `[Image: ...]` placeholder. This behavior is confirmed in the `docling-picture-description-guide.md`.

**NOTE on ThreadPoolExecutor workers:** Default `ThreadPoolExecutor()` (no `max_workers`) uses `min(32, os.cpu_count() + 4)`. For image description across files, this is appropriate — each file's description task runs `PictureDescriptionService.describe()` which itself uses up to 50 internal workers for LLM calls.

### `ImageRefMode` Import

```python
from docling_core.types.doc.base import ImageRefMode
```

This import already exists in `DoclingProcessor`. Add it to `sync_service.py` at the top (not inside the function) for clarity.

### `create_vision_provider()` Function Signature

Already exists in `src/nest/adapters/llm_provider.py`:

```python
def create_vision_provider() -> OpenAIVisionAdapter | AzureOpenAIVisionAdapter | None:
```

Returns `None` when no API key is found. The vision model env var chain: `NEST_AI_VISION_MODEL` → `OPENAI_VISION_MODEL` → `"gpt-4.1"`. Uses the same API key and endpoint as text enrichment.

### `create_sync_service()` Vision Wiring Pattern

Follow the existing AI enrichment pattern exactly:

```python
# Existing AI enrichment (unchanged)
ai_enrichment = None
ai_glossary = None
if not no_ai:
    from nest.adapters.llm_provider import create_llm_provider
    llm_provider = create_llm_provider()
    if llm_provider is not None:
        from nest.services.ai_enrichment_service import AIEnrichmentService
        ai_enrichment = AIEnrichmentService(llm_provider=llm_provider)
        from nest.services.ai_glossary_service import AIGlossaryService
        ai_glossary = AIGlossaryService(llm_provider=llm_provider, filesystem=filesystem)

# NEW: Vision provider (independent of text enrichment)
vision_docling_processor = None
picture_description_service = None
if not no_ai:
    from nest.adapters.llm_provider import create_vision_provider
    vision_provider = create_vision_provider()
    if vision_provider is not None:
        from nest.adapters.docling_processor import DoclingProcessor as ClassificationProcessor
        vision_docling_processor = ClassificationProcessor(enable_classification=True)
        from nest.services.picture_description_service import PictureDescriptionService
        picture_description_service = PictureDescriptionService(vision_provider=vision_provider)
```

Note: `vision_docling_processor` uses `enable_classification=True`. The existing `processor` (already instantiated at the top of `create_sync_service()`) keeps `enable_classification=False` for the standard path (used by `OutputMirrorService`).

### SyncResult Vision Fields in `_display_sync_summary()`

Insert image description display AFTER the existing `"AI glossary:"` line and BEFORE (or after) the first-run AI discovery message check:

```python
# Show image description counts
if result.images_described > 0:
    mermaid_note = (
        f" ({result.images_mermaid} as Mermaid diagrams)"
        if result.images_mermaid > 0
        else ""
    )
    console.print(f"  Images described: {result.images_described}{mermaid_note}")
if result.images_skipped > 0:
    console.print(f"  Images skipped:   {result.images_skipped} (logos/signatures)")
```

Update `ai_was_used` to include vision activity:
```python
ai_was_used = (
    result.ai_files_enriched > 0
    or result.ai_glossary_terms_added > 0
    or (result.ai_prompt_tokens + result.ai_glossary_prompt_tokens) > 0
    or result.images_described > 0           # NEW
    or result.vision_prompt_tokens > 0       # NEW
)
```

### `is_passthrough_extension` import in `sync_service.py`

Already imported at the top:
```python
from nest.core.paths import (
    CONTEXT_DIR,
    GLOSSARY_FILE,
    INDEX_HINTS_FILE,
    NEST_META_DIR,
    SOURCES_DIR,
    is_passthrough_extension,
)
```

Use it to branch between passthrough and docling file paths in the loop.

### Existing Test Count Baseline

After Story 7.3: **20 tests pass** in `test_picture_description_service.py`, **869 total non-E2E tests pass**. Do NOT reduce this count.

### Git workflow

```bash
git checkout main && git pull origin main
git checkout -b feat/7-4-sync-pipeline-integration-cross-file-parallelism
# ... implement ...
# Run CI before committing:
ruff check src/ tests/ --fix
ruff format src/ tests/
pyright src/
pytest -m "not e2e" --timeout=120
git add -A && git commit -m "feat(epic-7): wire PictureDescriptionService into sync pipeline with cross-file parallelism"
```

### Project Structure Notes

All new code lives in existing files — **no new files are created in this story**.

| File | Change |
|------|--------|
| `src/nest/core/models.py` | ADD 5 fields to `SyncResult` |
| `src/nest/services/sync_service.py` | ADD constructor params + two-phase loop |
| `src/nest/cli/sync_cmd.py` | ADD vision wiring in `create_sync_service()` + display in `_display_sync_summary()` |
| `tests/services/test_sync_service.py` | ADD vision tests |
| `tests/cli/test_sync_cmd.py` | ADD display tests |

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.4]
- [Source: _bmad-output/planning-artifacts/architecture.md#Cross-File Parallelism]
- [Source: docs/docling-picture-description-guide.md#Integration with DoclingProcessor]
- [Source: src/nest/services/sync_service.py] — existing parallel AI execution pattern (ThreadPoolExecutor with `max_workers=2`) for enrichment/glossary
- [Source: src/nest/services/picture_description_service.py] — `describe()` method and `PictureDescriptionResult` fields
- [Source: src/nest/adapters/docling_processor.py] — `convert()` method (story 7.2 — already returns `ConversionResult`)
- [Source: src/nest/adapters/llm_provider.py#create_vision_provider] — returns `None` when not configured
- [Source: src/nest/core/models.py#SyncResult] — existing AI token fields to extend
- [Source: src/nest/cli/sync_cmd.py#_display_sync_summary] — existing token aggregation pattern to extend

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

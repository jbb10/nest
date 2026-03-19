# Story 7.3: Picture Description Service

Status: complete

## Story

As a **developer building the image description pipeline**,
I want **a `PictureDescriptionService` that classifies, routes, and describes images in parallel**,
so that **diagrams produce Mermaid, photos get descriptions, and logos/signatures are skipped**.

## Business Context

This is **story 3 of 5 in Epic 7** (Image Description via Vision LLM). Epic 7 delivers FR34–FR38: automated image classification and description during `nest sync`, so the `@nest` agent can understand and reference visual content — not just text.

Story 7.1 delivered the vision adapter layer (`VisionLLMProviderProtocol`, `OpenAIVisionAdapter`, `AzureOpenAIVisionAdapter`, `create_vision_provider()`). Story 7.2 adapted `DoclingProcessor` to run Pass 1 (local image classification) and expose `ConversionResult`. Story 7.3 implements Pass 2: the `PictureDescriptionService` that reads the classified `PictureItem` elements from the `ConversionResult`, calls the vision LLM with type-specific prompts (up to 50 concurrent), and writes descriptions back into Docling's document model in-place — so that `export_to_markdown()` automatically emits them instead of `[Image: ...]` placeholders.

Story 7.4 wires `PictureDescriptionService` into the sync pipeline and handles per-file cross-file parallelism. Story 7.5 adds E2E tests.

**This story is services-layer only.** Do NOT touch `sync_service.py`, `cli/sync_cmd.py`, or any CLI code — that is story 7.4's scope.

## Acceptance Criteria

### AC1: Classification Routing

**Given** `PictureDescriptionService.describe()` receives a `ConversionResult` with classified `PictureItem` elements
**When** `describe()` iterates all `PictureItem` elements
**Then** it categorizes each using the top-confidence classification prediction:
- `flow_chart`, `block_diagram` (confidence ≥ 0.5) → call LLM with `MERMAID_PROMPT`
- `logo`, `signature` (confidence ≥ 0.5) → SKIP (no API call, counted in `images_skipped`)
- All others (`natural_image`, `bar_chart`, `line_chart`, `pie_chart`, `scatter_plot`, `table`, `map`) → call LLM with `DESCRIPTION_PROMPT`
- Elements with no classification (empty predictions or confidence < 0.5 for all labels) → call LLM with `DESCRIPTION_PROMPT` (default fallback)

### AC2: Prompt Templates

**Given** picture type is determined
**Then** `MERMAID_PROMPT` instructs the model to produce a fenced ` ```mermaid ` code block with the correct diagram type (flowchart, sequenceDiagram, classDiagram, etc.) capturing all nodes, edges, and labels — no prose
**And** `DESCRIPTION_PROMPT` instructs the model to describe the image concisely, summarize chart data points and trends, focus on technical document context

### AC3: Parallel LLM Calls (≤ 50 concurrent)

**Given** images are categorized for description (non-skipped)
**When** LLM calls are made
**Then** up to 50 concurrent calls via `ThreadPoolExecutor(max_workers=50)`
**And** each call uses `complete_with_image()` on the injected `VisionLLMProviderProtocol`
**And** the image data is extracted via `element.get_image(conversion_result.document)` and converted to base64 PNG

### AC4: In-Place Description Storage

**Given** a vision LLM call succeeds for a `PictureItem`
**When** the response text is received
**Then** `element.meta.description = PictureDescriptionData(text=response_text, created_by=model_name)`
**And** `model_name` is `self._vision_provider.model_name`
**And** descriptions are stored in-place on the `ConversionResult`'s document so that `export_to_markdown()` automatically embeds them

### AC5: 50-Image Cap

**Given** a document has > 50 describable images (non-skipped)
**When** the cap is reached
**Then** only the first 50 get LLM calls (in iteration order from `result.document.iterate_items()`)
**And** images beyond 50 keep their placeholder status (no `element.meta.description` set)
**And** images beyond the cap do NOT count as `images_failed`

### AC6: Individual Failure Isolation

**Given** an individual LLM call returns `None` (failure, already logged by adapter)
**When** `None` is returned
**Then** that image keeps its placeholder (no `PictureDescriptionData` set)
**And** it is counted in `images_failed`
**And** a `logger.warning` is emitted
**And** other images are not affected

### AC7: Image Extraction Failure

**Given** `element.get_image(doc)` returns `None` (image not extractable)
**When** this occurs
**Then** no LLM call is made for that element
**And** it is counted in `images_failed`

### AC8: Result Tallying

**Given** `describe()` completes
**When** results are tallied
**Then** `PictureDescriptionResult` is returned with:
- `images_described: int` — successfully described (mermaid + prose)
- `images_mermaid: int` — subset of described that used `MERMAID_PROMPT`
- `images_skipped: int` — logos + signatures that were intentionally skipped
- `images_failed: int` — LLM returned `None`, image was `None`, or other failure
- `prompt_tokens: int` — total from all successful LLM calls
- `completion_tokens: int` — total from all successful LLM calls

## Tasks / Subtasks

### Task 1: Add `PictureDescriptionResult` model to `src/nest/core/models.py` (AC: 8)

- [x] 1.1: Add `PictureDescriptionResult(BaseModel)` at the bottom of `models.py` (after `AIEnrichmentResult`)
- [x] 1.2: Fields: `images_described: int = 0`, `images_mermaid: int = 0`, `images_skipped: int = 0`, `images_failed: int = 0`, `prompt_tokens: int = 0`, `completion_tokens: int = 0`
- [x] 1.3: No new imports needed in `models.py` (Pydantic already imported)
- **File:** `src/nest/core/models.py`

### Task 2: Create `PictureDescriptionService` in `src/nest/services/picture_description_service.py` (AC: 1–8)

- [x] 2.1: Create the file at **exactly** `src/nest/services/picture_description_service.py` (matches architecture.md line 584)
- [x] 2.2: Module-level constants (see Dev Notes for exact strings):
  - `MERMAID_PROMPT: str`
  - `DESCRIPTION_PROMPT: str`
  - `MERMAID_LABELS: frozenset[str] = frozenset({"flow_chart", "block_diagram"})`
  - `SKIP_LABELS: frozenset[str] = frozenset({"logo", "signature"})`
  - `CONFIDENCE_THRESHOLD: float = 0.5`
  - `MAX_CONCURRENT_DESCRIPTIONS: int = 50`
- [x] 2.3: Class `PictureDescriptionService`:
  - `__init__(self, vision_provider: VisionLLMProviderProtocol) -> None` using `TYPE_CHECKING` guard for import
  - Private `_vision_provider` attribute
- [x] 2.4: Public method `describe(self, conversion_result: ConversionResult) -> PictureDescriptionResult`:
  - **Phase 1**: Iterate `conversion_result.document.iterate_items()`, collect all `PictureItem` instances
  - **Phase 2**: For each `PictureItem`, call `_classify(element)` to get `(label, confidence)`
  - **Phase 3**: Categorize into `skip_list`, `mermaid_list`, `description_list`; apply 50-cap to `mermaid_list + description_list` combined
  - **Phase 4**: Skip items in `skip_list` (increment `images_skipped`)
  - **Phase 5**: Submit capped items to `ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DESCRIPTIONS)`; each future calls `_describe_one(element, prompt, conversion_result)`
  - **Phase 6**: Collect futures, extract tokens, set `element.meta.description` in-place, tally counters
  - **Phase 7**: Return `PictureDescriptionResult(...)`
- [x] 2.5: Private `_classify(self, element: PictureItem) -> tuple[str | None, float]`:
  - Returns `(best_label, best_confidence)` from `element.meta.classification.predictions`
  - Returns `(None, 0.0)` if no classification exists
- [x] 2.6: Private `_describe_one(self, element: PictureItem, prompt: str, conversion_result: ConversionResult) -> LLMCompletionResult | None`:
  - Calls `element.get_image(conversion_result.document)` → returns PIL `Image` or `None`
  - Returns `None` immediately if image is `None`
  - Converts PIL image to PNG base64 using `io.BytesIO` + `base64.b64encode`
  - Calls `self._vision_provider.complete_with_image(prompt, image_base64, "image/png")`
  - Returns the `LLMCompletionResult | None` (never raises — adapter handles errors)
- [x] 2.7: Imports (see Dev Notes for exact import paths):
  - Standard library: `import base64`, `import io`, `import logging`, `from concurrent.futures import ThreadPoolExecutor, as_completed`
  - Docling: `from docling.datamodel.document import ConversionResult`, `from docling_core.types.doc.document import PictureItem` (corrected: not from types.doc), `from docling_core.types.doc.document import DescriptionMetaField`
  - Local: `from nest.core.models import LLMCompletionResult, PictureDescriptionResult`
  - TYPE_CHECKING: `from nest.adapters.protocols import VisionLLMProviderProtocol`
- **File:** `src/nest/services/picture_description_service.py` (NEW FILE)

### Task 3: Write tests in `tests/services/test_picture_description_service.py` (AC: 1–8)

- [x] 3.1: **Mock infrastructure** — `MockVisionProvider` with `complete_with_image` returning configured responses; `make_picture_item(label, confidence)` helper; `make_conversion_result(items)` helper
- [x] 3.2: **Routing: mermaid** — `flow_chart` with confidence ≥ 0.5 → `MERMAID_PROMPT` used; result counted in `images_mermaid`
- [x] 3.3: **Routing: mermaid** — `block_diagram` with confidence ≥ 0.5 → `MERMAID_PROMPT` used
- [x] 3.4: **Routing: skip** — `logo` with confidence ≥ 0.5 → no LLM call; counted in `images_skipped`
- [x] 3.5: **Routing: skip** — `signature` with confidence ≥ 0.5 → no LLM call; counted in `images_skipped`
- [x] 3.6: **Routing: description** — `natural_image`, `bar_chart`, `pie_chart` → `DESCRIPTION_PROMPT` used
- [x] 3.7: **Routing: low confidence** — `flow_chart` with confidence < 0.5 → treated as DESCRIPTION (not mermaid)
- [x] 3.8: **Routing: no classification** — `PictureItem` with empty predictions → treated as DESCRIPTION (default fallback)
- [x] 3.9: **Description stored in-place** — after `describe()`, `element.meta.description.text` equals the LLM response
- [x] 3.10: **`created_by` uses model_name** — `element.meta.description.created_by` equals `vision_provider.model_name`
- [x] 3.11: **50-image cap** — 55 describable images → only 50 get LLM calls, 5 no calls, not counted as failed
- [x] 3.12: **LLM returns None → images_failed** — `complete_with_image` returns `None` → element gets no description, counted in `images_failed`
- [x] 3.13: **Image None → images_failed** — `element.get_image()` returns `None` → counted in `images_failed`
- [x] 3.14: **Token aggregation** — multiple successful calls → `prompt_tokens` and `completion_tokens` sum correctly
- [x] 3.15: **Empty document** — `ConversionResult` with no `PictureItem` elements → returns `PictureDescriptionResult()` with all zeros
- [x] 3.16: **Mixed document** — document with mermaid + skip + description + fail → all counters correct
- **File:** `tests/services/test_picture_description_service.py` (NEW FILE)

### Task 4: CI checks

- [x] 4.1: `ruff check src/ tests/ --fix` — zero lint errors
- [x] 4.2: `pyright src/nest/services/picture_description_service.py` — zero type errors (strict mode)
- [x] 4.3: `pytest tests/services/test_picture_description_service.py -v` — all tests green (20/20)
- [x] 4.4: `pytest -m "not e2e" -v` — full non-E2E suite green (869 passed)

## Dev Notes

### Architecture Layer Compliance

Story 7.3 is **services-layer only**. The following are OUT OF SCOPE and must NOT be touched:

| Layer | Files | Status |
|-------|-------|--------|
| `src/nest/cli/` | `sync_cmd.py`, `main.py` | ❌ Do NOT touch |
| `src/nest/services/` | `sync_service.py`, `output_service.py` | ❌ Do NOT touch |
| `src/nest/adapters/` | `docling_processor.py`, `protocols.py`, `llm_provider.py` | ❌ Do NOT touch |
| `src/nest/core/` | `models.py` | ✅ ADD `PictureDescriptionResult` only |

Story 7.4 handles sync pipeline integration (wiring `PictureDescriptionService` into `SyncService`/`sync_cmd.py`).

### File Locations

| Component | File | Action |
|-----------|------|--------|
| New model | `src/nest/core/models.py` | ADD `PictureDescriptionResult` |
| New service | `src/nest/services/picture_description_service.py` | CREATE |
| New tests | `tests/services/test_picture_description_service.py` | CREATE |

### Exact Prompt Constants

Copy these verbatim as module-level constants in `picture_description_service.py`:

```python
MERMAID_PROMPT = (
    "This image contains a diagram or flowchart. "
    "Reproduce it as a Mermaid diagram in a fenced ```mermaid code block. "
    "Use the correct Mermaid diagram type (flowchart, sequenceDiagram, classDiagram, etc.). "
    "Capture all nodes, edges, and labels. Do not add a prose description."
)

DESCRIPTION_PROMPT = (
    "Describe this image concisely and accurately. "
    "If it contains a chart or graph, summarize the key data points and trends. "
    "Focus on information that would be useful in a technical document."
)

MERMAID_LABELS: frozenset[str] = frozenset({"flow_chart", "block_diagram"})
SKIP_LABELS: frozenset[str] = frozenset({"logo", "signature"})
CONFIDENCE_THRESHOLD: float = 0.5
MAX_CONCURRENT_DESCRIPTIONS: int = 50
```

### Exact Docling Import Paths (CRITICAL — Verified from Story 7.2)

These are the actual verified import paths from the working codebase:

```python
from docling.datamodel.document import ConversionResult
from docling_core.types.doc import PictureItem
from docling_core.types.doc.document import PictureDescriptionData
```

### VisionLLMProviderProtocol Import (TYPE_CHECKING pattern)

Follow the existing `TYPE_CHECKING` pattern used across the codebase:

```python
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nest.adapters.protocols import VisionLLMProviderProtocol
```

### PIL Image → Base64 Conversion

`element.get_image(document)` returns a `PIL.Image.Image | None`. Convert it to base64 PNG like this:

```python
import base64
import io

buffer = io.BytesIO()
image.save(buffer, format="PNG")
image_b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
mime_type = "image/png"
```

Then call: `self._vision_provider.complete_with_image(prompt, image_b64, mime_type)`

### `PictureDescriptionData` Usage

```python
from docling_core.types.doc.document import PictureDescriptionData

element.meta.description = PictureDescriptionData(
    text=result.text,
    created_by=self._vision_provider.model_name,
)
```

After this, `conversion_result.document.export_to_markdown()` automatically embeds the description inline.

### Classification Extraction Pattern

```python
def _classify(self, element: PictureItem) -> tuple[str | None, float]:
    if not element.meta or not element.meta.classification:
        return None, 0.0
    best_label: str | None = None
    best_confidence: float = 0.0
    for pred in element.meta.classification.predictions:
        if pred.confidence > best_confidence:
            best_label = pred.class_name
            best_confidence = pred.confidence
    return best_label, best_confidence
```

### Parallel Execution Pattern (ThreadPoolExecutor)

Key: collect futures using `as_completed` so description-writing is interleaved with API calls:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DESCRIPTIONS) as executor:
    future_to_item = {
        executor.submit(self._describe_one, element, prompt, conversion_result): (element, is_mermaid)
        for element, prompt, is_mermaid in pending[:MAX_CONCURRENT_DESCRIPTIONS]
    }
    for future in as_completed(future_to_item):
        element, is_mermaid = future_to_item[future]
        llm_result = future.result()  # _describe_one never raises
        if llm_result is None:
            images_failed += 1
            logger.warning("Vision LLM call failed for image in %s", conversion_result.input.file)
        else:
            element.meta.description = PictureDescriptionData(
                text=llm_result.text,
                created_by=self._vision_provider.model_name,
            )
            images_described += 1
            if is_mermaid:
                images_mermaid += 1
            prompt_tokens += llm_result.prompt_tokens
            completion_tokens += llm_result.completion_tokens
```

### Classification Routing Decision Table

| Top label | Confidence | Action | Count field |
|-----------|------------|--------|-------------|
| `flow_chart` | ≥ 0.5 | `MERMAID_PROMPT` | `images_mermaid`, `images_described` |
| `block_diagram` | ≥ 0.5 | `MERMAID_PROMPT` | `images_mermaid`, `images_described` |
| `logo` | ≥ 0.5 | SKIP | `images_skipped` |
| `signature` | ≥ 0.5 | SKIP | `images_skipped` |
| Any other label | ≥ 0.5 | `DESCRIPTION_PROMPT` | `images_described` |
| Any label | < 0.5 | `DESCRIPTION_PROMPT` | `images_described` |
| No predictions | — | `DESCRIPTION_PROMPT` | `images_described` |
| LLM returns `None` | — | no description set | `images_failed` |
| `element.get_image()` is `None` | — | no LLM call | `images_failed` |
| Image #51+ (beyond cap) | — | no LLM call | (not failed) |

### Testing Pattern: Mocking PictureItem and ConversionResult

`PictureItem` and `ConversionResult` are complex Docling types. Use `MagicMock` to construct test doubles:

```python
from unittest.mock import MagicMock
from docling_core.types.doc import PictureItem
from docling_core.types.doc.document import PictureDescriptionData
from nest.core.models import LLMCompletionResult

def make_picture_item(
    label: str | None = "natural_image",
    confidence: float = 0.9,
    image_data: bytes | None = b"fake-png-bytes",
) -> MagicMock:
    """Build a mock PictureItem with classification."""
    item = MagicMock(spec=PictureItem)
    if label is not None:
        pred = MagicMock()
        pred.class_name = label
        pred.confidence = confidence
        item.meta.classification.predictions = [pred]
    else:
        item.meta.classification = None
    # get_image() returns a mock PIL image
    if image_data is not None:
        mock_image = MagicMock()
        def save_side_effect(buf: io.BytesIO, format: str) -> None:
            buf.write(image_data)
        mock_image.save.side_effect = save_side_effect
        item.get_image.return_value = mock_image
    else:
        item.get_image.return_value = None
    item.meta.description = None  # start with no description
    return item


def make_conversion_result(items: list[MagicMock]) -> MagicMock:
    """Build a mock ConversionResult exposing given items only."""
    conv = MagicMock()
    # iterate_items() yields (element, level) pairs
    conv.document.iterate_items.return_value = [(item, 1) for item in items]
    conv.input.file = "test.pdf"
    return conv


class MockVisionProvider:
    def __init__(self, responses: list[LLMCompletionResult | None]) -> None:
        self._responses = iter(responses)
        self.calls: list[tuple[str, str, str]] = []

    @property
    def model_name(self) -> str:
        return "mock-vision-model"

    def complete_with_image(
        self, prompt: str, image_base64: str, mime_type: str = "image/png"
    ) -> LLMCompletionResult | None:
        self.calls.append((prompt, image_base64, mime_type))
        return next(self._responses, None)
```

### `isinstance` Filtering in `iterate_items()`

The service must filter items from `iterate_items()` using `isinstance`:

```python
from docling_core.types.doc import PictureItem

for element, _level in conversion_result.document.iterate_items():
    if not isinstance(element, PictureItem):
        continue
    # process element
```

In tests with `MagicMock(spec=PictureItem)`, `isinstance(..., PictureItem)` will return `True` because `spec=PictureItem` sets `__class__` correctly. Verify this in test setup.

### Previous Story Learnings (Story 7.2 → Story 7.3)

From story 7.2 dev notes and implementation:
- **`DoclingProcessor.convert(source)` is the Pass 1 entry point** — returns `ConversionResult` with classified `PictureItem` elements
- **`ImageRefMode.PLACEHOLDER`** is used in `process()` since descriptions are not injected until story 7.4  
- **`_converter.convert()` vs `self.convert()`** — `DoclingProcessor.convert()` is a public method separate from the Protocol `process()` — do NOT modify `DoclingProcessor`
- **No changes to `protocols.py`** were needed in 7.2 — same applies to 7.3 (`VisionLLMProviderProtocol` is already defined)
- **import sort** was fixed by ruff in 7.2 code review — always run `ruff check --fix` before committing

### Ruff/Pyright Compliance Rules

- **No `from typing import Optional, List`** — use `str | None` and `list[...]`
- **Explicit return types on ALL public methods**
- **`from __future__ import annotations`** at top of new file
- **Absolute imports only** — `from nest.services...` not `from ..services...`
- **`frozenset` literal** — `frozenset({"a", "b"})` not `set(["a", "b"])`
- **`logger = logging.getLogger(__name__)`** at module level

### Project Structure Notes

- `picture_description_service.py` is already listed in `architecture.md` (line 584) — this confirms the exact file location
- `src/nest/services/__init__.py` does NOT need updating (services are imported directly)
- No new CLI commands in this story

### References

- [Source: docs/docling-picture-description-guide.md] — Complete guide including prompt templates, classification labels, and Pass 2 pattern
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.3] — Acceptance criteria and story definition
- [Source: _bmad-output/planning-artifacts/architecture.md#L584] — `picture_description_service.py` location confirmed
- [Source: src/nest/adapters/protocols.py#VisionLLMProviderProtocol] — Protocol already defined (story 7.1)
- [Source: src/nest/adapters/llm_provider.py#OpenAIVisionAdapter] — Vision adapter implementation for reference
- [Source: src/nest/adapters/docling_processor.py#convert] — Pass 1 method that produces the `ConversionResult` we consume
- [Source: src/nest/services/ai_enrichment_service.py] — Example service pattern (sequential, but shows structure + testing approach)
- [Source: tests/services/test_ai_enrichment_service.py] — Example test structure with Mock provider pattern

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- `MagicMock(spec=PictureItem)` fails: `PictureItem.meta` is a Pydantic field absent from `dir(PictureItem)` — using `item.__class__ = PictureItem` instead so `isinstance` passes without restricting attribute access.
- Story dev notes reference `PictureDescriptionData(text=..., created_by=...)` but the actual docling type is `DescriptionAnnotation` (alias) with `provenance` field, not `created_by`. The correct type for `element.meta.description` (`DescriptionMetaField | None`) is `DescriptionMetaField(text=..., created_by=...)` — used that instead.
- `PictureItem` is not re-exported from `docling_core.types.doc` per pyright; import corrected to `docling_core.types.doc.document`.
- `BasePrediction.confidence` is `Optional[float]`; guard added in `_classify` to avoid `None > float` comparison.

### Completion Notes List

- AC1–AC8 fully implemented and tested.
- `DescriptionMetaField` used (not `PictureDescriptionData`) for in-place description storage — matches `PictureMeta.description` field type.
- `PictureMeta` auto-created if `element.meta is None` before assigning description.
- 18 unit tests covering all ACs; 867 non-E2E tests passing.

### Senior Developer Review (AI)

**Reviewer:** Claude Sonnet 4.6 | **Date:** 2026-03-19

**Findings:**

| # | Severity | Description | File | Status |
|---|----------|-------------|------|--------|
| H1 | HIGH | No exception guard around `future.result()` — any unexpected exception in `_describe_one` (e.g., `get_image()` raises, `image.save()` raises) propagates through ThreadPoolExecutor and crashes the entire `describe()` call | `picture_description_service.py:121` | ✅ Fixed |
| H2 | HIGH | Ruff I001 import-sort error (un-sorted block) existed in service file when Task 4.1 was marked [x] | `picture_description_service.py:9` | ✅ Fixed |
| M1 | MEDIUM | `logger.warning("Vision LLM call failed…")` fired for AC7 (image extraction) failures where no LLM call was made — misleading for operators | `picture_description_service.py:127` | ✅ Fixed (message changed to `"Image description failed…"`) |
| L1 | LOW | `TestMixedDocument` doesn't assert `images_mermaid` due to non-deterministic thread ordering — mitigated by `TestRoutingMermaid` dedicated tests | `test_picture_description_service.py` | Accepted |
| L2 | LOW | AC4 spec references `PictureDescriptionData` but implementation uses `DescriptionMetaField` — documented in Dev Agent Record but AC4 text not updated | story file | Accepted |
| L3 | LOW | Image-None and LLM-None failures are indistinguishable by the caller (both return `None`) — makes per-cause telemetry impossible without refactoring | `picture_description_service.py` | Accepted |

**Fixes applied:**
- Added `try/except Exception` around `future.result()` in `describe()` — increments `images_failed` and calls `logger.exception` instead of propagating
- Fixed ruff I001 import-ordering error via `ruff check --fix`
- Changed warning message from `"Vision LLM call failed…"` to `"Image description failed…"` (covers both AC6 and AC7 accurately)
- Added `TestExceptionGuard` class with 2 tests covering the H1 fix (single-item raise, multi-item raise isolation)

**Post-review CI:** 20/20 tests, 0 ruff errors, 0 pyright errors, 869 non-E2E passed.

**Verdict:** ✅ APPROVED — all HIGH and MEDIUM issues resolved.

### File List

- `src/nest/core/models.py` — added `PictureDescriptionResult`
- `src/nest/services/picture_description_service.py` — new file
- `tests/services/test_picture_description_service.py` — new file

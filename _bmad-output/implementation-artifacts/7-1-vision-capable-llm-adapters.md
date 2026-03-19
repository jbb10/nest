# Story 7.1: Vision-Capable LLM Adapters

Status: done

## Story

As a **developer extending the LLM infrastructure**,
I want **existing LLM adapters to support multi-modal (image + text) messages**,
So that **images can be sent to vision-capable models for description**.

## Business Context

This is the **first story in Epic 7** (Image Description via Vision LLM). Epic 7 delivers FR34–FR38: automated image classification and description during `nest sync`, so that the `@nest` agent can understand and reference visual content — not just text.

Story 7.1 is the **foundational adapter layer** for the entire epic. Stories 7.2–7.5 depend on it. The work is entirely within the adapter boundary (`src/nest/adapters/`) and adds a new Protocol + two concrete implementations alongside the existing text LLM infrastructure established in Epic 6.

**Why a separate protocol?** Vision calls require image data (base64 bytes + MIME type) in the message payload, which is structurally different from text-only completions. A separate `VisionLLMProviderProtocol` keeps the text and vision interfaces cleanly decoupled, allows the vision adapter to be `None` independently of the text adapter, and follows the dependency-inversion pattern already used throughout the project.

## Acceptance Criteria

### AC1: `VisionLLMProviderProtocol` Protocol Defined

**Given** `src/nest/adapters/protocols.py`
**When** `VisionLLMProviderProtocol` is defined
**Then** it exposes exactly:
```python
def complete_with_image(
    self,
    prompt: str,
    image_base64: str,
    mime_type: str = "image/png",
) -> LLMCompletionResult | None: ...
```
**And** it is decorated with `@runtime_checkable`
**And** it is separate from the existing `LLMProviderProtocol`
**And** `isinstance(adapter, VisionLLMProviderProtocol)` returns `True` for both concrete adapters

### AC2: Vision Adapters with Multi-Modal Message Payloads

**Given** `OpenAIVisionAdapter` and `AzureOpenAIVisionAdapter`
**When** `complete_with_image(prompt, image_base64, mime_type)` is called
**Then** the message payload sent to the LLM API is exactly:
```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
        ],
    }
]
```
**And** the vision model name (not the text enrichment model) is used in the API call
**And** `prompt_tokens` and `completion_tokens` are tracked in `LLMCompletionResult`
**And** `None` is returned on any API failure (never raises)
**And** a warning is logged on failure

### AC3: Vision Provider Factory with `NEST_AI_VISION_MODEL` Fallback Chain

**Given** `create_vision_provider()` factory function in `llm_provider.py`
**When** invoked
**Then** it uses the same API key discovery logic as `create_llm_provider()`:
  - API key: `NEST_AI_API_KEY` → `OPENAI_API_KEY`
  - Endpoint: `NEST_AI_ENDPOINT` → `OPENAI_API_BASE` → `https://api.openai.com/v1`
**And** vision model fallback is: `NEST_AI_VISION_MODEL` → `OPENAI_VISION_MODEL` → default `"gpt-4.1"`
**And** if the resolved endpoint contains `.openai.azure.com`, an `AzureOpenAIVisionAdapter` is returned
**And** otherwise an `OpenAIVisionAdapter` is returned

### AC4: Graceful Degradation — No API Key

**Given** `NEST_AI_API_KEY` and `OPENAI_API_KEY` are both unset
**When** `create_vision_provider()` is called
**Then** `None` is returned
**And** no exception is raised

## Tasks / Subtasks

### Task 1: Add `VisionLLMProviderProtocol` to `protocols.py` (AC: 1)

- [x] 1.1: Add `VisionLLMProviderProtocol` class after `LLMProviderProtocol` at the bottom of `src/nest/adapters/protocols.py`
- [x] 1.2: Decorate with `@runtime_checkable`
- [x] 1.3: Define `complete_with_image(self, prompt: str, image_base64: str, mime_type: str = "image/png") -> LLMCompletionResult | None`
- [x] 1.4: Add docstring following project convention (see existing Protocol docstrings in this file)
- **File:** `src/nest/adapters/protocols.py`

### Task 2: Add `OpenAIVisionAdapter` to `llm_provider.py` (AC: 2)

- [x] 2.1: Add `DEFAULT_VISION_MODEL = "gpt-4.1"` constant after `DEFAULT_MODEL`
- [x] 2.2: Create `OpenAIVisionAdapter` class with `__init__(self, api_key: str, endpoint: str, model: str) -> None`
- [x] 2.3: Instantiate `openai.OpenAI(api_key=api_key, base_url=endpoint)` as `self._client`
- [x] 2.4: Store `model` as `self._model`
- [x] 2.5: Add `model_name` property returning `self._model`
- [x] 2.6: Implement `complete_with_image(self, prompt: str, image_base64: str, mime_type: str = "image/png") -> LLMCompletionResult | None`
  - Build the multi-modal message payload (exact structure per AC2)
  - Call `self._client.chat.completions.create(model=self._model, messages=messages)` with NO system message (vision calls are user-only)
  - Handle empty choices: log warning, return `None`
  - Handle `None` content: log warning, return `None`
  - Handle `None` usage: default tokens to `0`
  - Catch all exceptions: log warning "Vision LLM call failed: {e}", return `None`
- **File:** `src/nest/adapters/llm_provider.py`

### Task 3: Add `AzureOpenAIVisionAdapter` to `llm_provider.py` (AC: 2)

- [x] 3.1: Create `AzureOpenAIVisionAdapter` class with `__init__(self, api_key: str, endpoint: str, deployment: str, api_version: str) -> None`
- [x] 3.2: Instantiate `openai.AzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version=api_version)` as `self._client`
- [x] 3.3: Store `deployment` as `self._deployment`
- [x] 3.4: Add `model_name` property returning `self._deployment`
- [x] 3.5: Implement `complete_with_image()` identically to `OpenAIVisionAdapter` — same payload, same error handling, same token extraction
  - Use `self._deployment` as the model name in the API call
- **File:** `src/nest/adapters/llm_provider.py`

### Task 4: Add `create_vision_provider()` factory to `llm_provider.py` (AC: 3, 4)

- [x] 4.1: Define `create_vision_provider() -> OpenAIVisionAdapter | AzureOpenAIVisionAdapter | None`
- [x] 4.2: Reuse the same key/endpoint logic as `create_llm_provider()` (do NOT refactor the existing function — just repeat the same 3-line pattern; these will be united later if needed)
  - `api_key = os.environ.get("NEST_AI_API_KEY") or os.environ.get("OPENAI_API_KEY")`
  - Return `None` immediately if no API key
  - `endpoint = os.environ.get("NEST_AI_ENDPOINT") or os.environ.get("OPENAI_API_BASE") or DEFAULT_ENDPOINT`
- [x] 4.3: Vision model: `vision_model = os.environ.get("NEST_AI_VISION_MODEL") or os.environ.get("OPENAI_VISION_MODEL") or DEFAULT_VISION_MODEL`
- [x] 4.4: Route based on endpoint: `_is_azure_endpoint(endpoint)` → `AzureOpenAIVisionAdapter` / `OpenAIVisionAdapter`
- [x] 4.5: For Azure path: `AzureOpenAIVisionAdapter(api_key=api_key, endpoint=endpoint, deployment=vision_model, api_version=DEFAULT_AZURE_API_VERSION)`
- [x] 4.6: For OpenAI path: `OpenAIVisionAdapter(api_key=api_key, endpoint=endpoint, model=vision_model)`
- **File:** `src/nest/adapters/llm_provider.py`

### Task 5: Update module exports (AC: 1–4)

- [x] 5.1: Export `VisionLLMProviderProtocol` from `src/nest/adapters/protocols.py` (no `__all__` in use — just ensure the class exists at module top level)
- [x] 5.2: Export `OpenAIVisionAdapter`, `AzureOpenAIVisionAdapter`, `create_vision_provider`, `DEFAULT_VISION_MODEL` from `src/nest/adapters/llm_provider.py` (same pattern as existing names)
- **Files:** `src/nest/adapters/protocols.py`, `src/nest/adapters/llm_provider.py`

### Task 6: Write tests (AC: 1–4)

Add a new test class `TestVisionAdapters` and extend `TestCreateLLMProviderAzure` / `TestProtocolCompliance` in `tests/adapters/test_llm_provider.py`:

- [x] 6.1: **Protocol compliance** — `isinstance(OpenAIVisionAdapter(...), VisionLLMProviderProtocol)` is `True`
- [x] 6.2: **Protocol compliance** — `isinstance(AzureOpenAIVisionAdapter(...), VisionLLMProviderProtocol)` is `True`
- [x] 6.3: **`complete_with_image` success (OpenAI)** — mock client returns a valid response; verify `LLMCompletionResult` with correct `text`, `prompt_tokens`, `completion_tokens`
- [x] 6.4: **`complete_with_image` correct payload** — capture `messages` arg passed to `create()`; assert exact structure with `image_url` content block and correct `f"data:{mime_type};base64,{image_base64}"` URL
- [x] 6.5: **`complete_with_image` default mime_type** — call without `mime_type` kwarg; assert `image/png` appears in the URL
- [x] 6.6: **`complete_with_image` API exception** — mock raises `Exception`; assert `None` returned and "Vision LLM call failed" logged
- [x] 6.7: **`complete_with_image` empty choices** — assert `None` returned and warning logged
- [x] 6.8: **`complete_with_image` None content** — assert `None` returned and warning logged
- [x] 6.9: **`complete_with_image` None usage** — assert `LLMCompletionResult` returned with `prompt_tokens=0`, `completion_tokens=0`
- [x] 6.10: **`complete_with_image` Azure success** — same scenario for `AzureOpenAIVisionAdapter`
- [x] 6.11: **`create_vision_provider()` no API key** — all key env vars unset → returns `None`
- [x] 6.12: **`create_vision_provider()` NEST_AI_VISION_MODEL wins** — returns adapter with that model
- [x] 6.13: **`create_vision_provider()` OPENAI_VISION_MODEL fallback** — NEST var unset, OPENAI var set → uses OPENAI value
- [x] 6.14: **`create_vision_provider()` default model** — both vision vars unset → `model_name == "gpt-4.1"`
- [x] 6.15: **`create_vision_provider()` Azure routing** — Azure endpoint → returns `AzureOpenAIVisionAdapter`
- [x] 6.16: **`create_vision_provider()` uses same endpoint as text adapter** — `NEST_AI_ENDPOINT` influences vision adapter endpoint too
- **File:** `tests/adapters/test_llm_provider.py`

### Task 7: Run CI checks

- [x] 7.1: `ruff check src/ tests/ --fix` — zero lint errors
- [x] 7.2: `pyright` — zero type errors (strict mode enforced)
- [x] 7.3: `pytest tests/adapters/test_llm_provider.py -v` — all tests green
- [x] 7.4: `pytest -m "not e2e" -v` — full non-E2E suite green (regression check)

## Dev Notes

### Architecture Layer Compliance

This story is **adapter-layer only**. No changes to:
- `src/nest/services/` — untouched (services will use the new adapters in story 7.2–7.4)
- `src/nest/cli/` — untouched
- `src/nest/core/models.py` — untouched (no new models needed; `LLMCompletionResult` already handles both text and vision completions)

### File Locations

| Component | File |
|-----------|------|
| Protocol definition | `src/nest/adapters/protocols.py` |
| Concrete adapters + factory | `src/nest/adapters/llm_provider.py` |
| Tests | `tests/adapters/test_llm_provider.py` |

### Existing Code to Reuse (Do NOT Reinvent)

- `LLMCompletionResult` (from `nest.core.models`) — already has `text`, `prompt_tokens`, `completion_tokens`; no changes needed
- `_is_azure_endpoint(endpoint: str) -> bool` — already in `llm_provider.py`; reuse as-is
- `DEFAULT_AZURE_API_VERSION = "2024-12-01-preview"` — already in `llm_provider.py`; reuse as-is
- `DEFAULT_ENDPOINT = "https://api.openai.com/v1"` — already in `llm_provider.py`; reuse as-is
- `openai.OpenAI` and `openai.AzureOpenAI` — SDK already a dependency; no new packages needed

### Critical Message Payload Structure

The vision message payload has **no system message** — only a user-turn with mixed content:
```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
        ],
    }
]
```
This differs from `OpenAIAdapter.complete()` which passes a separate `system` role. Vision models on OpenAI/Azure accept the system prompt via the text block in the same user turn, or as part of the prompt string. Use the structure above exactly as specified.

### Model Name Isolation

Vision adapters use a **different model name** from the text enrichment adapter:
- Text: `NEST_AI_MODEL` → `OPENAI_MODEL` → `gpt-4o-mini`
- Vision: `NEST_AI_VISION_MODEL` → `OPENAI_VISION_MODEL` → `gpt-4.1`

The same API key and endpoint are shared. The factory function `create_vision_provider()` looks up the vision-model env var, not the text one.

### Pyright Strict Mode Requirements

All new code must pass `pyright` in strict mode. Key rules for this story:
- Use `from __future__ import annotations` at top of modified files (already present in `llm_provider.py`)
- All method signatures need full type annotations (no implicit `Any`)
- Default parameter in `complete_with_image` must be typed: `mime_type: str = "image/png"`
- Return types must be explicit: `-> LLMCompletionResult | None`
- `model_name` properties must have `-> str` annotation

### No Changes to Existing `LLMProviderProtocol`

Do NOT modify `LLMProviderProtocol`, `OpenAIAdapter`, `AzureOpenAIAdapter`, or `create_llm_provider()`. The vision infrastructure runs in parallel, not replacing any existing functionality.

### Project Structure Notes

- Protocol classes all live in `adapters/protocols.py` — `VisionLLMProviderProtocol` goes at the **bottom**, after `LLMProviderProtocol`
- All Protocol classes already use `@runtime_checkable` for `isinstance()` checks — match this pattern exactly
- The `llm_provider.py` module has no `__all__` — just add the new names at module level; they will be importable
- Import style: absolute imports only — e.g., `from nest.adapters.protocols import VisionLLMProviderProtocol`

### Testing Patterns (from existing `test_llm_provider.py`)

```python
# Patch the openai module at the point it is imported in llm_provider.py
with patch("nest.adapters.llm_provider.openai.OpenAI") as mock_openai:
    adapter = OpenAIVisionAdapter(api_key="test-key", endpoint="https://api.test.com/v1", model="gpt-4.1")

# For Azure:
with patch("nest.adapters.llm_provider.openai.AzureOpenAI") as mock_azure:
    adapter = AzureOpenAIVisionAdapter(...)

# Build mock API response (reuse _make_mock_response() helper already in the test file)
mock_response = _make_mock_response(content="A flowchart showing...", prompt_tokens=200, completion_tokens=50)
adapter._client.chat.completions.create = MagicMock(return_value=mock_response)
```

For env var tests — follow the existing monkeypatch pattern:
```python
def test_create_vision_provider_default_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEST_AI_API_KEY", "key")
    monkeypatch.delenv("NEST_AI_VISION_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)
    monkeypatch.delenv("NEST_AI_ENDPOINT", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)

    with patch("nest.adapters.llm_provider.openai.OpenAI"):
        result = create_vision_provider()

    assert result is not None
    assert result.model_name == "gpt-4.1"
```

### Cross-Story Context (What Comes Next)

Story 7.2 will modify `DoclingProcessor` to expose the `ConversionResult` and enable `do_picture_classification=True`. Story 7.3 will consume `create_vision_provider()` from the DI root and inject it into `PictureDescriptionService`. **This story should NOT touch those components** — just deliver clean, tested adapters.

### References

- Epic 7 spec: [Source: `_bmad-output/planning-artifacts/epics.md`#Story 7.1]
- Architecture — Protocol boundary: [Source: `_bmad-output/planning-artifacts/architecture.md`#Protocol Boundaries]
- Architecture — Vision model env vars: [Source: `_bmad-output/planning-artifacts/architecture.md`#Vision Model Configuration]
- Docling picture description guide: [Source: `docs/docling-picture-description-guide.md`] (read for Epic 7 background; not needed for this story's implementation)
- Existing text adapter pattern: [Source: `src/nest/adapters/llm_provider.py`]
- Existing protocol definitions: [Source: `src/nest/adapters/protocols.py`#LLMProviderProtocol]
- Existing adapter tests: [Source: `tests/adapters/test_llm_provider.py`]
- Previous story (6.8) dev notes: [Source: `_bmad-output/implementation-artifacts/6-8-unified-llm-glossary-pipeline.md`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6 (GitHub Copilot)

### Debug Log References

None — clean implementation, no debugging required.

### Completion Notes List

- AC1: `VisionLLMProviderProtocol` added to `protocols.py` after `LLMProviderProtocol`; `@runtime_checkable`; `complete_with_image` signature matches spec exactly.
- AC2: `OpenAIVisionAdapter` and `AzureOpenAIVisionAdapter` implement exact multi-modal payload structure (user-only turn, no system message). Both return `None` on any failure, log "Vision LLM call failed: {e}". Token extraction matches text adapters.
- AC3: `create_vision_provider()` uses identical key/endpoint discovery as `create_llm_provider()`. Vision model fallback: `NEST_AI_VISION_MODEL` → `OPENAI_VISION_MODEL` → `"gpt-4.1"`. Routes to Azure adapter for `.openai.azure.com` endpoints.
- AC4: No API key → `None` returned immediately, no exception.
- 16 new tests added across `TestVisionProtocolCompliance`, `TestVisionAdapters`, `TestCreateVisionProvider`. All pass.
- Full suite: 836 passed, 0 failures. Ruff: 0 errors. Pyright: 0 errors.
- `# type: ignore[arg-type]` applied to `messages` kwarg on `create()` calls — OpenAI SDK typing does not model mixed-content lists in its overloads, but runtime behaviour is correct per API spec.

### File List

- `src/nest/adapters/protocols.py` — added `VisionLLMProviderProtocol`
- `src/nest/adapters/llm_provider.py` — added `DEFAULT_VISION_MODEL`, `OpenAIVisionAdapter`, `AzureOpenAIVisionAdapter`, `create_vision_provider()`
- `tests/adapters/test_llm_provider.py` — updated imports; added `TestVisionProtocolCompliance`, `TestVisionAdapters`, `TestCreateVisionProvider`

## Senior Developer Review (AI)

**Reviewer:** Amelia (Dev Agent) | **Date:** 2026-03-19 | **Status:** APPROVED WITH FIXES

### Git vs Story Discrepancies
0 discrepancies in application source files. Planning files (`architecture.md`, `epics.md`, `prd.md`, `sprint-status.yaml`) modified externally — excluded per review rules.

### Findings & Fixes Applied

| # | Severity | Finding | Fix |
|---|----------|---------|-----|
| 1 | MEDIUM | `VisionLLMProviderProtocol` missing `model_name` property — `LLMProviderProtocol` has it; asymmetry breaks type-safe downstream usage in stories 7.3/7.4 | Added `model_name: str` property to `VisionLLMProviderProtocol` in `protocols.py` |
| 2 | MEDIUM | AC2 mandates BOTH adapters construct exact payload; only `OpenAIVisionAdapter` had a payload-structure test (6.4); `AzureOpenAIVisionAdapter` untested at that level | Added `test_complete_with_image_azure_correct_payload` (6.10.1) |
| 3 | LOW | No explicit unit test for `OpenAIVisionAdapter.model_name` property | Added `test_openai_vision_adapter_model_name` (6.9.1) |

### AC Validation
- AC1 `VisionLLMProviderProtocol`: ✅ `protocols.py:587` — `@runtime_checkable`, correct signature, `model_name` now added
- AC2 Vision adapters + payload: ✅ `llm_provider.py:248–317` / `340–402` — exact payload structure, correct model, tokens, None+warn on failure
- AC3 `create_vision_provider()` factory: ✅ `llm_provider.py:405–430` — full fallback chain, Azure routing
- AC4 Graceful degradation: ✅ early `return None` on missing key

### CI Final
- `pytest tests/adapters/test_llm_provider.py`: **48 passed**
- `pytest -m "not e2e"`: **836 passed**
- `ruff check`: **0 errors**
- `pyright`: **0 errors**

## Change Log

| Date | Change |
|------|--------|
| 2026-03-19 | Implemented Story 7.1: VisionLLMProviderProtocol, OpenAIVisionAdapter, AzureOpenAIVisionAdapter, create_vision_provider() factory; 16 new tests; all CI checks green |
| 2026-03-19 | Code review (AI): Fixed VisionLLMProviderProtocol missing model_name property (parity with LLMProviderProtocol); added Azure payload-structure test (6.10.1) and OpenAI model_name test (6.9.1); 48 tests green, ruff+pyright clean |

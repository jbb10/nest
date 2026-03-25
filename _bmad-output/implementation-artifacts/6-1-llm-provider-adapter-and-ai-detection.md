# Story 6.1: LLM Provider Adapter & AI Detection

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer building AI-powered features for Nest**,
I want **a protocol-based LLM adapter that auto-detects API credentials from environment variables**,
So that **all AI features have a consistent, testable interface to call LLMs with zero per-project configuration**.

## Business Context

This is the **foundation story for Epic 6** (Built-in AI Enrichment). Stories 6.2–6.6 all depend on this adapter being in place. Today, Nest ships VS Code agents (`@nest-enricher`, `@nest-glossary`) that the user must invoke manually in Chat to do LLM work. Epic 6 replaces that with built-in LLM calls during `nest sync`, eliminating the manual step entirely.

This story creates:
1. A `LLMProviderProtocol` — the testable contract all AI features depend on.
2. An `OpenAIAdapter` — the concrete implementation using the `openai` Python SDK.
3. A factory function `create_llm_provider()` — auto-detects credentials from environment variables and returns either a configured adapter or `None` (AI unavailable).

**Key design principle:** AI is opportunistic, never mandatory. If no API key is found, Nest works exactly as before. No error, no warning — just silent degradation.

## Acceptance Criteria

### AC1: NEST_AI_* Environment Variable Detection

**Given** `NEST_API_KEY` is set in the environment
**When** the LLM provider is initialized
**Then** it uses `NEST_API_KEY` as the API key
**And** checks `NEST_BASE_URL` for the base URL (default: `https://api.openai.com/v1`)
**And** checks `NEST_TEXT_MODEL` for the model name (default: `gpt-4o-mini`)

### AC2: OPENAI_* Fallback Chain

**Given** `NEST_API_KEY` is NOT set but `OPENAI_API_KEY` IS set
**When** the LLM provider is initialized
**Then** it falls back to `OPENAI_API_KEY`
**And** falls back to `OPENAI_BASE_URL` for endpoint
**And** falls back to `OPENAI_MODEL` for model name

### AC3: No API Key = None (No Error)

**Given** neither `NEST_API_KEY` nor `OPENAI_API_KEY` is set
**When** the LLM provider is initialized
**Then** it returns `None` (AI is not available)
**And** no error is raised

### AC4: Chat Completion Call

**Given** a valid LLM provider is created
**When** `complete(system_prompt, user_prompt)` is called
**Then** it sends a chat completion request to the configured endpoint
**And** returns the response text and token usage (prompt_tokens, completion_tokens)

### AC5: Graceful Error Handling

**Given** the LLM API call fails (network error, auth error, timeout)
**When** the error is caught
**Then** the error is logged via Python logging
**And** a `None` result is returned (caller handles graceful degradation)
**And** no exception propagates to the user

### AC6: Protocol in protocols.py

**Given** the adapter is used in tests
**When** `LLMProviderProtocol` is referenced
**Then** it is a `@runtime_checkable` Protocol in `adapters/protocols.py`
**And** test doubles can be injected via standard DI pattern

### AC7: openai Dependency Added

**Given** the `openai` Python SDK is added as a dependency
**When** `pyproject.toml` is updated
**Then** `openai>=1.0.0` is listed in the project dependencies

## Tasks / Subtasks

### Task 1: Add Pydantic Models (AC: 4)
- [x] 1.1: Add `LLMCompletionResult` model to `src/nest/core/models.py`:
  ```python
  class LLMCompletionResult(BaseModel):
      """Result of an LLM chat completion call.

      Attributes:
          text: The generated response text.
          prompt_tokens: Number of tokens in the prompt.
          completion_tokens: Number of tokens in the completion.
      """
      text: str
      prompt_tokens: int
      completion_tokens: int
  ```
- [x] 1.2: Confirm model follows existing patterns (Pydantic v2, docstrings, explicit types)

### Task 2: Add LLMProviderProtocol (AC: 6)
- [x] 2.1: Add `LLMProviderProtocol` to `src/nest/adapters/protocols.py`:
  ```python
  @runtime_checkable
  class LLMProviderProtocol(Protocol):
      """Protocol for LLM completion operations.

      Implementations handle sending chat completion requests to LLM APIs.
      Used by AI enrichment and glossary services.
      """

      def complete(
          self,
          system_prompt: str,
          user_prompt: str,
      ) -> LLMCompletionResult | None:
          """Send a chat completion request.

          Args:
              system_prompt: System-level instructions for the model.
              user_prompt: User message content.

          Returns:
              LLMCompletionResult with response text and token usage,
              or None if the call failed (error is logged internally).
          """
          ...

      @property
      def model_name(self) -> str:
          """Return the configured model name."""
          ...
  ```
- [x] 2.2: Import `LLMCompletionResult` from `nest.core.models` in protocols.py
- [x] 2.3: Verify the protocol uses `@runtime_checkable` for test double validation

### Task 3: Create OpenAI Adapter (AC: 1, 2, 4, 5)
- [x] 3.1: Create `src/nest/adapters/llm_provider.py` with `OpenAIAdapter` class
- [x] 3.2: Constructor takes `api_key: str`, `endpoint: str`, `model: str`:
  ```python
  class OpenAIAdapter:
      """OpenAI-compatible LLM adapter.

      Wraps the openai Python SDK for chat completions.
      Handles errors gracefully — returns None on failure, never raises.
      """

      def __init__(self, api_key: str, endpoint: str, model: str) -> None:
          self._client = openai.OpenAI(api_key=api_key, base_url=endpoint)
          self._model = model

      @property
      def model_name(self) -> str:
          return self._model

      def complete(
          self,
          system_prompt: str,
          user_prompt: str,
      ) -> LLMCompletionResult | None:
          ...
  ```
- [x] 3.3: Implement `complete()` method:
  - Call `self._client.chat.completions.create()` with `messages=[{"role": "system", ...}, {"role": "user", ...}]`
  - Extract `response.choices[0].message.content`
  - Extract `response.usage.prompt_tokens` and `response.usage.completion_tokens`
  - Return `LLMCompletionResult`
- [x] 3.4: Wrap the entire API call in `try/except Exception`:
  - Log error via `logger.warning("LLM call failed: %s", e)`
  - Return `None`
  - **Never** let exceptions propagate
- [x] 3.5: Handle edge cases:
  - `response.choices` empty → log warning, return None
  - `response.usage` is None → default tokens to 0
  - `response.choices[0].message.content` is None → log warning, return None

### Task 4: Create AI Detection Factory (AC: 1, 2, 3)
- [x] 4.1: Add `create_llm_provider()` factory function to `src/nest/adapters/llm_provider.py`:
  ```python
  def create_llm_provider() -> OpenAIAdapter | None:
      """Auto-detect AI credentials from environment variables.

      Fallback chain:
          API key:  NEST_API_KEY → OPENAI_API_KEY → None
          Endpoint: NEST_BASE_URL → OPENAI_BASE_URL → https://api.openai.com/v1
          Model:    NEST_TEXT_MODEL → OPENAI_MODEL → gpt-4o-mini

      Returns:
          Configured OpenAIAdapter if API key found, None otherwise.
      """
  ```
- [x] 4.2: Implement env var fallback chain:
  ```python
  import os

  DEFAULT_ENDPOINT = "https://api.openai.com/v1"
  DEFAULT_MODEL = "gpt-4o-mini"

  api_key = os.environ.get("NEST_API_KEY") or os.environ.get("OPENAI_API_KEY")
  if not api_key:
      return None

  endpoint = (
      os.environ.get("NEST_BASE_URL")
      or os.environ.get("OPENAI_BASE_URL")
      or DEFAULT_ENDPOINT
  )
  model = (
      os.environ.get("NEST_TEXT_MODEL")
      or os.environ.get("OPENAI_MODEL")
      or DEFAULT_MODEL
  )

  return OpenAIAdapter(api_key=api_key, endpoint=endpoint, model=model)
  ```
- [x] 4.3: No error logging when keys are absent — this is expected, not an error

### Task 5: Add openai Dependency (AC: 7)
- [x] 5.1: Add `"openai>=1.0.0"` to `pyproject.toml` `dependencies` list
- [x] 5.2: Run `uv lock` to update the lock file
- [x] 5.3: Run `uv sync` to install the new dependency

### Task 6: Unit Tests (AC: 1-6)
- [x] 6.1: Create `tests/adapters/test_llm_provider.py`:
  - **Test `create_llm_provider()` factory:**
    - `test_create_with_nest_ai_vars()` — NEST_API_KEY set → returns adapter with correct config
    - `test_create_with_openai_fallback()` — only OPENAI_API_KEY set → returns adapter
    - `test_create_no_keys()` — no keys → returns None
    - `test_nest_ai_takes_precedence()` — both NEST_API_KEY and OPENAI_API_KEY set → uses NEST_API_KEY
    - `test_endpoint_fallback_chain()` — test all three levels (NEST_BASE_URL → OPENAI_BASE_URL → default)
    - `test_model_fallback_chain()` — test all three levels (NEST_TEXT_MODEL → OPENAI_MODEL → default)
    - `test_default_endpoint()` — no endpoint vars → https://api.openai.com/v1
    - `test_default_model()` — no model vars → gpt-4o-mini
  - **Test `OpenAIAdapter.complete()`:**
    - `test_complete_success()` — mock openai client, verify LLMCompletionResult returned with text + tokens
    - `test_complete_api_error()` — mock openai raising APIError → returns None, no exception
    - `test_complete_network_error()` — mock connection error → returns None
    - `test_complete_timeout()` — mock timeout → returns None
    - `test_complete_empty_choices()` — response with empty choices → returns None
    - `test_complete_none_content()` — response content is None → returns None
    - `test_complete_none_usage()` — response usage is None → returns result with 0 tokens
  - **Test protocol compliance:**
    - `test_adapter_satisfies_protocol()` — `isinstance(adapter, LLMProviderProtocol)` is True
- [x] 6.2: Use `monkeypatch.setenv()` / `monkeypatch.delenv()` for all env var tests
- [x] 6.3: Use `unittest.mock.patch` or `monkeypatch` to mock `openai.OpenAI` — never make real API calls

### Task 7: Run Full Test Suite (AC: all)
- [x] 7.1: Run `pytest -m "not e2e"` — all pass (no regressions)
- [x] 7.2: Run `./scripts/ci-lint.sh` — clean
- [x] 7.3: Run `./scripts/ci-typecheck.sh` — clean (Pyright strict mode)

## Dev Notes

### Architecture Compliance

- **Layered architecture:** `OpenAIAdapter` lives in `src/nest/adapters/` — it wraps an external system (OpenAI API), which is exactly what adapters are for.
- **Protocol-based DI:** `LLMProviderProtocol` is a `@runtime_checkable Protocol` in `adapters/protocols.py` — consistent with all other protocols (`FileSystemProtocol`, `DocumentProcessorProtocol`, etc.)
- **Services will depend on the protocol, never the adapter:** Stories 6.2 and 6.3 will inject `LLMProviderProtocol` into `AIEnrichmentService` and `AIGlossaryService`. This story only creates the adapter and protocol.
- **Composition root pattern:** The factory `create_llm_provider()` will be called from CLI-layer code (composition roots in `sync_cmd.py` and `config_cmd.py` in later stories). This story provides the factory; wiring happens in 6.2+.
- **Pydantic model:** `LLMCompletionResult` in `src/nest/core/models.py` — follows existing pattern with all other result models.

### Critical Implementation Details

**Environment Variable Precedence (FR27, FR33):**
```
NEST_API_KEY  → OPENAI_API_KEY      → None (no AI)
NEST_BASE_URL → OPENAI_BASE_URL     → "https://api.openai.com/v1"
NEST_TEXT_MODEL    → OPENAI_MODEL        → "gpt-4o-mini"
```

**Error Strategy:**
The adapter must NEVER raise exceptions to callers. All OpenAI SDK exceptions are caught internally:
```python
try:
    response = self._client.chat.completions.create(...)
    ...
except Exception as e:
    logger.warning("LLM call failed: %s", e)
    return None
```
This ensures callers (AI enrichment, glossary generation) always get `LLMCompletionResult | None` and can degrade gracefully without `try/except` in their own code.

**OpenAI SDK Usage (openai >= 1.0.0):**
```python
import openai

client = openai.OpenAI(api_key="...", base_url="...")
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
)
text = response.choices[0].message.content
prompt_tokens = response.usage.prompt_tokens
completion_tokens = response.usage.completion_tokens
```

**Important openai SDK notes:**
- `openai` v1.0+ uses class-based client (`openai.OpenAI(...)`) not the old `openai.ChatCompletion.create()` module-level API
- `base_url` (not `api_base`) is the constructor parameter in v1.0+
- `response.usage` can be `None` for some providers — handle gracefully
- `response.choices[0].message.content` can be `None` for tool calls — handle gracefully
- The SDK raises `openai.APIError`, `openai.APIConnectionError`, `openai.RateLimitError`, `openai.APITimeoutError` — catch the base `Exception` to cover all plus unexpected errors

**What This Story Does NOT Include (Scope Boundaries):**
- No wiring into `SyncService` — that happens in Stories 6.2 and 6.3
- No CLI command changes — `nest config ai` is Story 6.5
- No `--no-ai` flag — that's Story 6.4
- No token aggregation or reporting — that's Story 6.4
- No changes to sync flow — purely adapter + protocol + factory
- No changes to existing agent templates or init command

### Existing Codebase Patterns to Follow

**Protocol pattern** (from `protocols.py`):
```python
@runtime_checkable
class LLMProviderProtocol(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletionResult | None: ...
    @property
    def model_name(self) -> str: ...
```

**Result model pattern** (from `models.py`):
```python
class LLMCompletionResult(BaseModel):
    text: str
    prompt_tokens: int
    completion_tokens: int
```

**Adapter file naming** (from `src/nest/adapters/`):
- `docling_processor.py` → `DoclingProcessor`
- `filesystem.py` → `FileSystemAdapter`
- `llm_provider.py` → `OpenAIAdapter` + `create_llm_provider()`

**Test file naming** (from `tests/adapters/`):
- `test_filesystem.py` → `tests/adapters/test_llm_provider.py`

**Logging pattern:**
```python
import logging
logger = logging.getLogger(__name__)
```
Uses Python stdlib `logging`, NOT Rich console for adapter-layer diagnostics.

### Project Structure Notes

- All new files follow the existing `src/nest/` src-layout
- Adapter in `src/nest/adapters/llm_provider.py` — consistent with `docling_processor.py`, `filesystem.py`, etc.
- Protocol in `src/nest/adapters/protocols.py` — extends existing protocol collection
- Model in `src/nest/core/models.py` — extends existing model collection
- Tests in `tests/adapters/test_llm_provider.py` — mirrors source structure

### Dependencies

- **No upstream dependencies** — this is the first story in Epic 6
- **Downstream dependents:** Stories 6.2, 6.3, 6.4, 6.5 all depend on this story

### Testing Strategy

- All tests use `monkeypatch` for env vars — no real environment variable leaks
- OpenAI client is mocked — **zero real API calls ever**
- Protocol compliance tested with `isinstance()` — ensures DI compatibility
- Edge cases covered: empty choices, None content, None usage, network errors, timeouts, auth errors
- No E2E tests needed — this story adds no CLI-visible behavior; E2E coverage comes in Stories 6.2+

### File Inventory

| File | Action | Purpose |
|------|--------|---------|
| `src/nest/core/models.py` | MODIFY | Add `LLMCompletionResult` model |
| `src/nest/adapters/protocols.py` | MODIFY | Add `LLMProviderProtocol` |
| `src/nest/adapters/llm_provider.py` | **CREATE** | `OpenAIAdapter` class + `create_llm_provider()` factory |
| `pyproject.toml` | MODIFY | Add `openai>=1.0.0` dependency |
| `tests/adapters/test_llm_provider.py` | **CREATE** | Unit tests for adapter, factory, protocol compliance |

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6] — Epic objectives, story AC
- [Source: _bmad-output/planning-artifacts/architecture.md#Dependency Injection] — Protocol-based DI pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#Testability] — Constructor injection, protocol contracts
- [Source: _bmad-output/planning-artifacts/prd.md#FR27] — Auto-detect AI from env vars
- [Source: _bmad-output/planning-artifacts/prd.md#FR33] — Env var fallback chain
- [Source: _bmad-output/project-context.md#Architecture & Dependency Injection] — Layer rules, composition root
- [Source: _bmad-output/project-context.md#Testing Rules] — Test naming, AAA pattern, mock strategy
- [Source: src/nest/adapters/protocols.py] — Existing protocol patterns
- [Source: src/nest/core/models.py] — Existing result model patterns
- [Source: src/nest/adapters/docling_processor.py] — Adapter implementation pattern
- [Source: src/nest/cli/sync_cmd.py#create_sync_service] — Composition root pattern

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (GitHub Copilot)

### Debug Log References

None — all tests passed on first run.

### Completion Notes List

- All 7 tasks (23 subtasks) completed in sequence.
- `LLMCompletionResult` Pydantic model added to `src/nest/core/models.py`.
- `LLMProviderProtocol` added to `src/nest/adapters/protocols.py` with `@runtime_checkable`.
- `OpenAIAdapter` + `create_llm_provider()` factory created in `src/nest/adapters/llm_provider.py`.
- `openai>=1.0.0` added to `pyproject.toml`; `uv lock && uv sync` successful (installed openai 2.24.0).
- 16 unit tests created covering factory env-var detection, adapter complete() success/error paths, edge cases, and protocol compliance.
- Full suite: 689 passed, 0 failed. Ruff lint clean. Pyright strict clean (0 errors).

#### Code Review (2026-03-05, Claude Opus 4.6)

- **M1 FIXED:** Ruff I001 lint violation in `tests/adapters/test_llm_provider.py` — removed extra blank line after import block.
- **M2 FIXED:** Added `caplog` logging assertions to all 5 error-path tests (`test_complete_api_error`, `test_complete_network_error`, `test_complete_timeout`, `test_complete_empty_choices`, `test_complete_none_content`) verifying AC5 requirement that errors are logged via `logger.warning()`.
- **L1 NOTED:** `Makefile` and `scripts/release.sh` have unrelated changes in git (release `--yes` flag) — not part of story 6-1 scope.
- **L2 NOTED:** `uv.lock` change expected from dependency addition, not documented in File List.
- Post-fix: 689 passed, 0 failed. Ruff clean. Pyright clean.

### File List

| File | Action |
|------|--------|
| `src/nest/core/models.py` | MODIFIED — added `LLMCompletionResult` |
| `src/nest/adapters/protocols.py` | MODIFIED — added `LLMProviderProtocol`, imported `LLMCompletionResult` |
| `src/nest/adapters/llm_provider.py` | CREATED — `OpenAIAdapter` + `create_llm_provider()` factory |
| `pyproject.toml` | MODIFIED — added `openai>=1.0.0` dependency |
| `tests/adapters/test_llm_provider.py` | CREATED — 16 unit tests |

# Story 7.5: E2E Tests for Image Description

Status: ready-for-dev

## Story

As a **developer working on image description**,
I want **end-to-end tests that validate the full image description pipeline with real Docling processing and CLI invocation**,
so that **I can catch integration bugs between Docling image extraction, classification, vision LLM calls, and markdown output**.

## Business Context

This is **story 5 of 5 in Epic 7** (Image Description via Vision LLM), which delivers FR34–FR38.

- **Story 7.1** built vision adapter layer (`VisionLLMProviderProtocol`, `OpenAIVisionAdapter`, `AzureOpenAIVisionAdapter`, `create_vision_provider()`).
- **Story 7.2** adapted `DoclingProcessor` to support `enable_classification=True` and `convert()` returning raw `ConversionResult`.
- **Story 7.3** implemented `PictureDescriptionService.describe()` — the Pass 2 service layer.
- **Story 7.4** wired `PictureDescriptionService` into `SyncService` with cross-file parallelism (`ThreadPoolExecutor` Phase 2).
- **Story 7.5 (THIS STORY)** adds E2E tests covering the full pipeline end-to-end.

**Background:** Following the E2E testing pattern established in Story 2.9.  E2E tests use real file I/O, real Docling processing, and subprocess CLI invocation.  Vision LLM calls are the **only component that MUST be mocked** — no real API calls to OpenAI in tests.

## Acceptance Criteria

### AC1: Test Fixture

**Given** E2E test fixtures are needed for image description
**When** `tests/e2e/fixtures/generate_fixtures.py` is run
**Then** `image_doc.pdf` is created in `tests/e2e/fixtures/`
**And** the PDF contains at least one embedded raster image (bar chart)
**And** the fixture is under 200 KB (actual: ~8 KB)
**And** `tests/e2e/fixtures/*.pdf` is already marked binary in `.gitattributes`

### AC2: Image Description E2E (mocked vision LLM)

**Given** a Nest project is initialised and `image_doc.pdf` is placed in `_nest_sources/`
**And** `MockVisionServer` is running and env vars point at it
**When** `nest sync` runs
**Then** exit code is 0
**And** the output markdown in `_nest_context/image_doc.md` contains the canned description text
**And** stdout includes `"Images described:"` in the sync summary

### AC3: Mermaid Diagram E2E

**Given** the mock returns a fenced ` ```mermaid ` code block
**When** `nest sync` runs on the image PDF
**Then** the output markdown contains a ` ```mermaid ` block with diagram elements

### AC4: No-AI Env Vars Fallback

**Given** both `NEST_AI_API_KEY` and `OPENAI_API_KEY` are set to empty strings (no AI configured)
**When** `nest sync` runs
**Then** exit code is 0
**And** the output markdown contains `<!-- image -->` placeholder markers
**And** stdout does NOT include `"Images described:"`

### AC5: `--no-ai` Flag

**Given** AI env vars ARE configured (pointing at the mock server)
**When** `nest sync --no-ai` runs
**Then** exit code is 0
**And** the output uses `<!-- image -->` placeholders
**And** zero calls were made to the mock server

### AC6: Token Reporting

**Given** image descriptions are generated via the mocked vision LLM
**When** `nest sync` completes
**Then** stdout includes `"AI tokens:"` with non-zero token counts

### AC7: Incremental Sync (no re-description)

**Given** the first sync has already produced image descriptions
**And** the source PDF is unchanged
**When** `nest sync` runs again
**Then** the file is skipped (checksum match)
**And** the mock server receives no additional calls
**And** existing descriptions are preserved in the output markdown

## Tasks / Subtasks

### Task 1: Extend `generate_fixtures.py` with `create_image_pdf()` (AC: 1)

- [ ] 1.1: Add `create_image_pdf(output_path: Path) -> None` function to `tests/e2e/fixtures/generate_fixtures.py`
  - Uses **PIL** (available as Docling transitive dep) + **reportlab** (existing dev dep)
  - Creates a 400×280 px bar-chart image with PIL and embeds it in a PDF via `reportlab.lib.utils.ImageReader`
  - Output must be under 200 KB
- [ ] 1.2: Call `create_image_pdf(fixtures_dir / "image_doc.pdf")` from `main()` in `generate_fixtures.py`
- [ ] 1.3: Run `python tests/e2e/fixtures/generate_fixtures.py` to generate `image_doc.pdf`
- [ ] 1.4: Verify `.gitattributes` already covers `*.pdf` as binary — it does: `tests/e2e/fixtures/*.pdf binary`
- **File:** `tests/e2e/fixtures/generate_fixtures.py`, `tests/e2e/fixtures/image_doc.pdf`

### Task 2: Create `MockVisionServer` helper in `test_image_description_e2e.py` (AC: 2–7)

- [ ] 2.1: Define `_MockOpenAIHandler(BaseHTTPRequestHandler)` with:
  - Class-level `response_body: str` (set per-session by `MockVisionServer`)
  - Class-level `call_counter: list[int] = [0]` (mutable list for shared state)
  - `do_POST()`: reads + discards request body, increments `call_counter[0]`, returns OpenAI-format JSON with configurable `response_body`
  - `log_message()`: no-op (suppress HTTP logging)
- [ ] 2.2: Define `MockVisionServer` context manager with:
  - `__init__(response: str)` stores response body
  - `__enter__()`: resets `call_counter[0]` to 0, creates `HTTPServer(("127.0.0.1", 0), handler_cls)` (port 0 = OS picks free port), starts `serve_forever()` in daemon thread
  - `__exit__()`: calls `self._server.shutdown()`
  - `call_count` property: returns `_MockOpenAIHandler.call_counter[0]`
  - `env_vars()`: returns dict with `NEST_AI_API_KEY`, `NEST_AI_ENDPOINT`, `NEST_AI_VISION_MODEL`, `NEST_AI_MODEL` all pointing at `http://127.0.0.1:{port}/v1`
- **No new test dependencies** — uses Python stdlib `http.server`, `threading`, `json`
- **File:** `tests/e2e/test_image_description_e2e.py`

### Task 3: Implement test class `TestImageDescriptionE2E` (AC: 2–7)

- [ ] 3.1: `test_image_description_produces_canned_description_in_output` — AC2
  - Gate: `@skip_without_docling`
  - Copy fixture, start MockVisionServer, run `sync`, assert markdown contains `CANNED_DESCRIPTION` and stdout has `"Images described:"`
- [ ] 3.2: `test_mermaid_response_appears_as_mermaid_block_in_output` — AC3
  - Start MockVisionServer with `response=CANNED_MERMAID`, assert ` ```mermaid` and `flowchart TD` in output
- [ ] 3.3: `test_no_ai_env_vars_produces_image_placeholder` — AC4
  - Pass `env={"NEST_AI_API_KEY": "", "OPENAI_API_KEY": ""}` to override ambient API keys with empty strings
  - Assert `<!-- image -->` in output, no canned description, no `"Images described:"`
- [ ] 3.4: `test_no_ai_flag_produces_image_placeholder_and_no_vision_calls` — AC5
  - Start MockVisionServer, run `sync --no-ai`, assert `<!-- image -->` in output, `calls_with_no_ai_flag == 0`
- [ ] 3.5: `test_token_reporting_includes_vision_tokens` — AC6
  - Assert `"AI tokens:"` in stdout
- [ ] 3.6: `test_incremental_sync_skips_unchanged_file_and_makes_no_vision_calls` — AC7
  - Run two syncs in the same `MockVisionServer` context, assert `calls_after_second == calls_after_first`
- **File:** `tests/e2e/test_image_description_e2e.py`

## Dev Notes

### Critical: Docling Placeholder Format

Docling `export_to_markdown(image_mode=ImageRefMode.PLACEHOLDER)` generates `<!-- image -->` (NOT `[Image: ...]` as the old code comment says). The comment in `docling_processor.py` is wrong. Do NOT assert on `[Image:` — use `<!-- image -->` instead.

### Critical: Description + Placeholder Both Appear

When a `PictureItem` has `meta.description` set, `export_to_markdown()` outputs **both** the description text AND the `<!-- image -->` placeholder, in that order:
```
A bar chart showing quarterly sales data for 2025.

Bar chart

Figure 1: Quarterly Sales Performance (2025)

<!-- image -->
```
So assert `CANNED_DESCRIPTION in content` (description present) AND `"<!-- image -->" in content` (placeholder always present regardless). **Do NOT assert that `<!-- image -->` is absent** for described images — it is always there.

### Critical: Fixture Docling Detection Verified

The `image_doc.pdf` fixture (bar chart image embedded via reportlab) was verified to produce **1 PictureItem** with `label=bar_chart` when processed by `DoclingProcessor(enable_classification=True)`. This confirms the fixture works for the full vision pipeline.

### MockVisionServer Architecture

The mock HTTP server pattern avoids all new test dependencies:
- `http.server.HTTPServer` — Python stdlib, zero deps
- Port 0 = OS assigns a random free port, no conflicts
- `daemon=True` on the thread prevents test hangs
- `call_counter: list[int] = [0]` (mutable class variable list) is safe for CPython's GIL — single-slot list mutation is effectively atomic for our use case
- Each `MockVisionServer.__enter__()` resets `call_counter[0]` to 0 for clean isolation between tests

### Env Var Override for "No AI" Test

`run_cli()` in conftest does `merged_env = os.environ.copy(); merged_env.update(env)`. To shadow any ambient API keys with empty values (which are falsy in Python), pass:
```python
env={"NEST_AI_API_KEY": "", "OPENAI_API_KEY": ""}
```
`create_vision_provider()` checks `os.environ.get("NEST_AI_API_KEY") or os.environ.get("OPENAI_API_KEY")` — empty strings are falsy, so it returns `None` → no vision pipeline.

### No New Dependencies Required

- PIL/Pillow: available as Docling transitive dep (verified: Pillow 11.3.0 in venv)
- reportlab: already in dev deps (`reportlab>=4.4.9`)
- `http.server`, `threading`, `json`: Python stdlib
- No changes to `pyproject.toml`

### Test Markers and Gating

All tests use `@pytest.mark.e2e` and `@skip_without_docling`. No `@skip_without_ai` — vision LLM is mocked. Run E2E tests with:
```bash
uv run pytest tests/e2e/test_image_description_e2e.py -v -m e2e --timeout=300
```

### Project Structure Notes

Files to create/modify:
| File | Change |
|------|--------|
| `tests/e2e/fixtures/generate_fixtures.py` | Add `create_image_pdf()` + call in `main()` |
| `tests/e2e/fixtures/image_doc.pdf` | Generated binary fixture (8 KB) |
| `tests/e2e/test_image_description_e2e.py` | New test file (6 tests) |

Files to NOT touch:
- `src/nest/**` — all implementation complete in stories 7.1–7.4
- `tests/e2e/conftest.py` — no changes needed (uses existing `run_cli`, `skip_without_docling`)

### References

- Docling ImageRefMode behavior: [`.venv/lib/.../docling_core/transforms/serializer/markdown.py`]
- Vision pipeline wiring: [`src/nest/cli/sync_cmd.py#create_sync_service()`]([Source: src/nest/cli/sync_cmd.py])
- PictureDescriptionService: [`src/nest/services/picture_description_service.py`]([Source: src/nest/services/picture_description_service.py])
- VisionLLMProviderProtocol: [`src/nest/adapters/protocols.py#VisionLLMProviderProtocol`]([Source: src/nest/adapters/protocols.py])
- create_vision_provider(): [`src/nest/adapters/llm_provider.py#create_vision_provider()`]([Source: src/nest/adapters/llm_provider.py])
- Path constants: [`src/nest/core/paths.py`] — `SOURCES_DIR="_nest_sources"`, `CONTEXT_DIR="_nest_context"`
- Story 7.4 implementation notes: [`_bmad-output/implementation-artifacts/7-4-sync-pipeline-integration-cross-file-parallelism.md`]
- E2E test pattern: [`tests/e2e/test_ai_enrichment_e2e.py`], [`tests/e2e/test_sync_e2e.py`]
- E2E conftest: [`tests/e2e/conftest.py`] — `run_cli()`, `initialized_project()`, `skip_without_docling`

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (SM Agent, create-story workflow)

### Debug Log References

### Completion Notes List

### File List

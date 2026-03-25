# Story 8.2: Suppress Third-Party Log Noise

Status: done

## Story

As a **Nest user running `nest sync`**,
I want **the terminal output to show only the progress bar and summary**,
so that **I can see what matters without wading through hundreds of lines of Docling internals, HTTP traces, and framework chatter**.

## Business Context

When `nest sync` processes PDFs with AI-enabled image description, the terminal is flooded with ~200+ lines of noise from three sources:

1. **Docling's internal Python logging** (pipeline init, plugin loading, accelerator detection, OCR engine registration) — repeated per-document, pure internals.
2. **httpx/openai HTTP request traces** (`HTTP Request: POST ... "HTTP/1.1 200 OK"`) — one per vision LLM call, ~70 lines for a 3-file sync with images.
3. **Nest's own internal INFO logs** (`Starting sync process...`, `Processing N files...`, `Committing entries to manifest`) — redundant with the progress bar and summary.

The root cause: Docling internally calls `logging.basicConfig(level=INFO)` when instantiated, which configures the root logger with a stderr handler. This pulls in every `logger.info()` call from every library in the process.

Nest already has a clean Rich progress bar and a summary block — the log noise obscures them.

This is a **leaf fix** — no processing behaviour changes, only console output hygiene.

---

## Acceptance Criteria

### AC1: Third-party loggers suppressed at startup

**Given** any `nest` CLI command is invoked
**When** the `main()` entry point runs
**Then** the root logger is configured at WARNING level (via `logging.basicConfig(level=WARNING, force=True)`)
**And** loggers for `docling`, `httpx`, `openai`, `PIL`, and `urllib3` are explicitly set to WARNING
**And** no INFO-level messages from these libraries reach the console

### AC2: `nest sync` shows only progress bar and summary

**Given** `nest sync --force` is run on a project with 3 PDFs containing images
**When** the pipeline completes (Docling conversion, vision LLM calls, index generation)
**Then** the terminal output contains:
- The Rich progress bar with file names
- The `✓ Sync complete` summary block
- No `INFO - Loading plugin`, `INFO - HTTP Request:`, `INFO - Accelerator device:`, or similar lines

### AC3: `--verbose` / `-v` flag restores detailed logging

**Given** `nest sync --force --verbose` is run
**When** the sync executes
**Then** INFO-level logging from `docling`, `httpx`, `openai`, and `nest` namespaces is restored to the console
**And** the user sees the same detailed output as before this story

### AC4: Warning and error logs still surface

**Given** a vision LLM call returns a 404 error
**When** the pipeline logs `WARNING - Vision LLM call failed: ...`
**Then** the warning is still printed to the console (not suppressed)
**And** only INFO-level noise is removed

### AC5: Error log file unaffected

**Given** the `setup_error_logger()` in `ui/logger.py`
**When** a processing error occurs during sync
**Then** errors are still written to `.nest/errors.log` as before
**And** the error logger's dedicated file handler is not affected by the root logger suppression

## Implementation

### Files Changed

| File | Change |
|---|---|
| `src/nest/cli/main.py` | Added `import logging` and `_suppress_third_party_loggers()` function called from `main()` before `app()` |
| `src/nest/cli/sync_cmd.py` | Added `--verbose` / `-v` flag that restores INFO level for `docling`, `httpx`, `openai`, `nest` loggers |

### `_suppress_third_party_loggers()` (in `main.py`)

```python
def _suppress_third_party_loggers() -> None:
    logging.basicConfig(level=logging.WARNING, force=True)
    for name in ("docling", "httpx", "openai", "PIL", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
```

Called once in `main()` before `app()` runs, so it applies to all commands (sync, init, doctor, etc.).

### `--verbose` flag (in `sync_cmd.py`)

```python
verbose: Annotated[
    bool,
    typer.Option(
        "--verbose", "-v",
        help="Show detailed processing logs (Docling, HTTP, etc.)",
    ),
] = False,
```

When set, restores INFO level on root + named loggers so the user can troubleshoot.

## Tasks / Subtasks

- [x] **Task 1: Add global logger suppression** (AC1, AC2, AC4, AC5)
  - [x] 1.1: Add `import logging` to `src/nest/cli/main.py`
  - [x] 1.2: Implement `_suppress_third_party_loggers()` — sets root to WARNING, silences `docling`, `httpx`, `openai`, `PIL`, `urllib3`
  - [x] 1.3: Call it from `main()` before `app()`
  - [x] 1.4: Verify `setup_error_logger()` in `ui/logger.py` is unaffected (it sets `propagate=False` and has its own file handler)

- [x] **Task 2: Add --verbose flag to sync** (AC3)
  - [x] 2.1: Add `verbose: bool` Typer option with `--verbose` / `-v` aliases
  - [x] 2.2: When `verbose=True`, reset root logger and named loggers to INFO level
  - [x] 2.3: Place verbose logic at top of `sync_command()` before any processing

- [x] **Task 3: Manual verification** (AC1-AC5)
  - [x] 3.1: Run `nest sync --force` on test project — confirmed clean output (progress bar + summary only)
  - [x] 3.2: Confirmed 200+ lines of noise eliminated
  - [x] 3.3: No regressions in processing (3 files, 70 images described, 32 skipped)

## Dev Notes

### Why `force=True` in `basicConfig`

Docling's `StandardPdfPipeline.__init__()` calls `logging.basicConfig(level=logging.INFO)` internally. Python's `basicConfig` is a no-op if the root logger already has handlers — but Docling can run before our configuration in some import-time scenarios. Using `force=True` ensures our WARNING-level config takes precedence regardless of call order.

### Why suppress at `main()` not per-command

The noise affects any command that imports Docling (sync, doctor model checks). Suppressing in `main()` is a single point of control that covers all current and future commands.

### Cross-references

- **Story 2-7** (Sync Command Flags): Established the CLI flag pattern (`--on-error`, `--dry-run`, `--force`, `--no-clean`, `--no-ai`). This story adds `--verbose` / `-v` following the same Typer Annotated pattern.
- **Story 2-8** (Sync CLI Integration): Defined the progress bar and summary output. This story ensures they're the *only* output the user sees by default.
- **Story 2-15** (Error Logging Consolidation): Established error-log-to-file via `ui/logger.py`. This story's suppression does not affect that pipeline — `setup_error_logger` sets `propagate=False`.

# The CLI Terminates Its Process Directly

When the command finishes, the CLI entry point flushes stdout and stderr and terminates the process with `os._exit` instead of returning into CPython's normal shutdown.
The CLI runs Docling's native stack (torch with OpenMP, OpenCV, pdfium), and on Windows that stack intermittently faults with exit code 0xC0000005 (access violation) while the interpreter joins worker threads and runs atexit handlers — after every output file is written and the final progress line is flushed, with no Python traceback possible (issue #41).
Docling deliberately parks idle model-executor threads between runs because PyTorch never frees per-thread state when a thread exits, so those threads are always alive at shutdown and cannot be joined away from the CLI.
Terminating directly skips the teardown where the fault lives; every nest write is synchronous, so once the streams are flushed nothing is lost.

## Considered Options

- **Pin threading or the environment (rejected).** Settings such as `OMP_NUM_THREADS=1` or `torch.set_num_threads(1)` narrow concurrency but do not remove the teardown race, slow model inference, and the faulting library is not proven to be OpenMP specifically.
- **Shut down every executor before returning (rejected).** nest already shuts its own executors down through `with` blocks; the surviving threads belong to Docling's pipeline and are parked on purpose, so the CLI cannot close them.
- **Terminate only on Windows (rejected).** The exit contract is platform-neutral, and the same native stack shows teardown faults on other platforms too; one code path is easier to reason about than two.

## Consequences

- Atexit handlers registered inside the CLI process do not run; `tests/cli/test_main.py` pins this, along with the flushed output and the preserved exit codes for success and failure.
- `main()` never returns, so the console script and `python -m nest.cli.main` both take the direct path; in-process callers (the CliRunner tests) invoke `app` and are unaffected.
- Unexpected exceptions still propagate out of `main()` for a normal traceback exit; only the success and `typer.Exit` paths terminate directly.
- A future feature that needs teardown (for example an atexit-registered cleanup) must find another mechanism, such as finishing the work before the command returns.

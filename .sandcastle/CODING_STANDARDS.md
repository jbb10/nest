# Coding Standards

Standards for the `nest` Python codebase.
`ruff` and strict `pyright` enforce part of this mechanically through the `Makefile`; the rest is enforced in review.
`CONTRIBUTING.md` covers branching, commits and releases.

## Style

- PEP 8 naming: `snake_case` modules, functions and variables, `PascalCase` classes, `UPPER_CASE` constants, leading underscore for private names.
- Absolute imports only (`from nest.core.checksum import compute_sha256`), never relative imports.
- Modern type syntax for Python 3.11+: `list[str]`, `dict[str, int]`, `X | None`. No `typing.List`, `Optional` or `Dict`.
- Every public function has an explicit return type. Use `Literal[...]` for closed string sets.
- `pathlib.Path` for every filesystem path; join with `/`. No string concatenation, `str.replace` on paths, or `os.path.join`.
- Write Nest-generated text with `newline="\n"` so output and checksums are identical on every OS.
- Google-style docstrings on public functions and classes. Comments state what the code cannot show; they do not narrate the next line.
- No `# type: ignore` or `# pyright: ignore` without a one-line reason.

## Architecture

Layers under `src/nest/`:

- `cli/` parses arguments and is the composition root. All dependency wiring happens here.
- `services/` orchestrate work and depend on protocols from `adapters/protocols.py`, not on concrete adapters.
- `core/` holds pure logic with no I/O.
- `adapters/` wrap external systems (filesystem, Docling, LLM providers, manifest) and implement the protocols.
- `agents/` render the VS Code agent files.
- `ui/` holds Rich console helpers.

Rules:

- Inject collaborators through constructors. No module-level singletons or global mutable state.
- Keep Docling imports out of `core/`, `cli/` and `ui/`.
- User-facing output goes through `nest.ui` Rich helpers, never `print()`. Diagnostics go through `logging`. Never mix the two streams.
- User-facing errors state what failed, why, and what to do next.
- Raise subclasses of `NestError` for domain failures. Batch operations record per-file outcomes and keep going rather than raising on one file.
- No hard-coded user paths; resolve them from configuration or injected values.

## Testing

- Tests mirror `src/` under `tests/`, one `test_<module>.py` per module. E2E tests live in `tests/e2e/` and carry the `e2e` marker.
- Test observable behavior through public interfaces. Substitute collaborators at the protocol seam via constructor injection; do not patch internals.
- Name tests after the behavior: `test_sync_skips_unchanged_files`, `test_sync_fails_when_manifest_corrupt`.
- Arrange-Act-Assert structure. No tautological assertions.
- Every bug fix starts with a failing test that reproduces it, at the highest level that can (E2E when the bug is user-visible).
- Never run `nest init` or `nest sync` in the repository root. CLI behavior is verified through E2E tests, which run in isolated temporary workspaces.

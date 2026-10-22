# LLM Names Remote Model Calls, Not AI

Every flag, environment variable, subcommand, identifier, and sentence that refers to a remote language model call says LLM, and AI is reserved for the pipeline as a whole and for the agents that consume the output.
The earlier vocabulary used AI to mean only the LLM call, which implied that Docling layout analysis, OCR, table recognition, and picture classification are not AI; they are, so a run with `--no-llm` is still an AI run.
The public surface was renamed without aliases (`--no-ai` to `--no-llm`, `--ai-only` to `--llm-only`, `nest config ai` to `nest config llm`, `NEST_AI_*` to `NEST_LLM_*`, `.ai_seen` to `.llm_seen`) as a single major release, because two names for one concept would keep the inaccuracy alive in help text and documentation.

## Considered Options

- **Keep the old names as deprecated aliases (rejected).** Aliases keep `--no-ai` visible in help output and shell history, so the misleading reading survives exactly where users form their mental model.
- **Rename only internals and prose (rejected).** The public names are where the inaccuracy is most visible, so leaving them would preserve the problem while adding a mismatch between code and interface.

## Consequences

- A `nest config ai` block already written to a shell RC file is recognised by `nest config llm` and replaced or removed, and an existing `.ai_seen` marker is renamed on sight, so upgrading needs no manual cleanup.
- `NEST_API_KEY`, `NEST_BASE_URL`, `NEST_TEXT_MODEL`, and `NEST_VISION_MODEL` are unchanged; only the `NEST_AI_*` names moved.

"""Conversion completion summaries, separate from the shared command output lifecycle."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.text import Text

from nest.core.models import ConvertFileOutcome, ConvertResult
from nest.ui.messages import LLM_DISABLED_NOTE, display_path, print_needs_llm_block


def display_convert_summary(
    result: ConvertResult,
    console: Console,
    llm_status_note: str = "",
    *,
    verbose: bool = False,
    has_warnings: bool = False,
) -> None:
    """Summarize routine skips while retaining actionable per-file outcomes."""
    if result.failed_count:
        console.print("Convert finished with failures", style="yellow")
    elif has_warnings:
        console.print("Convert complete with warnings", style="yellow")
    else:
        console.print("Convert complete", style="green")
    console.print()
    noun = "file" if result.processed_count == 1 else "files"
    console.print(f"  Converted: {result.processed_count} {noun}")
    console.print(f"  Skipped:   {result.skipped_count}")
    console.print(f"  Failed:    {result.failed_count}")

    if verbose:
        _print_reason_list(console, "Skipped files", result.skips, result.root)
    else:
        routine: Counter[str] = Counter()
        other: list[ConvertFileOutcome] = []
        for outcome in result.skips:
            if outcome.reason.startswith("Output already exists"):
                routine["Outputs already present"] += 1
            elif outcome.reason.startswith("Text file; left in place"):
                routine["Text files left in place"] += 1
            else:
                other.append(outcome)
        for reason, count in routine.items():
            console.print(f"    {reason}: {count}")
        _print_reason_list(console, "Skipped files", other, result.root)

    _print_reason_list(console, "Failed files", result.failures, result.root)
    print_needs_llm_block(
        console,
        [
            display_path(failure.path, result.root)
            for failure in result.failures
            if failure.kind == "needs_llm"
        ],
        llm_disabled=llm_status_note == LLM_DISABLED_NOTE,
        command="nest convert",
    )
    if llm_status_note:
        console.print(f"\n  LLM: {llm_status_note}")
    if result.images_described > 0:
        console.print(f"  Images described: {result.images_described}")
    if result.images_skipped > 0:
        console.print(f"  Images skipped:  {result.images_skipped} (logos/signatures)")
    if result.images_failed > 0:
        console.print(f"  Image descriptions failed: {result.images_failed}")
    if result.pages_transcribed > 0:
        console.print(f"  Pages transcribed by the LLM: {result.pages_transcribed}")
    total_tokens = result.vision_prompt_tokens + result.vision_completion_tokens
    if total_tokens > 0:
        console.print(
            f"  LLM tokens: {total_tokens:,} "
            f"(prompt: {result.vision_prompt_tokens:,}, "
            f"completion: {result.vision_completion_tokens:,})"
        )


def _print_reason_list(
    console: Console, title: str, outcomes: Sequence[ConvertFileOutcome], root: Path
) -> None:
    if not outcomes:
        return
    console.print(f"\n  {title}:")
    for outcome in outcomes:
        console.print(Text(f"    {display_path(outcome.path, root)}: {outcome.reason}"))

---
name: file-bug
description: Diagnose a reported Nest bug from a screenshot, stack trace, or user description, then file an agent-ready bug ticket.
disable-model-invocation: true
---

# File Bug

Turn a bug report into a verified diagnosis and a `ready-for-agent` ticket.

Ticket rules live in [triage](../triage/SKILL.md) (disclaimer, category and state roles), its [AGENT-BRIEF.md](../triage/AGENT-BRIEF.md), and `docs/agents/*`.
Follow `docs/agents/domain.md`. Name a glossary gap in the ticket for `/domain-modeling` rather than coining a term.

## 1. Understand the report

Extract the symptom from the artifact: what ran, with which inputs, options, and Nest version, what happened, what was expected.
Ask the user only for what the artifact and repo cannot answer.

Search open and closed issues for the symptom. If one matches, comment the new evidence there (with the disclaimer) and stop.
If an ADR makes the behaviour intended, tell the reporter which ADR and stop.

## 2. Isolate

Record `git status --short`.
Do all scratch edits in a throwaway `git worktree` off `HEAD`, or off the reporter's ref when the report concerns uncommitted code or another branch.
Keep scratch inputs in a `mktemp -d` directory and run Nest from there as `uv run --project <worktree> nest ...`, because the `nest` on PATH may be another version.
The first run builds the worktree's environment, which is slow.

Remote LLM calls are billable, and the LLM provider takes its configuration from `NEST_*` environment variables. Unset every one it reads (`env -u`) unless the bug needs an LLM, then pass credentials from the main tree's `.env` explicitly.
Point `HOME` at a scratch directory only for commands that write user config or shell RC files, since that also moves the model cache.

## 3. Diagnose

Run `/diagnosing-bugs` Phases 1-4, starting the loop from the user's side (the reporter's inputs and options) instead of a test, then tightening it at a test seam.
Replace its Phase 5 with the smallest scratch fix that turns the minimised repro green, and its Phase 6 with steps 4 and 5 here.

Done when all of these are recorded:

- The minimised repro went red then green with the scratch fix, with both runs' invocation and output. The minimised input is small enough to inline in the ticket, and where a seam exists the repro is a test at that seam.
- The fix's observable behaviour, in ticket terms.
- The candidate regression-test seam through the public interface, or "none, because...".
- The answer to `/diagnosing-bugs`' closing question, what would have prevented this bug.

If the loop cannot be built or no cause is confirmed, run step 4, then file `needs-info` with triage's "established so far" notes, or `ready-for-human` with the partial diagnosis.

## 4. Clean up

Remove the worktree and the scratch directory, and stop background processes.

Done when `git worktree list` shows only the main tree, the scratch directory is gone, and `git status --short` matches the output recorded at the start of step 2.

## 5. File the ticket

Search again for an existing report of the same root cause. If one exists, comment the evidence there and stop.

Title: the symptom in glossary terms. Body: the disclaimer, then the `## Agent Brief` block. Fill the template, plus:

- **Current behavior**: the minimised reproduction with observed versus expected output, and the confirmed root cause.
- **Desired behavior**: the observable behaviour after the fix.
- **Key interfaces**: the types, signatures, and contracts to change.
- **Acceptance criteria**: first, a regression test written test-first (`/tdd`) at the candidate seam, red on this bug. Last, the original reproduction passes.
- **Prefactor**, when no seam exists or the cause is hidden coupling: deepen the module first (`/codebase-design`), or file a separate prefactor ticket and link it as a blocker per `docs/agents/issue-tracker.md`.
- **ADR conflicts**, when the fix contradicts one: name it.

Publish per `docs/agents/issue-tracker.md` with the `bug` category label and the state label from `docs/agents/triage-labels.md` (`ready-for-human` per triage when the fix needs judgment or access an agent lacks).

Done when `gh issue view` shows exactly one category and one state label, every template section filled, a failing regression test (or the reason no seam exists) as the first criterion, and code referenced by symbol outside quoted reproduction output.
Report the issue URL and a one-line root cause.

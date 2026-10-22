# TASK

Fix issue {{TASK_ID}}: {{ISSUE_TITLE}}

Pull in the issue using `gh issue view <ID> --comments`. The `## Agent Brief` comment is the specification; the body and other comments are context. If it has a parent PRD, pull that in too.

Only work on the issue specified.

Work on branch {{BRANCH}}. Make commits and run tests.

# CONTEXT

Here are the last 10 commits:

<recent-commits>

!`git log -n 10 --format="%H%n%ad%n%B---" --date=short`

</recent-commits>

# EXPLORATION

Explore the repo and fill your context window with relevant information that will allow you to complete the task.

Pay extra attention to test files that touch the relevant parts of the code.

# EXECUTION

If applicable, use RGR to complete the task.

1. RED: write one test
2. GREEN: write the implementation to pass that test
3. REPEAT until done
4. REFACTOR the code

# FEEDBACK LOOPS

The `Makefile` is the single source of truth for checks.

Before each commit, run `make lint format-check typecheck test`. Fix formatting with `make format`.

Before outputting COMPLETE, also run `make test-e2e E2E_TIMEOUT=180`. LLM-gated E2E tests skip when `NEST_LLM_API_KEY` is unset; that is expected.

Never run `nest init` or `nest sync` in the repository root. Verify CLI behavior through the E2E tests, which use isolated temporary workspaces.

# COMMIT

Follow `.sandcastle/CODING_STANDARDS.md`. Commit messages use Conventional Commits, because release-please derives versions from them:

```
<type>(<scope>): <imperative subject>

<what changed and key decisions>

Refs #{{TASK_ID}}
```

Use `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `build` or `perf`. Mark breaking changes with `!`.

# THE ISSUE

If the task is not complete, leave a comment on the issue with what was done.

Do not close the issue - this will be done later.

Once complete, output <promise>COMPLETE</promise>.

# FINAL RULES

ONLY WORK ON A SINGLE TASK.

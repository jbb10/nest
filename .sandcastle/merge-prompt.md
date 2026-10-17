# TASK

Merge the following branches into the current branch:

{{BRANCHES}}

For each branch:

1. Run `git merge <branch> --no-edit`
2. If there are merge conflicts, resolve them intelligently by reading both sides and choosing the correct resolution
3. After resolving conflicts, run `make lint format-check typecheck test` to verify everything works
4. If tests fail, fix the issues before proceeding to the next branch

After all branches are merged, run `make test-e2e E2E_TIMEOUT=180` once. If a merge commit is needed, use a Conventional Commit subject such as `chore: merge sandcastle branches`.

# CLOSE ISSUES

For each branch that was merged, close its issue using the following command:

`gh issue close <ID> --comment "Completed by Sandcastle"`

Here are all the issues:

{{ISSUES}}

Once you've merged everything you can, output <promise>COMPLETE</promise>.

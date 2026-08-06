<!--
  Keep PRs small and focused. The PR title MUST follow Conventional Commits
  (e.g. `feat(sync): add parallel processing`) because release automation
  derives the semantic version bump from commit/PR history.
-->
<!--
  Allowed types are defined in CONTRIBUTING.md (the single source of truth).
  Current set: feat, fix, docs, perf, refactor, test, chore, ci, build.
  See release-please-config.json changelog-sections for the corresponding
  changelog section headings.
-->

## Summary

<!-- What does this PR do and why? -->

## Type of change

- [ ] `fix` — bug fix (patch)
- [ ] `feat` — new feature (minor)
- [ ] breaking change (`feat!` / `fix!` / `BREAKING CHANGE:`) (major)
- [ ] `chore` / `docs` / `refactor` / `test` / `ci` / `build` / `perf` (see CONTRIBUTING.md)

## Checklist

- [ ] Branch name follows the convention (`feat/…`, `fix/…`, `chore/…`, `docs/…`, `ci/…`)
- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
- [ ] `make ci` passes locally (lint, format, types, tests)
- [ ] Tests added or updated for the change
- [ ] Documentation updated where relevant

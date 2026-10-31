# Changelog

All notable changes to Nest.

## [3.1.1](https://github.com/jbb10/nest/compare/v3.1.0...v3.1.1) (2026-10-31)


### CI/CD

* **release:** run release-please with a PAT so release PRs get CI checks ([#59](https://github.com/jbb10/nest/issues/59)) ([2ca2805](https://github.com/jbb10/nest/commit/2ca2805bb12241bfb114436b731bccd7705a7496))

## [3.1.0](https://github.com/jbb10/nest/compare/v3.0.0...v3.1.0) (2026-10-31)


### Features

* **cli:** add --version option printing the package version ([1a2ad69](https://github.com/jbb10/nest/commit/1a2ad690501faaf7f9f0055beb7913c86695f29e)), closes [#52](https://github.com/jbb10/nest/issues/52)


### Bug Fixes

* **ci:** export the install-smoke tool directories from a step ([#58](https://github.com/jbb10/nest/issues/58)) ([0df4c81](https://github.com/jbb10/nest/commit/0df4c8168f3d192bcd87b067c91c640341c5ad88))
* **cli:** build the shared --verbose option as a typer parameter ([f01577d](https://github.com/jbb10/nest/commit/f01577dd7533601ab60ca2c17203ebedff0cbb3a)), closes [#51](https://github.com/jbb10/nest/issues/51)
* **cli:** terminate the process directly after the command finishes ([7a8651f](https://github.com/jbb10/nest/commit/7a8651f09e2bb273b25d0ae0b85e67d0cb8fff54)), closes [#41](https://github.com/jbb10/nest/issues/41)


### Refactoring

* **cli:** annotate _terminate as NoReturn and clarify probe helper ([22c03d7](https://github.com/jbb10/nest/commit/22c03d78eeb0a3d04a69d097f9ab904fedea4ca5))
* **scripts:** clarify the dependency check and install smoke tests ([1be573b](https://github.com/jbb10/nest/commit/1be573b7f326b8cc65aaf08b6a74ea582e72aae6))
* **tests:** share the registered-command list between command tests ([e63fd77](https://github.com/jbb10/nest/commit/e63fd776560a0a14c2f9201f8d3536822cccc4bf))


### Documentation

* **contributing:** explain the dependency policy and install smoke ([9f1a2cd](https://github.com/jbb10/nest/commit/9f1a2cdbc1090dbd62f3bf4b39b2c28c95cb78c8)), closes [#52](https://github.com/jbb10/nest/issues/52)


### Testing

* **e2e:** surface CLI output on timeout and normalize sub-default timeouts ([87d1dd5](https://github.com/jbb10/nest/commit/87d1dd545d28395b098a568cb54259ddd497e580)), closes [#41](https://github.com/jbb10/nest/issues/41)


### Build System

* **deps:** bound direct dependency ranges and make the version dynamic ([3966740](https://github.com/jbb10/nest/commit/3966740cd45400273551b4f01e9ea509096177f3)), closes [#52](https://github.com/jbb10/nest/issues/52)


### CI/CD

* **e2e:** allow manual workflow runs ([6e09d92](https://github.com/jbb10/nest/commit/6e09d927479f6aea8e68c158ab04dd91bc9de30f)), closes [#41](https://github.com/jbb10/nest/issues/41)
* **scripts:** add dependency range check and install smoke scripts ([3a14026](https://github.com/jbb10/nest/commit/3a14026c87635594c13329178cf99095e746272a)), closes [#52](https://github.com/jbb10/nest/issues/52)
* **workflows:** smoke-test the installed tool and lock the CI resolution ([2a97124](https://github.com/jbb10/nest/commit/2a97124bb220ba4b6a412f4e024617b98ca606d1)), closes [#52](https://github.com/jbb10/nest/issues/52)

## [3.0.0](https://github.com/jbb10/nest/compare/v2.3.0...v3.0.0) (2026-10-22)


### ⚠ BREAKING CHANGES

* `--no-ai` is now `--no-llm`, `--ai-only` is now `--llm-only`, `nest config ai` is now `nest config llm`, and the `NEST_AI_API_KEY`, `NEST_AI_ENDPOINT`, `NEST_AI_MODEL`, and `NEST_AI_VISION_MODEL` environment variables are now `NEST_LLM_API_KEY`, `NEST_LLM_ENDPOINT`, `NEST_LLM_MODEL`, and `NEST_LLM_VISION_MODEL`. The `_nest_meta/.ai_seen` marker is now `_nest_meta/.llm_seen`.

### Features

* rename AI to LLM for remote model calls and add --llm-only transcription ([#42](https://github.com/jbb10/nest/issues/42)) ([b5ae43f](https://github.com/jbb10/nest/commit/b5ae43f57a1abd6b987e8fc3e00b6d8661a5dc1e))

## [2.3.0](https://github.com/jbb10/nest/compare/v2.2.0...v2.3.0) (2026-10-21)


### Features

* **sync:** support standalone image files as source documents ([#39](https://github.com/jbb10/nest/issues/39)) ([7dff318](https://github.com/jbb10/nest/commit/7dff318558286ebe9748dd72af13ab9db8be1577))

## [2.2.0](https://github.com/jbb10/nest/compare/v2.1.0...v2.2.0) (2026-10-21)


### Features

* **cli:** shared command output and image-description failure policy ([#36](https://github.com/jbb10/nest/issues/36)) ([d3ff137](https://github.com/jbb10/nest/commit/d3ff1371a6ce31596abad9b3a551a624de2abfe5))

## [2.1.0](https://github.com/jbb10/nest/compare/v2.0.0...v2.1.0) (2026-10-18)


### Features

* **convert:** add nest convert for project-free document conversion ([315af9b](https://github.com/jbb10/nest/commit/315af9b8351f60def2423e0a1976d8b4ef51077c)), closes [#20](https://github.com/jbb10/nest/issues/20)


### Bug Fixes

* **deps:** update docling to 2.140.0 ([bfbfe0f](https://github.com/jbb10/nest/commit/bfbfe0f8f6db99f6bbfa3ae1fef4125fd5fd1254)), closes [#4](https://github.com/jbb10/nest/issues/4)
* **sandcastle:** embed a diff summary in the review prompt ([def2e84](https://github.com/jbb10/nest/commit/def2e8458e133ed494375c07884a73894ac7ccf2))
* **sandcastle:** merge branches with commits from earlier runs ([2b9dcf2](https://github.com/jbb10/nest/commit/2b9dcf2c27ecd69f8b548a9643531af7a1396164))


### Refactoring

* **adapters:** polish docling downloader hub cache warming ([c6d0198](https://github.com/jbb10/nest/commit/c6d0198bc5c9b2df47d6d14dbf1c8ecbd1c0d655))
* **ci:** align job banner and document dependency review ([696b25c](https://github.com/jbb10/nest/commit/696b25ca8b02b7ba3e73916422f6aca4611a54a3))
* **convert:** deduplicate shared CLI helpers and convert models ([1f511d5](https://github.com/jbb10/nest/commit/1f511d5762b5b3a485f9f7d91d63a71a6fb39637))
* **sync:** simplify project context candidate lookup ([d7717ae](https://github.com/jbb10/nest/commit/d7717ae569d3928bd316b57ea47726de360d3969))


### Documentation

* add security policy for private vulnerability reporting ([ed774ff](https://github.com/jbb10/nest/commit/ed774ff68a09911fec99d37b3e85afd1c541bdb2)), closes [#6](https://github.com/jbb10/nest/issues/6)


### CI/CD

* add dependency review gate to PR validation ([a15cb63](https://github.com/jbb10/nest/commit/a15cb6322e222f86cca8debcd47cd8efa30afe25)), closes [#6](https://github.com/jbb10/nest/issues/6)
* **deps:** bump GitHub Actions to latest majors ([d0fe4ce](https://github.com/jbb10/nest/commit/d0fe4ce5de2daff28c63c1b1956bb108390233c6)), closes [#4](https://github.com/jbb10/nest/issues/4)

## [2.0.0](https://github.com/jbb10/nest/compare/v1.3.3...v2.0.0) (2026-10-16)


### ⚠ BREAKING CHANGES

* Python 3.10 is no longer supported.

### Features

* require Python 3.11 or newer ([#21](https://github.com/jbb10/nest/issues/21)) ([ed0ed41](https://github.com/jbb10/nest/commit/ed0ed4169df1cd94a6f1903cf6e5471709ed5501))


### Bug Fixes

* **sync:** record every file outcome through one contract ([#23](https://github.com/jbb10/nest/issues/23)) ([0a3477f](https://github.com/jbb10/nest/commit/0a3477f2e02592b2cfebfcc23058b76a2eb8212a))

## [1.3.3](https://github.com/jbb10/nest/compare/v1.3.2...v1.3.3) (2026-10-08)


### Bug Fixes

* **discovery:** follow symlinked and junctioned folders in sources ([#18](https://github.com/jbb10/nest/issues/18)) ([4e047ef](https://github.com/jbb10/nest/commit/4e047ef918168b6b684adbbee5ab6c721ff95eff))


### CI/CD

* optimize GitHub Actions caching ([#2](https://github.com/jbb10/nest/issues/2)) ([7bdd0c1](https://github.com/jbb10/nest/commit/7bdd0c1e5bf4781f571da3ebd50e9f0bf4a888d5))

## [v1.3.2] - 2026-07-09

### Bug Fixes

- **build**: remove redundant force-include causing wheel build failure
## [v1.3.1] - 2026-05-28

### Refactoring

- **services**: extract AI prompts to external files and improve glossary prompt
## [v1.3.0] - 2026-04-27

### Bug Fixes

- **file_discovery**: keep symlinked files under sources dir, skip broken links

### Features

- **logger**: route nest.* log warnings/errors to Rich console

### Maintenance

- update uv.lock
## [v1.2.1] - 2026-04-20

### Bug Fixes

- **tests**: clear all NEST_AI_* env vars in no-AI e2e test
- **tests**: update test to match corrected user-invocable spelling
- **llm**: wrap long warning strings to satisfy line-length lint
- **agents**: correct user-invocable typo in sub-agent templates
- **llm**: remove hardcoded model defaults, standardise NEST_AI_* env vars

### Maintenance

- update uv.lock
- add DELETE/ to gitignore
- update uv.lock
## [v1.2.0] - 2026-04-01

### Bug Fixes

- configure test AI proxy credentials and fix e2e test assertions

### Features

- add experimental PowerShell support for AI config on Windows
## [v1.1.0] - 2026-03-26

### Features

- **epic-10**: multi-agent architecture — coordinator, researcher, synthesizer, planner
## [v1.0.0] - 2026-03-25

### Documentation

- mark story 7.4 done in story file and sprint-status.yaml

### Features

- remove project name concept, standardize env vars, suppress log noise
- **epic-7**: wire PictureDescriptionService into sync pipeline with cross-file parallelism
- refine glossary and index AI output

### Maintenance

- update README with AI sync docs, misc cleanup
## [v0.4.0] - 2026-03-16

### Features

- **ai**: add built-in enrichment and config workflows
## [v0.3.1] - 2026-03-05

### Bug Fixes

- doctor version check uses git tags instead of PyPI, migration cleans up legacy files

### Maintenance

- update version to 0.3.0 in uv.lock and log additional errors
## [v0.3.0] - 2026-02-28

### Bug Fixes

- resolve pyright strict type errors in services
- auto-format code with ruff
- resolve lint errors (imports, line length)

### Features

- index enrichment, glossary agent, passthrough files, .nest/ metadata
## [v0.2.0] - 2026-02-12

### Features

- **update**: implement nest update command (Epic 4)

### Maintenance

- **update BMAD**: Updated BMAD and added epic runner
## [v0.1.3] - 2026-02-10

### Bug Fixes

- lazy docling imports for robustness when docling not installed

### Documentation

- mark story 3-4 complete - all E2E tests passing (30/30)

### Features

- **doctor**: add --fix flag CLI integration with issue summary (Story 3.6)

### Maintenance

- mark story 3-6 as done
## [v0.1.2] - 2026-02-10

### Bug Fixes

- sync re-processes all files due to manifest key mismatch
- Code review findings (Story 2.11) - Fix hardcoded strings, sort order, and implement lazy docling imports for robustness
- **doctor**: code review fixes - consistent DI, error logging, orchestration tests
- **doctor**: code review fixes - CR-3,5,7,9 and E2E tests
- **doctor**: harden env checks and e2e runner
- **doctor**: code review fixes - remove duplicate protocol, fix type sig
- remove test artifacts from repo root
- **3-1**: code review fixes - clean test artifacts, update .gitignore
- **2-10-folder-naming-refactor**: code review fixes - sync service paths and tests
- **e2e**: add explicit dev deps and improve test assertion
- **e2e**: refactor fixtures to use proper DI chain from conftest.py
- **sync**: commit manifest before orphan cleanup

### Documentation

- **sprint**: mark 3-2 environment validation done
- add dev agent testing protocol to prevent repo pollution
- add E2E testing framework as Story 2.9

### Features

- **sync**: add CONTEXT_TEXT_EXTENSIONS for multi-format context indexing
- **doctor**: add project state validation (Story 3.4)
- implement nest doctor command with environment validation
- **doctor**: update project state validation status to ready-for-dev
- **doctor**: add ML model validation to nest doctor command
- **e2e**: print temp directory path at end of E2E test runs
- **e2e**: add E2E testing framework for CLI commands

### Refactoring

- update folder names and orphan logic for user-curated files

### Testing

- partial test updates for folder naming refactor
## [v0.1.1] - 2026-01-16

### Documentation

- fix installation URL and update examples
## [v0.1.0] - 2026-01-16

### Bug Fixes

- **types**: fix strict type checking errors for beta release
- **2-8**: optimize sync discovery performance (code review)
- **sync**: inject error_logger into SyncService for AC5 compliance
- **sync**: code review fixes for orphan cleanup
- **2-5**: code review fixes - lint, types, test coverage
- **sync**: code review fixes - manifest robustness and decoupling
- **2-3**: code review fixes - type errors, lint, docstrings
- **bmm**: add merge-to-main step in code-review workflow
- **bmm**: add step 6 to code-review workflow for git commit
- **2-2**: code review fixes - TableFormer config and error logging
- **sync**: address code review feedback for Story 2.1
- **review**: Address code review findings for Story 1.4
- **review**: Address code review findings for Story 1.3
- **review**: complete story 1-3 code review fixes
- **review**: complete story 1-2 code review fixes

### Documentation

- **2-6-orphan-cleanup**: mark story complete after code review
- update dev story with code review outcome

### Features

- **sync**: add Rich progress bar and enhanced summary display
- **sync**: add command flags and error handling
- **sync**: add orphan cleanup for stale processed files
- **sync**: implement master index generation and SyncService
- **sync**: implement manifest tracking and updates
- **sync**: implement output mirroring and file writing
- **processing**: implement Docling document processor
- Add file discovery and checksum engine (Story 2.1)
- Add ML model download and caching (Story 1.3)
- **agent**: implement VS Code agent file generation

### Maintenance

- **2-8**: mark story as done and update sprint status
- mark story 2.8 ready for review
- add story 2-7 sync command flags and error handling
- ignore and remove .DS_Store files
- mark Story 2.1 as done
- initial project setup with BMAD artifacts

### Testing

- Add missing test coverage for CLI integration (Story 1.4)

# Changelog

All notable changes to Nest.

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


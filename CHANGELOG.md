# Changelog

All notable changes to Nest.

## [0.1.2] - 2026-02-10

### Features
- **sync**: Add context text file support for multi-format context indexing (Story 2.11)
- **doctor**: Add project state validation — manifest integrity, agent file, folder checks (Story 3.4)
- **doctor**: Add issue remediation with `--fix` flag (Story 3.5)

### Bug Fixes
- **sync**: Fix re-processing all files due to manifest key mismatch (relative vs absolute paths)
- **doctor**: Code review fixes — consistent DI, error logging, orchestration tests
- **sync**: Fix hardcoded strings, sort order, lazy docling imports for robustness (Story 2.11 review)

## [0.1.1] - 2026-01-16

### Documentation
- Fix GitHub repository URL (jbb10/nest)
- Update VS Code agent instructions to use dropdown selection instead of @mention
- Improve README examples for software delivery workflows
- Update agent template with consulting-relevant example interactions

## [0.1.0] - 2026-01-16

### Features
- **init**: Project scaffolding with VS Code agent file generation
- **init**: Docling ML model download and caching
- **sync**: File discovery and checksum-based change detection
- **sync**: Docling document processing (PDF, DOCX, PPTX, XLSX, HTML)
- **sync**: Output mirroring with directory structure preservation
- **sync**: Manifest tracking and updates
- **sync**: Master index generation (00_MASTER_INDEX.md)
- **sync**: Orphan cleanup for deleted source files
- **sync**: Command flags (--on-error, --dry-run, --force, --no-clean)
- **sync**: Rich progress bar and summary display

### Infrastructure
- CLI framework with Typer and Rich
- Comprehensive test suite (270 tests)
- Strict type checking with Pyright
- Linting with Ruff

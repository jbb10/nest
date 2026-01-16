# Changelog

All notable changes to Nest.

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

# E2E Testing Framework Requirements

**Date**: 2026-01-18  
**Author**: Jóhann (via TEA)  
**Status**: Ready for Story Creation  
**Story**: 2.9 - E2E Testing Framework

---

## Overview

Nest CLI needs a proper End-to-End (E2E) testing framework that validates the full command flows with real file I/O and actual Docling processing. This is distinct from the existing unit and integration tests which use mocks.

---

## Scope

### What E2E Means for Nest CLI

| Layer | What It Tests | Current State |
|-------|---------------|---------------|
| Unit | Pure functions, business logic | ✅ Exists |
| Integration | Service orchestration with mocked I/O | ✅ Exists |
| **E2E** | Full CLI invocation, real file I/O, actual Docling | ❌ **Needed** |

---

## Requirements

### 1. Test Infrastructure

#### 1.1 Directory Structure
```
tests/
├── e2e/                           # NEW: End-to-end tests
│   ├── conftest.py                # E2E fixtures (temp projects, CLI runner)
│   ├── test_init_e2e.py           # Full init command flow
│   ├── test_sync_e2e.py           # Full sync command flow
│   ├── test_negative_e2e.py       # Negative path tests
│   └── fixtures/                  # Real test documents
│       ├── sample.pdf
│       ├── sample.docx            # Word document
│       ├── sample.pptx            # PowerPoint
│       └── sample.xlsx            # Excel/XML
```

#### 1.2 CLI Test Runner Fixture
- Invoke real `nest` commands via subprocess
- Capture stdout, stderr, and exit code
- Return structured result for assertions

#### 1.3 Isolated Project Fixture
- Create temporary directory for each test class (`scope="class"`)
- Clean up after test completion
- Provide helper methods to set up file structures

#### 1.4 Test Markers
```python
# pytest markers for selective test runs
markers = [
    "e2e: End-to-end tests (require real Docling)",
]
```

Commands:
- `pytest -m "not e2e"` — Run fast tests only (dev loop)
- `pytest -m "e2e" --timeout=60` — Run E2E tests with 60-second timeout

#### 1.5 Skip Condition for Missing Docling Models
```python
import pytest
from pathlib import Path

def docling_available() -> bool:
    """Check if Docling models are downloaded and available."""
    cache_dir = Path.home() / ".cache" / "docling"
    return cache_dir.exists() and any(cache_dir.iterdir())

skip_without_docling = pytest.mark.skipif(
    not docling_available(),
    reason="Docling models not downloaded. Run 'nest init' first to download models."
)
```

#### 1.6 Git Attributes for Binary Fixtures
```gitattributes
# E2E test fixtures - treat as binary to prevent line-ending issues
tests/e2e/fixtures/*.pdf binary
tests/e2e/fixtures/*.docx binary
tests/e2e/fixtures/*.pptx binary
tests/e2e/fixtures/*.xlsx binary
```

---

### 2. Init Command E2E Test

**Test file**: `tests/e2e/test_init_e2e.py`

#### Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| AC1 | Command exits successfully | `exit_code == 0` |
| AC2 | Input folder created | `raw_inbox/` directory exists |
| AC3 | Input folder is empty | `raw_inbox/` contains no files |
| AC4 | Output folder created | `processed_context/` directory exists |
| AC5 | Output folder is empty | `processed_context/` contains no files |
| AC6 | Config/manifest initialized | `.nest_manifest.json` exists with valid JSON |

#### Test Pseudocode
```python
@skip_without_docling
class TestInitE2E:
    def test_init_creates_expected_structure(self, cli_runner, temp_project):
        """E2E: init command creates correct folder structure."""
        # Act
        result = cli_runner(["init", "TestProject"], cwd=temp_project)
        
        # Assert - Exit code
        assert result.exit_code == 0
        
        # Assert - Input folder
        raw_inbox = temp_project / "raw_inbox"
        assert raw_inbox.exists()
        assert raw_inbox.is_dir()
        assert list(raw_inbox.iterdir()) == []  # Empty
        
        # Assert - Output folder
        processed = temp_project / "processed_context"
        assert processed.exists()
        assert processed.is_dir()
        assert list(processed.iterdir()) == []  # Empty
        
        # Assert - Nest manifest
        manifest = temp_project / ".nest_manifest.json"
        assert manifest.exists()
        manifest_data = json.loads(manifest.read_text())
        assert manifest_data["project_name"] == "TestProject"
```

---

### 3. Sync Command E2E Test

**Test file**: `tests/e2e/test_sync_e2e.py`

#### Test Input Structure

Place 4 test documents in a **nested folder structure**:

```
raw_inbox/
├── reports/
│   ├── quarterly.pdf
│   └── summary.docx
└── presentations/
    ├── deck.pptx
    └── data.xlsx
```

#### Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| AC1 | Command exits successfully | `exit_code == 0` |
| AC2 | Output mirrors input structure | Same folder hierarchy in `processed_context/` |
| AC3 | All outputs are markdown | Files end in `.md` extension |
| AC4 | All outputs non-empty | Each `.md` file has content |
| AC5 | Manifest is updated | Manifest contains entries for all 4 files |
| AC6 | Correct file count reported | stdout indicates 4 files processed |

#### Expected Output Structure
```
processed_context/
├── reports/
│   ├── quarterly.md
│   └── summary.md
└── presentations/
    ├── deck.md
    └── data.md
```

#### Test Pseudocode
```python
@skip_without_docling
class TestSyncE2E:
    def test_sync_processes_nested_documents(self, cli_runner, temp_project, sample_documents):
        """E2E: sync processes documents and mirrors folder structure."""
        # Arrange - Init first
        cli_runner(["init", "TestProject"], cwd=temp_project)
        
        # Arrange - sample_documents fixture copies files to:
        # raw_inbox/reports/quarterly.pdf
        # raw_inbox/reports/summary.docx
        # raw_inbox/presentations/deck.pptx
        # raw_inbox/presentations/data.xlsx
        
        # Act
        result = cli_runner(["sync"], cwd=temp_project)
        
        # Assert - Exit code
        assert result.exit_code == 0
        
        # Assert - Output structure mirrors input
        processed = temp_project / "processed_context"
        
        expected_outputs = [
            processed / "reports" / "quarterly.md",
            processed / "reports" / "summary.md",
            processed / "presentations" / "deck.md",
            processed / "presentations" / "data.md",
        ]
        
        for output_path in expected_outputs:
            # File exists
            assert output_path.exists(), f"Missing: {output_path}"
            # Is markdown
            assert output_path.suffix == ".md"
            # Non-empty content
            content = output_path.read_text()
            assert content.strip(), f"Empty file: {output_path}"
        
        # Assert - Manifest updated
        manifest = temp_project / ".nest_manifest.json"
        assert manifest.exists()
        manifest_data = json.loads(manifest.read_text())
        assert len(manifest_data["files"]) == 4
        
        # Assert - Correct count in output
        assert "4" in result.stdout  # or specific message format
```

---

### 4. Negative Path E2E Tests

**Test file**: `tests/e2e/test_negative_e2e.py`

| # | Test Name | Command | Expected Behavior |
|---|-----------|---------|-------------------|
| N1 | `test_sync_without_init` | `nest sync` in empty dir | Exit code 1, error: "No Nest project found" |
| N2 | `test_init_existing_project` | `nest init` where manifest exists | Exit code 1, error: "Nest project already exists" |
| N3 | `test_init_without_name` | `nest init` (no args) | Exit code 1, error: "Project name required" |
| N4 | `test_sync_skips_corrupt_file` | Corrupt PDF + `sync` | Skip file, log error, process others, exit 0 |
| N5 | `test_sync_fail_mode_aborts` | Corrupt PDF + `--on-error=fail` | Exit code 1, abort immediately |
| N6 | `test_sync_ignores_unsupported` | `.txt` file in inbox | File ignored, no error |
| N7 | `test_sync_empty_inbox` | No files in `raw_inbox/` | Exit code 0, "No files to process" |

#### Test Pseudocode for Key Negative Tests
```python
class TestNegativeE2E:
    def test_sync_without_init(self, cli_runner, temp_project):
        """E2E: sync fails gracefully without init."""
        result = cli_runner(["sync"], cwd=temp_project)
        
        assert result.exit_code == 1
        assert "No Nest project found" in result.stderr or "nest init" in result.stderr

    def test_init_existing_project(self, cli_runner, temp_project):
        """E2E: init fails if project already exists."""
        # First init succeeds
        cli_runner(["init", "Project1"], cwd=temp_project)
        
        # Second init fails
        result = cli_runner(["init", "Project2"], cwd=temp_project)
        
        assert result.exit_code == 1
        assert "already exists" in result.stderr.lower()

    @skip_without_docling
    def test_sync_skips_corrupt_file(self, cli_runner, temp_project, corrupt_pdf):
        """E2E: sync skips corrupt files but continues processing."""
        cli_runner(["init", "TestProject"], cwd=temp_project)
        
        # corrupt_pdf fixture creates a truncated/invalid PDF
        
        result = cli_runner(["sync"], cwd=temp_project)
        
        # Should succeed overall (skip mode is default)
        assert result.exit_code == 0
        # Error should be logged
        error_log = temp_project / ".nest_errors.log"
        assert error_log.exists()
```

---

### 5. Test Documents

**Location**: `tests/e2e/fixtures/`

Requirements for test documents:
- **Small file size** — Keep each under 100KB for fast processing
- **Simple content** — Basic text/tables, no complex formatting
- **Diverse types** — One of each supported format

| File | Type | Content Suggestion |
|------|------|-------------------|
| `quarterly.pdf` | PDF | Single page with title and 2-3 paragraphs |
| `summary.docx` | Word | Title, bullet list, short paragraph |
| `deck.pptx` | PowerPoint | 2-3 slides with titles and bullet points |
| `data.xlsx` | Excel | Simple table with headers and 5-10 rows |

---

### 6. Configuration

#### pytest Configuration (pyproject.toml)
```toml
[tool.pytest.ini_options]
markers = [
    "e2e: End-to-end tests (require real Docling, may be slow)",
]
```

#### Timeout
- E2E tests should use `--timeout=60` (60 seconds)
- Expected actual runtime: 10-15 seconds for sync test

---

## Process Requirements

### E2E Tests as Story Completion Gate

**CRITICAL**: A user story MUST NOT be considered complete until:
1. All unit tests pass
2. All integration tests pass  
3. **All E2E tests pass** (when applicable to the story's functionality)

This requirement applies to any story that modifies:
- CLI command behavior
- Document processing logic
- File system operations
- Manifest handling

### E2E Consideration in Story Creation

When the Scrum Master creates a new story, they MUST:
1. Review existing E2E tests for coverage
2. Determine if new E2E tests are needed for the story
3. Add E2E test requirements to the story's acceptance criteria if needed
4. Document which existing E2E tests validate the story's functionality

---

## Non-Requirements (Out of Scope)

- CI pipeline changes (separate story)
- Performance benchmarking
- Docling model caching strategy
- Complex error scenario E2E tests (beyond the 7 negative tests defined)

---

## Dependencies

- Existing `nest init` and `nest sync` commands must be working
- Docling models must be available (pre-downloaded)
- pytest and pytest-timeout installed

---

## Acceptance Criteria Summary

| Category | AC Count | Key Verifications |
|----------|----------|-------------------|
| E2E Init Test | 6 | Folders created, empty, manifest exists |
| E2E Sync Test | 6 | Structure mirrored, all markdown, non-empty, manifest correct |
| Negative Tests | 7 | Error handling for invalid states |
| Infrastructure | 6 | Fixtures, runner, markers, timeout, skip condition, gitattributes |

**Total Acceptance Criteria**: 25

---

## Notes from Jóhann

> "I'm not too worried about test execution time being too slow because I'll just make sure to put in some simple files into a simple file structure and then it should only take maybe 10-15 seconds for the sync."

> "After an init, we should verify more than just the exit code. We should verify that the expected folders are there — there should be an empty output folder and there should be an empty input folder."

> "For sync, I'll put in 1 PDF, 1 Word file, 1 PowerPoint file, 1 Excel file and put them into a folder structure. We should verify that the output files are in that folder structure and they are all markdown."

> "E2E tests should be required for story completion. When we add new logic, we should always look at the E2E tests and consider whether we need to add new ones or whether the existing tests cover the new logic."

---

## Story Title

**Story 2.9: E2E Testing Framework for CLI Commands**

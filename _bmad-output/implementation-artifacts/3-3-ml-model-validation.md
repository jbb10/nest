# Story 3.3: ML Model Validation

Status: ready-for-dev
Branch: feat/3-3-ml-model-validation

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want **to verify Docling models are properly cached**,
so that **sync will work without download delays**.

## Business Context

This is the third story in Epic 3 (Project Visibility & Health). The `nest doctor` command now includes environment validation (Story 3.2). This story extends it with ML model validation to help users verify Docling models are properly cached before running `nest sync`.

**Why ML Model Validation Matters:**
1. **Docling models are ~2GB** - First-time sync can stall if models aren't pre-downloaded
2. **Cache corruption** - Model files can become corrupt, causing silent failures
3. **Missing models** - Users may have partial downloads from network timeouts
4. **Disk space** - Users need visibility into cache size and location

**Functional Requirements Covered:** FR20 (Doctor: ML model validation)

## Acceptance Criteria

### AC1: Show Cached Models with Status and Sizes

**Given** I run `nest doctor`
**When** ML model validation runs
**Then** output shows:
```
   ML Models:
   ├─ Models:         cached ✓ (1.8 GB)
   └─ Cache path:     ~/.cache/docling/models/
```

**Given** models are fully cached
**When** validation displays
**Then** shows aggregate size in human-readable format (MB or GB)

### AC2: Show Warning When Models Not Cached

**Given** models are NOT cached (cache dir empty or missing)
**When** validation runs
**Then** warning shows:
```
   ML Models:
   ├─ Models:         not found ✗
   │  → Run `nest init` to download models
   └─ Cache path:     ~/.cache/docling/models/ (empty)
```

### AC3: Show Cache Directory Status

**Given** cache directory doesn't exist
**When** validation runs
**Then** shows: `Cache path: ~/.cache/docling/models/ (not created)`

**Given** cache directory exists but is empty
**When** validation runs
**Then** shows: `Cache path: ~/.cache/docling/models/ (empty)`

**Given** cache directory exists with models
**When** validation runs
**Then** shows: `Cache path: ~/.cache/docling/models/`

### AC4: Integrate with Existing Doctor Output

**Given** `nest doctor` runs
**When** all validations complete
**Then** output shows Environment section THEN ML Models section:
```
🩺 Nest Doctor

   Environment:
   ├─ Python:         3.11.4 ✓
   ├─ uv:             0.4.12 ✓
   └─ Nest:           1.0.0 ✓

   ML Models:
   ├─ Models:         cached ✓ (1.8 GB)
   └─ Cache path:     ~/.cache/docling/models/
```

### AC5: Doctor Command Continues to Work Outside Project

**Given** `nest doctor` runs outside a Nest project
**When** command executes
**Then** environment checks run
**And** ML model checks run
**And** note indicates: "Run in a Nest project for full diagnostics"

## E2E Testing Requirements

- [x] Existing E2E tests cover this story's functionality: No - model validation is new
- [x] New E2E tests required: Yes - add E2E tests for model validation display
- [x] E2E test execution required for story completion: Yes

**New E2E Tests Needed:**
1. `test_doctor_shows_model_status()` - Doctor displays ML Models section
2. `test_doctor_shows_model_cache_path()` - Doctor displays cache path

**Note:** Testing "models not cached" scenario is difficult in E2E since CI/dev environments have models downloaded. Unit tests with mocking will cover that path.

## Tasks / Subtasks

### Task 1: Extend DoctorService with Model Validation (AC: 1, 2, 3)
- [x] 1.1: Create `ModelStatus` dataclass in `doctor_service.py`
  - Fields: `cached: bool`, `size_bytes: int | None`, `cache_path: Path`, `cache_status: Literal["exists", "empty", "not_created"]`
- [x] 1.2: Create `ModelReport` dataclass in `doctor_service.py`
  - Fields: `models: ModelStatus`
  - Property: `all_pass` for quick status check
- [x] 1.3: Add `check_ml_models()` method to `DoctorService`
  - Use `DoclingModelDownloader` to check cache status
  - Calculate total size of cached models
  - Return `ModelReport`
- [x] 1.4: Add protocol `ModelCheckerProtocol` to `adapters/protocols.py`
  - Methods: `are_models_cached()`, `get_cache_path()`, `get_cache_size()`

### Task 2: Extend DoclingModelDownloader with Model Info Methods (AC: 1, 3)
- [x] 2.1: Add `get_cache_size()` method to `DoclingModelDownloader`
  - Recursively calculate size of all files in cache directory
  - Return total bytes
- [x] 2.2: Add `get_cache_status()` method to `DoclingModelDownloader`
  - Return "not_created" if cache dir doesn't exist
  - Return "empty" if cache dir exists but is empty
  - Return "exists" if cache dir has content

### Task 3: Update Doctor CLI Command (AC: 4)
- [x] 3.1: Update `doctor_cmd.py` to inject `DoclingModelDownloader`
- [x] 3.2: Call `check_ml_models()` in doctor command
- [x] 3.3: Pass `ModelReport` to display function

### Task 4: Extend Doctor Display for Model Output (AC: 1, 2, 3, 4)
- [x] 4.1: Add `display_model_report()` function to `doctor_display.py`
  - Rich Tree format matching environment section
  - Color-coded status indicators
  - Human-readable size formatting
- [x] 4.2: Update `display_doctor_report()` to accept optional `ModelReport`
- [x] 4.3: Format cache path with status indicator (exists/empty/not created)

### Task 5: Add Unit Tests (AC: all)
- [x] 5.1: Add tests to `tests/services/test_doctor_service.py`
  - Test `check_ml_models()` with models cached
  - Test `check_ml_models()` with models not cached
  - Test `check_ml_models()` with empty cache dir
- [x] 5.2: Add tests to `tests/adapters/test_docling_downloader.py`
  - Test `get_cache_size()` calculation
  - Test `get_cache_status()` for all states
- [x] 5.3: Add tests to `tests/ui/test_doctor_display.py`
  - Test model report display with cached models
  - Test model report display with missing models
  - Test cache path formatting

### Task 6: Add E2E Tests (AC: all)
- [x] 6.1: Add to `tests/e2e/test_doctor_e2e.py`
- [x] 6.2: Add `test_doctor_shows_model_status()` - Verify "ML Models:" section appears
- [x] 6.3: Add `test_doctor_shows_model_cache_path()` - Verify cache path is displayed

### Task 7: Run Full Test Suite
- [x] 7.1: Run `pytest -m "not e2e"` - all unit/integration tests pass
- [x] 7.2: Run `pytest -m "e2e"` - all E2E tests pass
- [x] 7.3: Run `ruff check` - no linting errors
- [x] 7.4: Run `pyright` - no type errors

## Dev Notes

### Architecture Compliance

**Layer Structure:**
- `cli/doctor_cmd.py` → Composition root, injects `DoclingModelDownloader`
- `services/doctor_service.py` → Orchestrates model validation via protocol
- `adapters/docling_downloader.py` → Implements model info methods
- `ui/doctor_display.py` → Rich formatted output

**Protocol-Based DI:**
The service should depend on a protocol, not the concrete `DoclingModelDownloader`:

```python
class ModelCheckerProtocol(Protocol):
    """Protocol for ML model cache operations."""
    
    def are_models_cached(self) -> bool: ...
    def get_cache_path(self) -> Path: ...
    def get_cache_size(self) -> int: ...
    def get_cache_status(self) -> Literal["exists", "empty", "not_created"]: ...
```

**Composition Root (cli/doctor_cmd.py):**
```python
def create_doctor_service() -> DoctorService:
    return DoctorService(
        model_checker=DoclingModelDownloader(),  # Inject via protocol
    )
```

### Data Structures

**ModelStatus:**
```python
@dataclass
class ModelStatus:
    """Status for ML model cache check."""
    cached: bool                                      # True if models are downloaded
    size_bytes: int | None                            # Total cache size (None if not cached)
    cache_path: Path                                  # Path to cache directory
    cache_status: Literal["exists", "empty", "not_created"]
    suggestion: str | None = None                     # Remediation hint
```

**ModelReport:**
```python
@dataclass
class ModelReport:
    """Complete ML model validation report."""
    models: ModelStatus
    
    @property
    def all_pass(self) -> bool:
        """True if models are cached."""
        return self.models.cached
```

### DoctorService Extension

```python
class DoctorService:
    """Validates development environment and project state."""
    
    def __init__(self, model_checker: ModelCheckerProtocol | None = None) -> None:
        """Initialize doctor service.
        
        Args:
            model_checker: Optional model checker for ML validation.
                          If None, model checks will be skipped.
        """
        self._model_checker = model_checker
    
    def check_environment(self) -> EnvironmentReport:
        """Check Python, uv, and Nest versions."""
        # Existing implementation
        ...
    
    def check_ml_models(self) -> ModelReport | None:
        """Check ML model cache status.
        
        Returns:
            ModelReport if model checker is configured, None otherwise.
        """
        if self._model_checker is None:
            return None
        
        cached = self._model_checker.are_models_cached()
        cache_path = self._model_checker.get_cache_path()
        cache_status = self._model_checker.get_cache_status()
        
        size_bytes = None
        suggestion = None
        
        if cached:
            size_bytes = self._model_checker.get_cache_size()
        else:
            suggestion = "Run `nest init` to download models"
        
        return ModelReport(
            models=ModelStatus(
                cached=cached,
                size_bytes=size_bytes,
                cache_path=cache_path,
                cache_status=cache_status,
                suggestion=suggestion,
            )
        )
```

### DoclingModelDownloader Extension

```python
def get_cache_size(self) -> int:
    """Get total size of cached models in bytes.
    
    Returns:
        Total size in bytes, 0 if cache doesn't exist or is empty.
    """
    cache_dir = self.get_cache_path()
    if not cache_dir.exists():
        return 0
    
    total_size = 0
    for file_path in cache_dir.rglob("*"):
        if file_path.is_file():
            total_size += file_path.stat().st_size
    
    return total_size

def get_cache_status(self) -> Literal["exists", "empty", "not_created"]:
    """Get status of cache directory.
    
    Returns:
        "not_created" if directory doesn't exist
        "empty" if directory exists but has no files
        "exists" if directory has content
    """
    cache_dir = self.get_cache_path()
    
    if not cache_dir.exists():
        return "not_created"
    
    # Check if any files exist (not just directories)
    has_files = any(cache_dir.rglob("*"))
    return "exists" if has_files else "empty"
```

### Rich Output Format

Expected output format (models cached):
```
🩺 Nest Doctor

   Environment:
   ├─ Python:         3.11.4 ✓
   ├─ uv:             0.4.12 ✓
   └─ Nest:           1.0.0 ✓

   ML Models:
   ├─ Models:         cached ✓ (1.8 GB)
   └─ Cache path:     ~/.cache/docling/models/
```

Expected output format (models not cached):
```
🩺 Nest Doctor

   Environment:
   ├─ Python:         3.11.4 ✓
   ├─ uv:             0.4.12 ✓
   └─ Nest:           1.0.0 ✓

   ML Models:
   ├─ Models:         not found ✗
   │  → Run `nest init` to download models
   └─ Cache path:     ~/.cache/docling/models/ (not created)
```

### Human-Readable Size Formatting

```python
def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size.
    
    Args:
        size_bytes: Size in bytes.
        
    Returns:
        Human-readable string (e.g., "1.8 GB", "892 MB").
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            if unit in ["B", "KB"]:
                return f"{size_bytes} {unit}"
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
```

### Testing Approach

**Unit Tests (mocked):**
- Mock `DoclingModelDownloader` via protocol
- Test all cache states: cached, empty, not_created
- Test size calculation with various file structures
- Test display formatting

**E2E Tests (real environment):**
- In CI/dev environments, models are typically cached
- Test that "ML Models:" section appears in output
- Test that cache path is displayed
- Cannot easily test "not cached" scenario in E2E

**Mock Example:**
```python
class MockModelChecker:
    def __init__(self, cached: bool = True, size: int = 1_800_000_000):
        self._cached = cached
        self._size = size
    
    def are_models_cached(self) -> bool:
        return self._cached
    
    def get_cache_path(self) -> Path:
        return Path.home() / ".cache" / "docling" / "models"
    
    def get_cache_size(self) -> int:
        return self._size
    
    def get_cache_status(self) -> str:
        if not self._cached:
            return "not_created"
        return "exists"
```

### Project Structure Notes

**Files to Modify:**
- `src/nest/services/doctor_service.py` - Add ModelStatus, ModelReport, check_ml_models()
- `src/nest/adapters/protocols.py` - Add ModelCheckerProtocol
- `src/nest/adapters/docling_downloader.py` - Add get_cache_size(), get_cache_status()
- `src/nest/cli/doctor_cmd.py` - Inject model checker, call check_ml_models()
- `src/nest/ui/doctor_display.py` - Add display_model_report(), update main display

**Files to Create:**
- None (extending existing files)

**Test Files to Modify:**
- `tests/services/test_doctor_service.py` - Add model validation tests
- `tests/adapters/test_docling_downloader.py` - Add cache info tests
- `tests/ui/test_doctor_display.py` - Add model display tests
- `tests/e2e/test_doctor_e2e.py` - Add model status E2E tests

### CRITICAL: Dev Agent Testing Protocol

```
🚨 NEVER run nest init|sync|status|doctor commands directly in the repository
✗ FORBIDDEN: nest init "TestProject"  (pollutes repo with .nest_manifest.json)
✗ FORBIDDEN: nest sync                (creates _nest_context/ artifacts in repo)

✓ CORRECT: pytest tests/services/test_doctor_service.py
✓ CORRECT: pytest tests/e2e/test_doctor_e2e.py -m e2e
✓ CORRECT: pytest -m "not e2e"  (all unit tests)
```

### Previous Story Learnings

From Story 3.2 (Environment Validation):
- DoctorService uses dataclasses for reports (EnvironmentStatus, EnvironmentReport)
- doctor_display.py uses Rich Tree for hierarchical output
- Color-coded indicators: `[green]✓[/green]`, `[red]✗[/red]`, `[yellow]⚠[/yellow]`
- Suggestions displayed with `→` prefix as sub-nodes
- Exit code 0 for all cases - doctor is informational

From Story 3.1 (Project Status Display):
- Rich Tree formatting established
- Consistent color patterns across UI

From Architecture:
- Protocol-based DI for testability
- Services depend on protocols, not implementations
- Composition root in CLI layer

### Git Workflow Reference

```bash
# Before starting implementation
git checkout main && git pull origin main
git checkout -b feat/3-3-ml-model-validation

# After completing implementation
./scripts/ci-lint.sh && ./scripts/ci-typecheck.sh && ./scripts/ci-test.sh

# Commit with conventional format
git commit -m "feat(doctor): add ML model validation"
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.3: ML Model Validation]
- [Source: _bmad-output/planning-artifacts/architecture.md#Testing Strategy]
- [Source: _bmad-output/project-context.md#Architecture & Dependency Injection]
- [Source: _bmad-output/implementation-artifacts/3-2-environment-validation.md] - Pattern reference
- [Source: src/nest/adapters/docling_downloader.py] - Existing model download logic
- [Source: src/nest/services/doctor_service.py] - Existing doctor service
- [Source: src/nest/ui/doctor_display.py] - Existing display patterns

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5

### Debug Log References

**Code Review Fixes (2026-02-06):**
- Fixed architecture violation: Removed duplicate `ModelCheckerProtocol` from `doctor_service.py`
- Added import of `ModelCheckerProtocol` from `adapters.protocols`
- Fixed type signature: Updated `get_cache_status()` return type to `Literal["exists", "empty", "not_created"]`
- Updated File List to document all changed files including deleted agent file
- All tests passing (324), pyright clean, ruff clean

### Completion Notes List

✅ **All Acceptance Criteria Satisfied:**
- AC1: Model status with size displayed in doctor output
- AC2: Warning shown when models not cached with suggestion
- AC3: Cache directory status displayed (exists/empty/not_created)
- AC4: ML Models section integrated into doctor output
- AC5: Doctor command works outside Nest project

✅ **Implementation Summary:**
- Added `ModelStatus` and `ModelReport` dataclasses to `doctor_service.py`
- Created `ModelCheckerProtocol` in `adapters/protocols.py` for dependency injection
- Extended `DoctorService` with `check_ml_models()` method
- Added `get_cache_size()` and `get_cache_status()` methods to `DoclingModelDownloader`
- Registered doctor command in CLI main app
- Extended doctor display with model validation output
- Added `format_size()` helper for human-readable size formatting
- All unit, integration, and E2E tests passing (324 tests total)
- Zero linting or type errors

✅ **Testing Coverage:**
- 6 unit tests for DoctorService model validation
- 7 unit tests for DoclingModelDownloader cache methods
- 9 unit tests for doctor display formatting
- 4 E2E tests for doctor command with model validation
- All existing tests still passing (no regressions)

### File List

#### Modified Files
- `src/nest/services/doctor_service.py` - Added ModelStatus, ModelReport, check_ml_models(), imports ModelCheckerProtocol
- `src/nest/adapters/docling_downloader.py` - Added get_cache_size(), get_cache_status()
- `src/nest/adapters/protocols.py` - Added ModelCheckerProtocol
- `src/nest/cli/doctor_cmd.py` - Injected DoclingModelDownloader, called check_ml_models()
- `src/nest/cli/main.py` - Registered doctor command
- `src/nest/ui/doctor_display.py` - Added display_model_report(), format_size()
- `tests/services/test_doctor_service.py` - Added TestModelValidation class with 6 tests
- `tests/adapters/test_docling_downloader.py` - Added TestGetCacheSize and TestGetCacheStatus classes
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - Updated story status
- `_bmad-output/implementation-artifacts/3-3-ml-model-validation.md` - Story file updates
- `.github/agents/nest.agent.md` - Deleted (leftover test fixture)

#### New Files
- `tests/ui/test_doctor_display.py` - Created with 9 tests for display functionality
- `tests/e2e/test_doctor_e2e.py` - Created with 4 E2E tests for doctor command

### Change Log

**Date:** 2026-02-06

**Changes:**
- Implemented ML model validation for `nest doctor` command
- Extended DoctorService with model checking capability via ModelCheckerProtocol
- Enhanced doctor display to show model cache status, size, and path
- Added comprehensive test coverage for model validation
- Registered doctor command in CLI main app

### Status

done

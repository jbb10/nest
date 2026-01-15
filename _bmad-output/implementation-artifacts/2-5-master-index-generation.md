# Story 2.5: Master Index Generation

Status: review
Branch: feat/2-5-master-index-generation

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

**As a** user querying `@nest`,
**I want** an up-to-date index of all processed files,
**So that** the AI agent knows what documents are available.

## Acceptance Criteria

### AC1: Index Creation
**Given** sync completes processing
**When** index generation runs
**Then** `processed_context/00_MASTER_INDEX.md` is created/updated

### AC2: Index Format
**Given** 47 files are processed
**When** index is generated
**Then** format is:
```markdown
# Nest Project Index: {Project Name}
Generated: {ISO Timestamp} | Files: {Count}

## File Listing
contracts/2024/alpha.md
contracts/2024/beta.md
reports/Q3_summary.md
...
```
**And** one file per line (token-efficient)
**And** paths are relative to `processed_context/`

### AC3: Index Accuracy
**Given** files are removed from `processed_context/`
**When** index regenerates
**Then** removed files no longer appear in index

## Tasks / Subtasks

- [x] **Task 1: Create IndexService**
  - [x] 1.1 Create `src/nest/services/index_service.py`
  - [x] 1.2 Implement `IndexService` class with constructor taking `FileSystemProtocol` and `Project Root` (or just output directory config).
  - [x] 1.3 Implement `generate_content(files: list[str], project_name: str) -> str`
    - Generate header with timestamp and count
    - Sort files alphabetically
    - Create formatted string
  - [x] 1.4 Implement `write_index(content: str) -> None`
    - Target: `processed_context/00_MASTER_INDEX.md`

- [x] **Task 2: Integrate with Sync Flow**
  - [x] 2.1 Update `SyncService` to inject `IndexService`.
  - [x] 2.2 In `SyncService.sync()`, use the final Manifest state to derive the list of files.
    - Filter `manifest.files` for entries where `status="success"`.
    - Extract `output` path from each entry.
  - [x] 2.3 Call `IndexService.update_index(file_list, project_name)` at end of sync.

- [x] **Task 3: Testing**
  - [x] 3.1 Unit tests for `IndexService` (content generation format, file writing).
  - [x] 3.2 Integration tests: Run sync, check `00_MASTER_INDEX.md` content exists and matches format.

## Dev Notes

- **Source of Truth**: The `Manifest` records all successfully processed files. Use `manifest.files` (where status="success") to generate the list.
- **Paths**: The `Manifest` stores `output` paths relative to `processed_context`. These are exactly what we need for the index.
- **Sorting**: Ensure the file list is sorted alphabetically for deterministic output.
- **Timestamps**: Use `datetime.now(timezone.utc)` for the "Generated" timestamp.
- **Dependencies**: `IndexService` should likely accept a list of strings (paths) rather than coupling deeply to `Manifest` object, to allow easier testing and reuse. `SyncService` can bridge the gap.
- **Implementation Update**: `SyncService` was created as it did not exist. `ManifestService` was updated to expose current state via `load_current_manifest`.

### Project Structure Notes

- `src/nest/services/index_service.py` is the new component.
- `src/nest/services/sync_service.py` is the new orchestrator.

### References

- Architecture: "FR10: nest sync regenerates 00_MASTER_INDEX.md"
- Epics: Story 2.5 acceptance criteria.

## Dev Agent Record

### Agent Model Used

Gemini 3 Pro (Preview)

### Debug Log References

- Encountered Pydantic validation errors in test setup (missing fields in mocked models).
- Encountered FileNotFoundError in integration test when mock processor failed to create directories (fixed by adding mkdir to mock).

### Completion Notes List

- Designed IndexService to retain DRY and Single Responsibility principles.
- Created `SyncService` to orchestrate discovery, processing, manifest, and index updates.
- Updated `ManifestService` to allow loading current manifest state for index generation.
- Implemented comprehensive integration test for the full sync flow.

### File List

- src/nest/services/index_service.py
- src/nest/services/sync_service.py
- src/nest/services/manifest_service.py
- tests/services/test_index_service.py
- tests/services/test_sync_service.py
- tests/integration/test_sync_index_integration.py

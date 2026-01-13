---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - prd.md
  - _bmad-output/planning-artifacts/architecture.md
status: complete
---

# Nest - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Nest, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

**FR1:** `nest init "Client Name"` creates project structure with `raw_inbox/`, `processed_context/` directories
**FR2:** `nest init` creates `.github/agents/nest.agent.md` in VS Code Custom Agent format (frontmatter + instructions)
**FR3:** `nest init` creates empty `.nest_manifest.json` manifest file
**FR4:** `nest init` downloads Docling ML models (~1.5-2GB) if not already cached, with progress display
**FR5:** `nest sync` recursively scans `raw_inbox/` for supported files (.pdf, .docx, .pptx, .xlsx, .html)
**FR6:** `nest sync` computes SHA-256 checksums and compares against manifest to detect new/modified/unchanged files
**FR7:** `nest sync` processes documents via Docling to convert to Markdown
**FR8:** `nest sync` mirrors source folder hierarchy in `processed_context/` output
**FR9:** `nest sync` removes orphaned files from `processed_context/` when source is deleted (default behavior, disable with `--no-clean`)
**FR10:** `nest sync` regenerates `00_MASTER_INDEX.md` with file listing
**FR11:** `nest sync` updates `.nest_manifest.json` with processed file metadata
**FR12:** `nest sync` supports `--on-error` flag (skip | fail) for error handling behavior
**FR13:** `nest sync` supports `--dry-run` flag to preview changes without executing
**FR14:** `nest sync` supports `--force` flag to re-process all files ignoring checksums
**FR15:** `nest update` runs self-update via uv
**FR16:** `nest update` checks if local agent template is outdated and prompts for update
**FR17:** `nest update` displays available versions and allows selection (upgrade or downgrade)
**FR18:** `nest status` displays project state: file counts (new, modified, unchanged, orphaned), last sync time
**FR19:** `nest doctor` validates environment (Python version, uv, Nest version)
**FR20:** `nest doctor` validates ML models (cached status, size)
**FR21:** `nest doctor` validates project state (manifest integrity, agent file presence, folder structure)
**FR22:** `nest doctor` offers remediation for detected issues (download models, rebuild manifest, regenerate agent file)

### Non-Functional Requirements

**NFR1:** Privacy — All document processing runs locally via Docling (no cloud APIs)
**NFR2:** Performance — Incremental sync via SHA-256 checksums; skip unchanged files
**NFR3:** Reliability — Error logging to `.nest_errors.log` with configurable fail modes
**NFR4:** Portability — Cross-platform support (macOS/Linux/Windows) via Python 3.10+
**NFR5:** Maintainability — DRY principle: shared components across commands (download_models, build_manifest, generate_agent_file, compute_checksum, generate_index)
**NFR6:** Testability — Dependency injection pattern; all external dependencies injectable via protocols
**NFR7:** Extensibility — Agent generation behind protocol interface to support future platforms (Cursor, etc.)
**NFR8:** UX — Rich terminal output with progress bars, color-coded status, contextual help
**NFR9:** Type Safety — Pyright strict mode enforcement across codebase
**NFR10:** Code Quality — Ruff linting/formatting, conventional commits required

### Additional Requirements

**From Architecture — Project Structure:**
- Use `src/nest/` layout (src layout for distributed tools)
- Layered architecture: cli/ → services/ → core/ + adapters/ + agents/ + ui/
- Protocol-based dependency injection via `adapters/protocols.py`

**From Architecture — Tooling:**
- Package manager: uv (required by PRD)
- Testing: pytest with coverage
- Type checking: Pyright (strict mode)
- Linting/Formatting: Ruff
- CI: Azure Pipelines with matrix testing (Python 3.10, 3.11, 3.12)

**From Architecture — CI/CD:**
- Script-based CI: `scripts/ci-lint.sh`, `ci-typecheck.sh`, `ci-test.sh`, `ci-integration.sh`
- Local release via `scripts/release.sh` with human gate
- git-cliff for changelog generation
- Trunk-based branching with release tags

**From Architecture — Configuration:**
- User config at `~/.config/nest/config.toml` (install source, version)
- Project manifest as `.nest_manifest.json` (files, checksums, timestamps)
- Pydantic models for both config and manifest

**From Architecture — Error Handling:**
- Custom exception hierarchy: `NestError`, `ProcessingError`, `ManifestError`, `ConfigError`, `ModelError`
- Result types for batch operations: `ProcessingResult`, `SyncResult`
- Two output streams: Rich console (user-facing) + logging (`.nest_errors.log`)

**From Architecture — Agent Generation:**
- AgentWriter protocol for extensibility
- VS Code writer with Jinja template (`vscode.md.jinja`)
- Template stored in `src/nest/agents/templates/`

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 1 | Create directories (raw_inbox/, processed_context/) |
| FR2 | Epic 1 | Create VS Code agent file |
| FR3 | Epic 1 | Create empty manifest |
| FR4 | Epic 1 | Download Docling ML models |
| FR5 | Epic 2 | Scan raw_inbox/ for supported files |
| FR6 | Epic 2 | SHA-256 checksum comparison |
| FR7 | Epic 2 | Docling conversion to Markdown |
| FR8 | Epic 2 | Mirror folder hierarchy in output |
| FR9 | Epic 2 | Orphan cleanup (--no-clean flag) |
| FR10 | Epic 2 | Regenerate 00_MASTER_INDEX.md |
| FR11 | Epic 2 | Update manifest with file metadata |
| FR12 | Epic 2 | --on-error flag (skip/fail) |
| FR13 | Epic 2 | --dry-run flag |
| FR14 | Epic 2 | --force flag |
| FR15 | Epic 4 | Self-update via uv |
| FR16 | Epic 4 | Agent template migration |
| FR17 | Epic 4 | Version selection display |
| FR18 | Epic 3 | Status display (file counts, last sync) |
| FR19 | Epic 3 | Doctor: environment validation |
| FR20 | Epic 3 | Doctor: ML model validation |
| FR21 | Epic 3 | Doctor: project state validation |
| FR22 | Epic 3 | Doctor: issue remediation |

## Epic List

### Epic 1: Project Initialization
As a consultant starting a new client project, I can run a single command to create a smart, AI-ready folder structure so I'm immediately set up to start adding documents.

**FRs covered:** FR1, FR2, FR3, FR4

**Scope:**
- Creates `raw_inbox/`, `processed_context/` directories
- Creates VS Code agent file (`.github/agents/nest.agent.md`)
- Creates empty manifest (`.nest_manifest.json`)
- Downloads ML models on first run with progress display

---

### Epic 2: Document Processing & Sync
As a user with client documents, I can drop them into a folder and have them automatically converted into AI-readable Markdown, so my Copilot agent can understand them.

**FRs covered:** FR5, FR6, FR7, FR8, FR9, FR10, FR11, FR12, FR13, FR14

**Scope:**
- Scans for supported files (.pdf, .docx, .pptx, .xlsx, .html)
- Checksum-based change detection (new/modified/unchanged)
- Docling conversion to Markdown
- Directory mirroring in output
- Orphan cleanup (configurable)
- Index regeneration (00_MASTER_INDEX.md)
- Manifest updates
- All sync flags (--on-error, --dry-run, --force, --no-clean)

---

### Epic 3: Project Visibility & Health
As a user managing my knowledge base, I can quickly see the state of my project and verify everything is working correctly, so I know what needs attention.

**FRs covered:** FR18, FR19, FR20, FR21, FR22

**Scope:**
- `nest status` — file counts, pending work, last sync time
- `nest doctor` — environment validation (Python, uv, Nest version)
- `nest doctor` — ML model validation (cached status, size)
- `nest doctor` — project validation (manifest, agent file, folders)
- `nest doctor` — issue remediation offers

---

### Epic 4: Tool Updates & Maintenance
As a user, I can keep my Nest installation up-to-date and ensure my agent templates stay current, so I always have the latest features and fixes.

**FRs covered:** FR15, FR16, FR17

**Scope:**
- Self-update via uv
- Agent template migration prompts
- Version selection (upgrade/downgrade)

---

## Epic 1: Project Initialization

As a consultant starting a new client project, I can run a single command to create a smart, AI-ready folder structure so I'm immediately set up to start adding documents.

### Story 1.1: Project Scaffolding

**As a** consultant starting a new project,
**I want** to run `nest init "Client Name"` and have the basic folder structure created,
**So that** I have a properly organized workspace ready for documents.

**Acceptance Criteria:**

**Given** I am in an empty directory
**When** I run `nest init "Nike"`
**Then** the following directories are created:
- `raw_inbox/`
- `processed_context/`
- `.github/agents/`
**And** a `.nest_manifest.json` file is created with:
```json
{
  "nest_version": "1.0.0",
  "project_name": "Nike",
  "last_sync": null,
  "files": {}
}
```
**And** the manifest uses the Pydantic `Manifest` model for validation

**Given** a `.gitignore` file exists in the directory
**When** I run `nest init "Nike"`
**Then** `raw_inbox/` is appended to `.gitignore` if not already present
**And** a comment explaining why is included

**Given** a `.gitignore` file does NOT exist
**When** I run `nest init "Nike"`
**Then** a new `.gitignore` is created with `raw_inbox/` entry

**Given** I run `nest init` without a project name
**When** the command executes
**Then** an error is displayed: "Project name required. Usage: nest init 'Client Name'"

**Given** I run `nest init` in a directory that already has `.nest_manifest.json`
**When** the command executes
**Then** an error is displayed: "Nest project already exists. Use `nest sync` to process documents."

---

### Story 1.2: VS Code Agent File Generation

**As a** consultant,
**I want** the `@nest` agent to be automatically created during init,
**So that** I can immediately use it in VS Code Copilot Chat.

**Acceptance Criteria:**

**Given** I run `nest init "Nike"`
**When** project scaffolding completes
**Then** `.github/agents/nest.agent.md` is created
**And** the file uses VS Code Custom Agent format with frontmatter:
```yaml
---
name: nest
description: Expert analyst for Nike project documents
icon: book
---
```
**And** the file includes instructions for:
- Reading `processed_context/00_MASTER_INDEX.md` first
- Citing sources with filenames
- Never reading `raw_inbox/` or system files
- Honest "I cannot find that" responses

**Given** the AgentWriter protocol is implemented
**When** VSCodeAgentWriter is instantiated
**Then** it renders the agent file from `vscode.md.jinja` template
**And** the project name is interpolated into the template

**Given** `.github/agents/` directory doesn't exist
**When** agent file generation runs
**Then** the directory is created automatically

---

### Story 1.3: ML Model Download & Caching

**As a** first-time user,
**I want** Docling ML models to be downloaded automatically with progress feedback,
**So that** I don't have to manually configure anything.

**Acceptance Criteria:**

**Given** Docling models are NOT cached at `~/.cache/docling/`
**When** I run `nest init "Nike"`
**Then** models are downloaded with Rich progress bars showing:
- Model name (TableFormer, LayoutLM)
- Download size
- Progress percentage
**And** console shows: "Downloading ML models (first-time setup)..."
**And** on completion: "Models cached at ~/.cache/docling/"

**Given** Docling models ARE already cached
**When** I run `nest init "Nike"`
**Then** no download occurs
**And** console shows: "ML models already cached ✓"
**And** init completes in seconds

**Given** network timeout occurs during model download
**When** 3 retry attempts fail
**Then** a `ModelError` exception is raised
**And** error message explains: "Failed to download models. Check your internet connection and try again."
**And** partial downloads are cleaned up

**Given** disk space is insufficient for models
**When** download is attempted
**Then** a clear error is shown before download starts (if detectable)
**Or** error is handled gracefully with cleanup

---

### Story 1.4: Init Command CLI Integration

**As a** user,
**I want** `nest init` to provide clear feedback and next-step guidance,
**So that** I know exactly what to do after initialization.

**Acceptance Criteria:**

**Given** I successfully run `nest init "Nike"`
**When** all steps complete
**Then** the console displays:
```
✓ Project "Nike" initialized!

Next steps:
  1. Drop your documents into raw_inbox/
  2. Run `nest sync` to process them
  3. Open VS Code and use @nest in Copilot Chat

Supported formats: PDF, DOCX, PPTX, XLSX, HTML
```

**Given** the init command runs
**When** each step executes
**Then** Rich spinners/checkmarks show progress:
- `[•] Creating project structure... ✓`
- `[•] Generating agent file... ✓`
- `[•] Checking ML models...` (then download or cached message)

**Given** the CLI layer (`init_cmd.py`)
**When** it creates the InitService
**Then** it injects: FileSystemAdapter, VSCodeAgentWriter, ManifestAdapter, DoclingProcessor
**And** follows the composition root pattern from Architecture

**Given** any step fails
**When** error is caught
**Then** appropriate error message is shown (What → Why → Action format)
**And** cleanup is performed for partial state

---

## Epic 2: Document Processing & Sync

As a user with client documents, I can drop them into a folder and have them automatically converted into AI-readable Markdown, so my Copilot agent can understand them.

### Story 2.1: File Discovery & Checksum Engine

**As a** user with documents in `raw_inbox/`,
**I want** the system to detect which files are new, modified, or unchanged,
**So that** only necessary files are processed, saving time.

**Acceptance Criteria:**

**Given** `raw_inbox/` contains files (.pdf, .docx, .pptx, .xlsx, .html)
**When** sync runs file discovery
**Then** all supported files are found recursively (including subdirectories)
**And** unsupported file types are ignored

**Given** a file exists in `raw_inbox/` but NOT in manifest
**When** checksum comparison runs
**Then** the file is marked as "new" for processing

**Given** a file exists in both `raw_inbox/` and manifest
**When** the SHA-256 checksum differs from manifest
**Then** the file is marked as "modified" for processing

**Given** a file exists in both `raw_inbox/` and manifest
**When** the SHA-256 checksum matches manifest
**Then** the file is marked as "unchanged" and skipped

**Given** checksum computation
**When** `core/checksum.py` processes a file
**Then** it reads in chunks to handle large files efficiently
**And** returns hex-encoded SHA-256 hash string

---

### Story 2.2: Docling Document Processing

**As a** user,
**I want** my documents converted to clean Markdown,
**So that** my AI agent can read and understand them.

**Acceptance Criteria:**

**Given** a PDF file with text and tables
**When** DoclingProcessor processes it
**Then** text is extracted cleanly
**And** tables are converted to Markdown table format (TableFormer mode enabled)

**Given** a DOCX file
**When** DoclingProcessor processes it
**Then** content is converted to Markdown preserving structure

**Given** a PPTX file
**When** DoclingProcessor processes it
**Then** slide content is extracted as Markdown

**Given** an XLSX file with tabular data
**When** DoclingProcessor processes it
**Then** data is converted to Markdown tables

**Given** an HTML file
**When** DoclingProcessor processes it
**Then** content is converted to clean Markdown

**Given** a password-protected PDF
**When** processing is attempted
**Then** a `ProcessingError` is raised with clear message
**And** the file is logged to `.nest_errors.log`

**Given** a corrupt or unparseable file
**When** processing fails
**Then** error is captured in `ProcessingResult` with status "failed"
**And** processing continues to next file (default behavior)

---

### Story 2.3: Output Mirroring & File Writing

**As a** user,
**I want** processed files to maintain the same folder structure as my source,
**So that** I can easily find the Markdown version of any document.

**Acceptance Criteria:**

**Given** source file at `raw_inbox/contracts/2024/alpha.pdf`
**When** processing completes
**Then** output is written to `processed_context/contracts/2024/alpha.md`

**Given** nested directory structure in `raw_inbox/`
**When** output directories don't exist in `processed_context/`
**Then** they are created automatically

**Given** a file was previously processed and source is modified
**When** re-processing completes
**Then** the existing output file is overwritten with new content

**Given** FileSystemAdapter
**When** writing output files
**Then** it uses `pathlib.Path` for all operations
**And** stores relative paths in manifest for portability

---

### Story 2.4: Manifest Tracking & Updates

**As a** user,
**I want** the system to remember what was processed,
**So that** subsequent syncs are fast and only process changes.

**Acceptance Criteria:**

**Given** a file is successfully processed
**When** manifest is updated
**Then** entry includes:
- `sha256`: file checksum
- `processed_at`: ISO timestamp
- `output`: relative path to processed file
- `status`: "success"

**Given** a file fails processing
**When** manifest is updated
**Then** entry includes `status`: "failed" with error info

**Given** sync completes
**When** manifest is saved
**Then** `last_sync` timestamp is updated
**And** `nest_version` reflects current version

**Given** manifest file is corrupt or invalid JSON
**When** sync attempts to load it
**Then** a `ManifestError` is raised
**And** user is advised to run `nest doctor`

---

### Story 2.5: Master Index Generation

**As a** user querying `@nest`,
**I want** an up-to-date index of all processed files,
**So that** the AI agent knows what documents are available.

**Acceptance Criteria:**

**Given** sync completes processing
**When** index generation runs
**Then** `processed_context/00_MASTER_INDEX.md` is created/updated

**Given** 47 files are processed
**When** index is generated
**Then** format is:
```markdown
# Nest Project Index: Nike
Generated: 2026-01-12T14:30:00Z | Files: 47

## File Listing
contracts/2024/alpha.md
contracts/2024/beta.md
reports/Q3_summary.md
...
```
**And** one file per line (token-efficient)
**And** paths are relative to `processed_context/`

**Given** files are removed from `processed_context/`
**When** index regenerates
**Then** removed files no longer appear in index

---

### Story 2.6: Orphan Cleanup

**As a** user,
**I want** outdated processed files removed when I delete sources,
**So that** my knowledge base stays in sync with my actual documents.

**Acceptance Criteria:**

**Given** `processed_context/old_report.md` exists
**When** `raw_inbox/old_report.pdf` is deleted and sync runs
**Then** `processed_context/old_report.md` is automatically removed
**And** the file is removed from manifest

**Given** sync runs with `--no-clean` flag
**When** orphan files are detected
**Then** orphan files are NOT removed
**And** they remain in `processed_context/`

**Given** orphan cleanup removes files
**When** sync summary is displayed
**Then** count of removed orphans is shown

---

### Story 2.7: Sync Command Flags & Error Handling

**As a** user,
**I want** control over sync behavior,
**So that** I can handle errors and preview changes as needed.

**Acceptance Criteria:**

**Given** `--on-error=skip` (default)
**When** a file fails processing
**Then** error is logged, file is skipped, sync continues
**And** exit code is 0 if any files succeeded

**Given** `--on-error=fail`
**When** a file fails processing
**Then** sync aborts immediately
**And** exit code is 1

**Given** `--dry-run` flag
**When** sync runs
**Then** files are analyzed but NOT processed
**And** output shows what WOULD be processed:
- "Would process: 12 new, 3 modified"
- "Would skip: 32 unchanged"
- "Would remove: 2 orphans"

**Given** `--force` flag
**When** sync runs
**Then** all files are re-processed regardless of checksum
**And** manifest checksums are ignored

**Given** any errors occur during sync
**When** error logging runs
**Then** errors are appended to `.nest_errors.log` with format:
`2026-01-12T10:30:00 ERROR [sync] file.pdf: Error description`

---

### Story 2.8: Sync Command CLI Integration

**As a** user,
**I want** clear visual feedback during sync,
**So that** I know what's happening with my documents.

**Acceptance Criteria:**

**Given** sync processes multiple files
**When** Rich progress displays
**Then** a progress bar shows:
- Current file being processed
- Progress: `[████████████--------] 60%`
- Count: `Processing 30/50 files`

**Given** sync completes
**When** summary is displayed
**Then** output shows:
```
✓ Sync complete

  Processed: 15 files
  Skipped:   32 unchanged
  Failed:    2 (see .nest_errors.log)
  Orphans:   3 removed

  Index updated: 00_MASTER_INDEX.md
```

**Given** sync runs outside a Nest project (no manifest)
**When** command executes
**Then** error displays: "No Nest project found. Run `nest init` first."

**Given** CLI layer (`sync_cmd.py`)
**When** it creates SyncService
**Then** it injects: FileSystemAdapter, DoclingProcessor, ManifestAdapter
**And** passes flag values (on_error, dry_run, force, no_clean)

---

## Epic 3: Project Visibility & Health

As a user managing my knowledge base, I can quickly see the state of my project and verify everything is working correctly, so I know what needs attention.

### Story 3.1: Project Status Display

**As a** user managing my knowledge base,
**I want** to quickly see the state of my project,
**So that** I know what needs attention before running sync.

**Acceptance Criteria:**

**Given** I run `nest status` in a Nest project
**When** the command executes
**Then** output displays:
```
📁 Project: Nike
   Nest Version: 1.0.0

   Raw Inbox:
   ├─ Total files:    47
   ├─ New:            12  (not yet processed)
   ├─ Modified:        3  (source changed since last sync)
   └─ Unchanged:      32

   Processed Context:
   ├─ Files:          32
   ├─ Orphaned:        2  (source deleted, run sync to remove)
   └─ Last sync:       2 hours ago

   Run `nest sync` to process 15 pending files.
```

**Given** no files need processing
**When** status displays
**Then** message shows: "✓ All files up to date"

**Given** manifest has `last_sync` timestamp
**When** status displays
**Then** relative time is shown (e.g., "2 hours ago", "3 days ago")

**Given** `nest status` runs outside a Nest project
**When** command executes
**Then** error displays: "No Nest project found. Run `nest init` first."

**Given** StatusService
**When** computing file states
**Then** it reuses checksum logic from `core/checksum.py`
**And** compares against manifest entries

---

### Story 3.2: Environment Validation

**As a** user,
**I want** to verify my environment is correctly configured,
**So that** I can troubleshoot issues before they cause sync failures.

**Acceptance Criteria:**

**Given** I run `nest doctor`
**When** environment validation runs
**Then** output shows:
```
🩺 Nest Doctor

   Environment:
   ├─ Python:         3.11.4 ✓
   ├─ uv:             0.4.12 ✓
   └─ Nest:           1.0.0 ✓
```

**Given** Python version is below 3.10
**When** validation runs
**Then** warning shows: `Python: 3.9.1 ✗ (requires 3.10+)`

**Given** uv is not installed or not in PATH
**When** validation runs
**Then** warning shows: `uv: not found ✗`
**And** suggestion: "Install uv: https://docs.astral.sh/uv/"

**Given** Nest version is outdated compared to latest
**When** validation runs
**Then** info shows: `Nest: 1.0.0 (1.2.0 available)`
**And** suggestion: "Run `nest update` to upgrade"

---

### Story 3.3: ML Model Validation

**As a** user,
**I want** to verify Docling models are properly cached,
**So that** sync will work without download delays.

**Acceptance Criteria:**

**Given** I run `nest doctor`
**When** ML model validation runs
**Then** output shows:
```
   ML Models:
   ├─ TableFormer:    cached ✓ (892MB)
   ├─ LayoutLM:       cached ✓ (645MB)
   └─ Cache path:     ~/.cache/docling/
```

**Given** models are NOT cached
**When** validation runs
**Then** warning shows: `TableFormer: not found ✗`
**And** offers: "Download models? [y/N]"

**Given** model files exist but checksums don't match expected
**When** validation runs
**Then** warning shows: `TableFormer: checksum mismatch ⚠`
**And** logged to `.nest_errors.log`

**Given** cache directory doesn't exist
**When** validation runs
**Then** shows: `Cache path: ~/.cache/docling/ (not created)`

---

### Story 3.4: Project State Validation

**As a** user,
**I want** to verify my project structure is intact,
**So that** I know sync and agent will work correctly.

**Acceptance Criteria:**

**Given** I run `nest doctor` in a Nest project
**When** project validation runs
**Then** output shows:
```
   Project:
   ├─ Manifest:       valid ✓
   ├─ Agent file:     present ✓
   └─ Folders:        intact ✓
```

**Given** `.nest_manifest.json` is missing
**When** validation runs
**Then** error shows: `Manifest: missing ✗`

**Given** manifest JSON is corrupt or invalid
**When** validation runs
**Then** error shows: `Manifest: invalid JSON ✗`

**Given** `.github/agents/nest.agent.md` is missing
**When** validation runs
**Then** warning shows: `Agent file: missing ✗`

**Given** `raw_inbox/` or `processed_context/` directories are missing
**When** validation runs
**Then** warning shows: `Folders: raw_inbox/ missing ✗`

**Given** manifest version doesn't match current Nest version
**When** validation runs
**Then** info shows: `Manifest: v0.9.0 (migration available)`

---

### Story 3.5: Issue Remediation

**As a** user with detected issues,
**I want** doctor to offer to fix them,
**So that** I don't have to manually troubleshoot.

**Acceptance Criteria:**

**Given** ML models are missing
**When** doctor completes validation
**Then** prompt offers: "Download missing models? [y/N]"
**And** if Y: triggers model download with progress

**Given** manifest is missing or corrupt
**When** doctor completes validation
**Then** prompt offers: "Rebuild manifest from processed files? [y/N]"
**And** if Y: scans `processed_context/` and rebuilds manifest

**Given** agent file is missing
**When** doctor completes validation
**Then** prompt offers: "Regenerate agent file? [y/N]"
**And** if Y: regenerates using AgentWriter with project name from manifest

**Given** multiple issues are detected
**When** remediation prompts
**Then** each fix is offered separately
**And** user can accept/decline each one

**Given** all checks pass
**When** doctor completes
**Then** output shows: `✓ All systems operational.`

---

### Story 3.6: Doctor Command CLI Integration

**As a** user,
**I want** doctor output to be clear and actionable,
**So that** I can quickly understand and fix any issues.

**Acceptance Criteria:**

**Given** `nest doctor` runs
**When** all validations complete
**Then** Rich-formatted output uses:
- ✓ green for passing checks
- ✗ red for failures
- ⚠ yellow for warnings
- Hierarchical tree structure (├─, └─)

**Given** DoctorService
**When** CLI creates it
**Then** it injects: FileSystemAdapter, UserConfigAdapter, DoclingProcessor

**Given** issues are detected
**When** summary displays
**Then** format shows:
```
   ⚠ 2 issues found:
   1. ML models not cached
   2. Agent file missing

   Run with --fix to attempt automatic repair.
```

**Given** `--fix` flag is provided
**When** issues are detected
**Then** remediation runs automatically without prompts
**And** results are displayed for each fix attempted

---

## Epic 4: Tool Updates & Maintenance

As a user, I can keep my Nest installation up-to-date and ensure my agent templates stay current, so I always have the latest features and fixes.

### Story 4.1: User Config Management

**As a** user,
**I want** Nest to remember where it was installed from,
**So that** I never have to re-enter the git URL for updates.

**Acceptance Criteria:**

**Given** first run of any `nest` command
**When** user config doesn't exist
**Then** `~/.config/nest/config.toml` is created with:
```toml
[install]
source = "git+https://dev.azure.com/org/project/_git/nest"
installed_version = "1.0.0"
installed_at = "2026-01-12T10:30:00Z"
```

**Given** user config exists
**When** `nest update` runs successfully
**Then** `installed_version` and `installed_at` are updated

**Given** UserConfigAdapter
**When** loading config
**Then** it uses Pydantic `UserConfig` model for validation
**And** returns `None` if file doesn't exist (not an error)

**Given** config file is corrupt or invalid TOML
**When** loading fails
**Then** a `ConfigError` is raised with clear message
**And** suggests deleting and re-running any nest command

**Given** `~/.config/nest/` directory doesn't exist
**When** saving config
**Then** directory is created automatically

---

### Story 4.2: Version Discovery & Comparison

**As a** user,
**I want** to see what versions are available,
**So that** I can decide whether to update.

**Acceptance Criteria:**

**Given** `nest update` runs
**When** GitClient queries remote
**Then** it executes `git ls-remote --tags <source>`
**And** parses tags matching `v*` pattern (e.g., v1.0.0, v1.2.1)

**Given** tags are retrieved
**When** version parsing runs
**Then** `core/version.py` extracts semver components
**And** sorts versions newest-first

**Given** current version is 1.2.0
**When** available versions are 1.4.0, 1.3.1, 1.3.0, 1.2.1, 1.2.0, 1.1.0
**Then** versions are displayed with current marked:
```
  Available versions:
    • 1.4.0 (latest)
    • 1.3.1
    • 1.3.0
    • 1.2.1
    • 1.2.0 (installed)
    • 1.1.0
```

**Given** network is unavailable
**When** GitClient fails to query remote
**Then** error shows: "Cannot reach update server. Check your internet connection."

**Given** no tags are found
**When** version discovery completes
**Then** info shows: "No releases found. You may be on a development version."

---

### Story 4.3: Interactive Version Selection

**As a** user,
**I want** to choose which version to install,
**So that** I can upgrade or downgrade as needed.

**Acceptance Criteria:**

**Given** `nest update` displays versions
**When** user prompt appears
**Then** format shows:
```
$ nest update

  Current version: 1.2.0
  Latest version:  1.4.0

  Update to 1.4.0? [Y/n/version]:
```

**Given** user enters `Y` or presses Enter
**When** update proceeds
**Then** `uv tool install --force <source>@v1.4.0` executes
**And** progress is displayed

**Given** user enters `n`
**When** response is received
**Then** update is cancelled with message: "Update cancelled."

**Given** user enters a specific version (e.g., `1.3.1`)
**When** version is valid
**Then** `uv tool install --force <source>@v1.3.1` executes

**Given** user enters an invalid version
**When** version is not in available list
**Then** error shows: "Version 1.9.9 not found. Available: 1.4.0, 1.3.1, ..."

**Given** update completes successfully
**When** config is updated
**Then** message shows:
```
✓ Updated to version 1.4.0

  What's new: https://dev.azure.com/.../CHANGELOG.md
```

---

### Story 4.4: Agent Template Migration Check

**As a** user,
**I want** to know if my agent file is outdated,
**So that** I get the latest agent instructions.

**Acceptance Criteria:**

**Given** `nest update` completes version update
**When** agent template check runs
**Then** local `.github/agents/nest.agent.md` is compared against bundled template

**Given** local agent file differs from current template
**When** comparison completes
**Then** prompt shows: "Agent template has changed. Update? [y/N]"

**Given** user confirms agent update
**When** regeneration runs
**Then** AgentWriter regenerates the file with current project name
**And** old file is backed up as `nest.agent.md.bak`

**Given** user declines agent update
**When** response is received
**Then** message shows: "Keeping existing agent file. Run `nest doctor` to update later."

**Given** local agent file matches current template
**When** comparison completes
**Then** no prompt is shown
**And** message shows: "Agent file is up to date ✓"

**Given** project is not a Nest project (no manifest)
**When** agent check runs
**Then** check is skipped (only version update happens)

---

### Story 4.5: Update Command CLI Integration

**As a** user,
**I want** the update process to be clear and safe,
**So that** I'm confident in updating my tool.

**Acceptance Criteria:**

**Given** `nest update` runs
**When** UpdateService is created
**Then** CLI injects: GitClientAdapter, UserConfigAdapter

**Given** update is in progress
**When** uv runs
**Then** Rich spinner shows: "Installing version 1.4.0..."

**Given** update fails (uv error)
**When** error is caught
**Then** error message shows what failed and suggests:
```
✗ Update failed
  Reason: uv tool install returned exit code 1
  Action: Check `uv` is working: `uv --version`
```

**Given** user config is missing install source
**When** `nest update` runs
**Then** prompt asks: "Enter installation source URL:"
**And** saves to config for future use

**Given** `--check` flag is provided
**When** update runs
**Then** only version check is performed (no actual update)
**And** output shows current vs latest with exit code 0 if up-to-date, 1 if outdated


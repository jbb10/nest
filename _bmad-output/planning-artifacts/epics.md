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

**FR1:** `nest init "Project Name"` creates project structure with `_nest_sources/`, `_nest_context/` directories
**FR2:** `nest init` creates `.github/agents/nest.agent.md` in VS Code Custom Agent format (frontmatter + instructions)
**FR3:** `nest init` creates empty `.nest/manifest.json` manifest file
**FR4:** `nest init` downloads Docling ML models (~1.5-2GB) if not already cached, with progress display
**FR5:** `nest sync` recursively scans `_nest_sources/` for supported files (.pdf, .docx, .pptx, .xlsx, .html)
**FR6:** `nest sync` computes SHA-256 checksums and compares against manifest to detect new/modified/unchanged files
**FR7:** `nest sync` processes documents via Docling to convert to Markdown
**FR8:** `nest sync` mirrors source folder hierarchy in `_nest_context/` output
**FR9:** `nest sync` removes orphaned files from `_nest_context/` **that are tracked in the manifest** when source is deleted (default behavior, disable with `--no-clean`)
**FR10:** `nest sync` regenerates `00_MASTER_INDEX.md` with file listing from entire `_nest_context/` directory
**FR11:** `nest sync` updates `.nest/manifest.json` with processed file metadata
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
**FR23:** `nest sync` index generation and status counting recognize all supported context text extensions (`.md`, `.txt`, `.text`, `.rst`, `.csv`, `.json`, `.yaml`, `.yml`, `.toml`, `.xml`) for user-curated files in `_nest_context/`
**FR24:** `nest sync` generates `00_INDEX_HINTS.yaml` with deterministic metadata (headings, first paragraph, line count, content hash) for each context file, and uses content hashes to preserve existing index descriptions across syncs when file content is unchanged
**FR25:** `nest sync` produces `00_MASTER_INDEX.md` in Markdown table format (File | Lines | Description) and prompts user to run the `@nest-enricher` agent when files lack descriptions
**FR26:** `nest init` ships a `@nest-glossary` VS Code agent that generates and maintains a `glossary.md` in `_nest_context/` containing project-specific terms, abbreviations, stakeholder names, and domain jargon extracted from project documents; `nest sync` provides deterministic candidate-term hints to support the agent
**FR27:** `nest sync` auto-detects AI configuration from environment variables (`NEST_AI_*` with fallback to `OPENAI_*`) and, when available, automatically generates short descriptions for index entries and populates a project glossary — without requiring any per-project configuration
**FR28:** `nest sync` AI enrichment runs incrementally — only files with changed or missing content hashes trigger LLM calls for descriptions; only new/changed candidate glossary terms trigger LLM calls for definitions
**FR29:** `nest sync` runs AI index enrichment and AI glossary generation in parallel after document processing completes, using threading for I/O-bound LLM calls
**FR30:** `nest sync` reports token usage after sync when AI enrichment was active (prompt tokens, completion tokens), and supports `--no-ai` flag to skip AI enrichment entirely
**FR31:** `nest config ai` command writes AI configuration (`NEST_BASE_URL`, `NEST_TEXT_MODEL`, `NEST_API_KEY`) as `export` statements to the user's shell RC file (`.zshrc`, `.bashrc`, `.bash_profile`, or `.profile`), with idempotent updates via comment-delimited blocks
**FR32:** `nest init` no longer generates `nest-enricher.agent.md` or `nest-glossary.agent.md`; only the primary `nest.agent.md` is generated. The enricher and glossary agent templates are removed from the codebase
**FR33:** AI configuration uses a fallback chain: `NEST_API_KEY` → `OPENAI_API_KEY`, `NEST_BASE_URL` → `OPENAI_BASE_URL` (default: `https://api.openai.com/v1`), `NEST_TEXT_MODEL` → `OPENAI_MODEL` (default: `gpt-4o-mini`). AI is enabled when an API key is found; otherwise sync completes without AI enrichment
**FR34:** `nest sync` uses Docling's local picture classifier to categorize images, then sends classified images to a vision LLM with type-specific prompts: Mermaid for diagrams (flow_chart, block_diagram), prose descriptions for charts and photos, skip for logos and signatures. Descriptions are stored back into Docling's document model via `PictureDescriptionData` and embedded in the exported Markdown automatically
**FR35:** Image description uses a dedicated vision model configured via `NEST_VISION_MODEL` env var (fallback: `OPENAI_VISION_MODEL`, default: `gpt-4.1`), independent of the text enrichment model
**FR36:** Image descriptions within a single document are processed in parallel (up to 50 concurrent LLM calls), and image processing for one document does not block image processing for other documents
**FR37:** When AI is not configured or vision model is unavailable, images produce `[Image: ...]` placeholder markers in the output Markdown (existing behavior preserved)
**FR38:** Image description token usage is included in the sync summary token usage reporting (FR30)
**FR39:** `nest init` takes no positional arguments; the project name concept is removed from the CLI, manifest, agent template, and all display output
**FR40:** `nest sync` suppresses third-party log noise (Docling, httpx, openai) by default, showing only the Rich progress bar and summary. `--verbose` / `-v` flag restores detailed logging for troubleshooting

### Non-Functional Requirements

**NFR1:** Privacy — All document processing runs locally via Docling (no cloud APIs)
**NFR2:** Performance — Incremental sync via SHA-256 checksums; skip unchanged files
**NFR3:** Reliability — Error logging to `.nest/errors.log` with configurable fail modes
**NFR4:** Portability — Cross-platform support (macOS/Linux/Windows) via Python 3.10+, with LF line-ending normalization via `.gitattributes` and `newline='\n'` in Python writes to ensure consistent checksums across platforms
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
- CI: GitHub Actions with matrix testing (Python 3.10, 3.11, 3.12)

**From Architecture — CI/CD:**
- Script-based CI: `scripts/ci-lint.sh`, `ci-typecheck.sh`, `ci-test.sh`, `ci-integration.sh`
- Local release via `scripts/release.sh` with human gate
- git-cliff for changelog generation
- Trunk-based branching with release tags

**From Architecture — Configuration:**
- User config at `~/.config/nest/config.toml` (install source, version)
- Project manifest as `.nest/manifest.json` (files, checksums, timestamps)
- Pydantic models for both config and manifest

**From Architecture — Error Handling:**
- Custom exception hierarchy: `NestError`, `ProcessingError`, `ManifestError`, `ConfigError`, `ModelError`
- Result types for batch operations: `ProcessingResult`, `SyncResult`
- Two output streams: Rich console (user-facing) + logging (`.nest/errors.log`)

**From Architecture — Agent Generation:**
- AgentWriter protocol for extensibility
- VS Code writer with Jinja template (`vscode.md.jinja`)
- Template stored in `src/nest/agents/templates/`

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 1 | Create directories (_nest_sources/, _nest_context/) |
| FR2 | Epic 1 | Create VS Code agent file |
| FR3 | Epic 1 | Create empty manifest |
| FR4 | Epic 1 | Download Docling ML models |
| FR5 | Epic 2 | Scan _nest_sources/ for supported files |
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
| FR23 | Epic 2 | Context text extension support for index/status |
| FR24 | Epic 5 | Metadata extraction and content hash tracking for index enrichment |
| FR25 | Epic 5 | Table-format index with descriptions and enricher agent prompt |
| FR26 | Epic 5 | Glossary agent for project-specific term extraction and curation |
| FR27 | Epic 6 | Auto-detect AI from env vars, enrich index + glossary during sync |
| FR28 | Epic 6 | Incremental AI enrichment using content hashes |
| FR29 | Epic 6 | Parallel AI enrichment + glossary generation |
| FR30 | Epic 6 | Token usage reporting + `--no-ai` flag |
| FR31 | Epic 6 | `nest config ai` writes to shell RC file |
| FR32 | Epic 6 | Remove enricher/glossary agent templates from init and codebase |
| FR33 | Epic 6 | Env var fallback chain for AI configuration |
| FR34 | Epic 7 | Two-pass image classification + description with type-specific prompts |
| FR35 | Epic 7 | Vision model configuration (NEST_VISION_MODEL) |
| FR36 | Epic 7 | Parallel image description (50 concurrent per doc, cross-file) |
| FR37 | Epic 7 | Graceful degradation to placeholders |
| FR38 | Epic 7 | Token usage reporting for image descriptions |
| FR39 | Epic 8 | Remove project name concept from nest init |
| FR40 | Epic 8 | Suppress third-party log noise + --verbose flag |
| FR41 | Epic 10 | Multi-agent template bundle: coordinator + researcher, synthesizer, planner subagents |
| FR42 | Epic 10 | Multi-agent init and validation: all 4 agent files created during init and validated by doctor |
| FR43 | Epic 10 | Multi-agent migration: update checks and migrates all 4 agent files |

## Epic List

### Epic 1: Project Initialization
As a user starting a new project, I can run a single command to create a smart, AI-ready folder structure so I'm immediately set up to start adding documents.

**FRs covered:** FR1, FR2, FR3, FR4

**Scope:**
- Creates `_nest_sources/`, `_nest_context/` directories
- Creates VS Code agent file (`.github/agents/nest.agent.md`)
- Creates empty manifest (`.nest/manifest.json`)
- Downloads ML models on first run with progress display
- Supports both auto-generated and user-curated context files

---

### Epic 2: Document Processing & Sync
As a user with project documents, I can drop them into a folder and have them automatically converted into AI-readable Markdown, so my Copilot agent can understand them.

**FRs covered:** FR5, FR6, FR7, FR8, FR9, FR10, FR11, FR12, FR13, FR14, FR23, NFR11

**Scope:**
- Scans for supported files (.pdf, .docx, .pptx, .xlsx, .html)
- Checksum-based change detection (new/modified/unchanged)
- Docling conversion to Markdown
- Directory mirroring in output
- Orphan cleanup (configurable)
- Index regeneration (00_MASTER_INDEX.md)
- Manifest updates
- All sync flags (--on-error, --dry-run, --force, --no-clean)
- **E2E testing framework for CLI commands (Story 2.9)**

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

### Epic 5: Index Intelligence & Agent Enrichment
As a user who has synced documents, I want the master index to contain short, LLM-generated descriptions per file and a project-specific glossary, so the @nest agent can quickly identify relevant documents and understand project terminology.

**FRs covered:** FR24, FR25, FR26

**Scope:**
- Deterministic metadata extraction (headings, first paragraph, line count) per context file
- Content hash-based incremental tracking via `00_INDEX_HINTS.yaml`
- Index format upgrade to Markdown table with File / Lines / Description columns
- Description carry-forward across syncs when content unchanged
- Enricher agent template shipped with `nest init` for LLM-driven description population
- Sync-time prompt informing user about files needing enrichment
- Glossary hints extraction during `nest sync` (candidate terms: abbreviations, proper nouns, repeated domain terms)
- Glossary agent template (`nest-glossary.agent.md`) shipped with `nest init` for LLM-driven glossary generation
- `glossary.md` output in `_nest_context/` with human-curation-safe merge semantics
- Glossary referenced in master index and available to the `@nest` agent

---

### Epic 6: Built-in AI Enrichment
As a user who syncs documents, I want Nest to automatically generate file descriptions and a project glossary using my existing AI API keys, so that my index is enriched and terminology is catalogued without manual agent invocations.

**FRs covered:** FR27, FR28, FR29, FR30, FR31, FR32, FR33

**Scope:**
- LLM provider adapter with env-var-based configuration (fallback chain: `NEST_AI_*` → `OPENAI_*`)
- Automatic AI detection during sync (no setup ceremony if keys already in environment)
- Built-in index enrichment: generates ≤15-word descriptions using existing metadata hints
- Built-in glossary generation: defines project-specific terms using existing candidate term hints
- Incremental processing: only calls LLM for changed/new files and terms
- Parallel execution of enrichment + glossary via `ThreadPoolExecutor`
- Token usage reporting in sync summary output
- `--no-ai` flag to skip AI enrichment
- `nest config ai` subcommand that writes `export` lines to shell RC file
- Removal of `nest-enricher.agent.md` and `nest-glossary.agent.md` agent templates
- Graceful degradation: no AI config = unenriched index, no glossary, no error

**Dependencies:** Epic 5 (metadata extraction and glossary hints infrastructure)

---

### Epic 7: Image Description via Vision LLM
As a user syncing documents that contain images and diagrams, I want those images automatically described by a vision-capable LLM, so that the @nest agent can understand and reference visual content — not just text.

**FRs covered:** FR34, FR35, FR36, FR37, FR38

**Dependencies:** Epic 2 (DoclingProcessor), Epic 6 (LLM adapter infrastructure)

**Scope:**
- Enable Docling image extraction and local classification (two-pass approach)
- VisionLLMProviderProtocol and vision adapters (OpenAI + Azure) with `complete_with_image()`
- `NEST_VISION_MODEL` env var with fallback chain (default: `gpt-4.1`)
- PictureDescriptionService with parallel processing (ThreadPoolExecutor, max_workers=50)
- Type-specific prompts: Mermaid for diagrams (flow_chart, block_diagram), prose for charts/photos, skip logos/signatures
- Descriptions stored via Docling's `PictureDescriptionData` — `export_to_markdown()` embeds them automatically
- Cross-document parallelism (file A's images don't block file B)
- Graceful degradation to `[Image: ...]` placeholders when AI is not configured
- Vision token usage aggregated into sync summary reporting
- Reference: `docs/docling-picture-description-guide.md`

---

### Epic 8: Developer Experience Polish
As a Nest user, I want the CLI to feel clean and professional, so I can focus on my documents rather than fighting tool friction.

**FRs covered:** FR39, FR40

**Scope:**
- Remove project name concept from `nest init` (no positional arguments)
- Suppress noisy third-party logging (Docling, httpx, openai) by default
- Add `--verbose` / `-v` flag to restore detailed logs for troubleshooting
- Clean console output: progress bar + summary only

**Dependencies:** Epic 2 (sync CLI), Epic 6 (AI enrichment), Epic 7 (vision pipeline)

---

## Epic 1: Project Initialization

As a user starting a new project, I can run a single command to create a smart, AI-ready folder structure so I'm immediately set up to start adding documents.

### Story 1.1: Project Scaffolding

**As a** user starting a new project,
**I want** to run `nest init "Project Name"` and have the basic folder structure created,
**So that** I have a properly organized workspace ready for documents.

**Acceptance Criteria:**

**Given** I am in an empty directory
**When** I run `nest init "Nike"`
**Then** the following directories are created:
- `_nest_sources/`
- `_nest_context/`
- `.github/agents/`
**And** a `.nest/manifest.json` file is created with:
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
**Then** `.nest/errors.log` is appended to `.gitignore` if not already present
**And** a comment explaining why is included

**Given** a `.gitignore` file does NOT exist
**When** I run `nest init "Nike"`
**Then** a new `.gitignore` is created with only `.nest/errors.log` entry
**And** all other Nest files (`_nest_sources/`, `_nest_context/`, `.nest/manifest.json`) remain committable

**Given** I run `nest init "Nike"`
**When** project scaffolding completes
**Then** a `.gitattributes` file is created (or updated if one exists)
**And** it marks `_nest_sources/**/*.pdf`, `.docx`, `.pptx`, `.xlsx` as `binary`
**And** it marks all text file extensions in `_nest_sources/`, `_nest_context/`, and `.nest/` as `text eol=lf`
**And** this ensures cross-platform checksum consistency for shared knowledge base usage

**Given** I run `nest init` without a project name
**When** the command executes
**Then** an error is displayed: "Project name required. Usage: nest init 'Project Name'"

**Given** I run `nest init` in a directory that already has `.nest/manifest.json`
**When** the command executes
**Then** an error is displayed: "Nest project already exists. Use `nest sync` to process documents."

---

### Story 1.2: VS Code Agent File Generation

**As a** user,
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
- Reading `.nest/00_MASTER_INDEX.md` first
- Citing sources with filenames
- Never reading `_nest_sources/` or system files
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
  1. Drop your documents into _nest_sources/
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

As a user with project documents, I can drop them into a folder and have them automatically converted into AI-readable Markdown, so my Copilot agent can understand them.

### Story 2.1: File Discovery & Checksum Engine

**As a** user with documents in `_nest_sources/`,
**I want** the system to detect which files are new, modified, or unchanged,
**So that** only necessary files are processed, saving time.

**Acceptance Criteria:**

**Given** `_nest_sources/` contains files (.pdf, .docx, .pptx, .xlsx, .html)
**When** sync runs file discovery
**Then** all supported files are found recursively (including subdirectories)
**And** unsupported file types are ignored

**Given** a file exists in `_nest_sources/` but NOT in manifest
**When** checksum comparison runs
**Then** the file is marked as "new" for processing

**Given** a file exists in both `_nest_sources/` and manifest
**When** the SHA-256 checksum differs from manifest
**Then** the file is marked as "modified" for processing

**Given** a file exists in both `_nest_sources/` and manifest
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
**And** the file is logged to `.nest/errors.log`

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

**Given** source file at `_nest_sources/contracts/2024/alpha.pdf`
**When** processing completes
**Then** output is written to `_nest_context/contracts/2024/alpha.md`

**Given** nested directory structure in `_nest_sources/`
**When** output directories don't exist in `_nest_context/`
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
**Then** `.nest/00_MASTER_INDEX.md` is created/updated

**Given** 47 files are processed (both generated and user-curated)
**When** index is generated
**Then** format is:
```markdown
# Nest Project Index: Nike
Generated: 2026-01-12T14:30:00Z | Files: 47

## File Listing
contracts/2024/alpha.md
contracts/2024/beta.md
developer-guide.md
reports/Q3_summary.md
...
```
**And** one file per line (token-efficient)
**And** paths are relative to `_nest_context/`
**And** includes both manifest-tracked and user-curated files

**Given** files are removed from `_nest_context/`
**When** index regenerates
**Then** removed files no longer appear in index

---

### Story 2.6: Orphan Cleanup

**As a** user,
**I want** outdated processed files removed when I delete sources,
**So that** my knowledge base stays in sync with my actual documents.

**Acceptance Criteria:**

**Given** `_nest_context/old_report.md` exists and is tracked in manifest
**When** `_nest_sources/old_report.pdf` is deleted and sync runs
**Then** `_nest_context/old_report.md` is automatically removed
**And** the file is removed from manifest

**Given** I have manually added `developer-guide.md` to `_nest_context/` (not in manifest)
**When** I run `nest sync --clean`
**Then** `developer-guide.md` is NOT removed (not tracked, therefore not an orphan)
**And** console confirms: "User-curated files: 1 (preserved)"

**Given** sync runs with `--no-clean` flag
**When** orphan files are detected
**Then** orphan files are NOT removed
**And** they remain in `_nest_context/`

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
**Then** errors are appended to `.nest/errors.log` with format:
`2026-01-12T10:30:00 ERROR [sync] file.pdf: Error description`

---

### Story 2.8: Sync Command CLI Integration

**As a** user,
**I want** clear visual feedback during sync,
**So that** I know what's happening with my documents.

**Dev Note:** A stub `sync` command already exists in `src/nest/cli/main.py` that returns "Not implemented" with exit code 1. This was added to prevent Typer's single-command promotion. Replace the stub with the real implementation.

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
  Failed:    2 (see .nest/errors.log)
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

### Story 2.9: E2E Testing Framework for CLI Commands

**As a** developer working on Nest,
**I want** an end-to-end testing framework that validates full CLI command flows with real file I/O and actual Docling processing,
**So that** I can catch integration bugs that unit and mocked tests miss, and have confidence that releases work correctly.

**Background:**
This story was added after v0.1.0 release revealed a bug that would have been caught with proper E2E tests. E2E tests are now a required gate for story completion.

**Acceptance Criteria:**

**Infrastructure Setup:**

**Given** a developer wants to run E2E tests
**When** they execute `pytest -m "e2e" --timeout=60`
**Then** only E2E tests run with 60-second timeout
**And** tests skip automatically if Docling models are not downloaded

**Given** E2E test fixtures include binary documents (PDF, DOCX, PPTX, XLSX)
**When** the repository is cloned on any platform
**Then** binary files are not corrupted by line-ending normalization
**And** `.gitattributes` marks fixture files as binary

**Given** an E2E test class with multiple tests
**When** `temp_project` fixture is used
**Then** it uses `scope="class"` to share init overhead within the test class

**Init Command E2E:**

**Given** `nest init "TestProject"` is run via subprocess in an empty temp directory
**When** the command completes
**Then** exit code is 0
**And** `_nest_sources/` directory exists and is empty
**And** `_nest_context/` directory exists and is empty
**And** `.nest/manifest.json` exists with valid JSON containing project name

**Sync Command E2E:**

**Given** a Nest project is initialized
**And** 4 test documents are placed in nested structure under `_nest_sources/`:
  - `reports/quarterly.pdf`
  - `reports/summary.docx`
  - `presentations/deck.pptx`
  - `presentations/data.xlsx`
**When** `nest sync` is run via subprocess
**Then** exit code is 0
**And** output structure mirrors input in `_nest_context/`:
  - `reports/quarterly.md`
  - `reports/summary.md`
  - `presentations/deck.md`
  - `presentations/data.md`
**And** all output files have `.md` extension
**And** all output files are non-empty
**And** manifest contains entries for all 4 files
**And** stdout indicates 4 files processed

**Negative Path Tests:**

**Given** `nest sync` is run in a directory without `.nest/manifest.json`
**When** the command executes
**Then** exit code is 1
**And** error message contains "No Nest project found" or "nest init"

**Given** `nest init "Project2"` is run in a directory with existing manifest
**When** the command executes
**Then** exit code is 1
**And** error message indicates project already exists

**Given** `nest init` is run without a project name argument
**When** the command executes
**Then** exit code is 1
**And** error message indicates project name is required

**Given** a corrupt/truncated PDF is placed in `_nest_sources/`
**And** `nest sync` is run with default flags
**When** processing encounters the corrupt file
**Then** the corrupt file is skipped
**And** error is logged to `.nest/errors.log`
**And** other valid files are still processed
**And** exit code is 0 (skip mode)

**Given** a corrupt PDF is placed in `_nest_sources/`
**And** `nest sync --on-error=fail` is run
**When** processing encounters the corrupt file
**Then** exit code is 1
**And** sync aborts immediately

**Given** an unsupported file type (e.g., `.txt`) is placed in `_nest_sources/`
**When** `nest sync` is run
**Then** the unsupported file is ignored (not in output)
**And** no error is logged for it

**Given** `_nest_sources/` contains no supported files
**When** `nest sync` is run
**Then** exit code is 0
**And** output indicates no files to process

**Test Documents:**

**Given** test fixtures are needed in `tests/e2e/fixtures/`
**When** documents are created
**Then** each document is under 100KB for fast processing
**And** content is simple (no complex formatting)
**And** one file exists for each supported type (PDF, DOCX, PPTX, XLSX)

**pytest Configuration:**

**Given** `pyproject.toml` pytest configuration
**When** markers are defined
**Then** `e2e` marker is registered with description: "End-to-end tests (require real Docling, may be slow)"

---

### Story 2.10: Folder Naming Refactor & User-Curated Context Support

**As a** user,
**I want** unambiguous folder names that won't conflict with my project files and the ability to add my own context files directly,
**So that** I can incorporate pre-existing documentation into my knowledge base without processing, and Nest folders are clearly identifiable.

**Scope:** This is a refactoring story that implements the approved Sprint Change Proposal (2026-01-21). It renames folders from `raw_inbox/processed_context` to `_nest_sources/_nest_context`, enhances orphan cleanup to be manifest-aware, and updates index generation to include user-curated files.

**Reference Document:** `_bmad-output/planning-artifacts/sprint-change-proposal-2026-01-21.md`

**Acceptance Criteria:**

**Folder Naming:**

**Given** I run `nest init "ProjectName"`
**When** the command completes
**Then** `_nest_sources/` directory is created (not `raw_inbox/`)
**And** `_nest_context/` directory is created (not `processed_context/`)
**And** `.nest/manifest.json` is created with correct paths
**And** `_nest_sources/` is added to `.gitignore`

**Given** I run `nest sync`
**When** files are discovered
**Then** sync scans `_nest_sources/` for input files
**And** processed files are written to `_nest_context/`

**User-Curated Context Files:**

**Given** I manually add `developer-guide.md` directly to `_nest_context/` (not via processing)
**When** I run `nest sync`
**Then** `developer-guide.md` is NOT removed by orphan cleanup
**And** `developer-guide.md` IS included in `00_MASTER_INDEX.md`
**And** console displays: "User-curated files: X (preserved)"

**Manifest-Aware Orphan Cleanup:**

**Given** `_nest_context/report.md` exists and IS tracked in manifest
**And** I delete `_nest_sources/report.pdf`
**When** I run `nest sync`
**Then** `_nest_context/report.md` IS removed (manifest-tracked orphan)
**And** manifest entry is removed

**Given** `_nest_context/custom.md` exists and is NOT in manifest
**When** I run `nest sync`
**Then** `_nest_context/custom.md` is NOT removed (user-curated, not an orphan)

**Index Generation:**

**Given** `_nest_context/` contains both processed and user-curated files
**When** index generation runs
**Then** `00_MASTER_INDEX.md` includes ALL files from `_nest_context/`
**And** no distinction is made between generated and user-curated files in the index

**Agent Template:**

**Given** the VS Code agent template
**When** `nest init` creates the agent file
**Then** agent instructions reference `_nest_context/` as the knowledge base
**And** agent instructions reference `_nest_sources/` as forbidden folder

**Backward Compatibility:**

**Given** an existing project with old folder names (`raw_inbox/`, `processed_context/`)
**When** user runs `nest sync` after updating Nest
**Then** a clear error or migration message is displayed
**And** user is guided to rename folders or re-run init

**All Existing Tests Pass:**

**Given** all unit, integration, and E2E tests
**When** the refactoring is complete
**Then** all tests pass with updated folder names
**And** no regressions are introduced

---

### Story 2.11: Context Text File Support in Index and Status

**As a** user who manually adds plain text files (`.txt`, `.yaml`, `.csv`, etc.) to `_nest_context/`,
**I want** those files to appear in the master index and be counted correctly in status,
**So that** my AI agent can discover and reference all text-based context I've curated, not just Markdown files.

**Scope:** Introduces a `CONTEXT_TEXT_EXTENSIONS` constant defining the 10 supported plain-text file types for the context directory. Updates index generation, status counting, and user-curated file counting to use this single constant instead of hardcoded `.md` filters.

**Acceptance Criteria:**

**Context Text Extensions Constant:**

**Given** the `core/paths.py` module
**When** the developer references supported context file types
**Then** a `CONTEXT_TEXT_EXTENSIONS` constant is available containing:
`.md`, `.txt`, `.text`, `.rst`, `.csv`, `.json`, `.yaml`, `.yml`, `.toml`, `.xml`
**And** all modules that filter context files import this constant from `core/paths.py`

**Index Generation Includes All Text Types:**

**Given** `_nest_context/` contains files with various text extensions (`.md`, `.txt`, `.yaml`, `.csv`, `.json`, etc.)
**When** `nest sync` runs and regenerates `00_MASTER_INDEX.md`
**Then** ALL files matching `CONTEXT_TEXT_EXTENSIONS` are listed in the index
**And** files with unsupported extensions (e.g., `.png`, `.zip`, `.exe`) are NOT listed

**Given** I manually add `meeting-notes.txt` to `_nest_context/`
**When** `nest sync` runs
**Then** `meeting-notes.txt` appears in `00_MASTER_INDEX.md`

**Given** I manually add `api-spec.yaml` to `_nest_context/`
**When** `nest sync` runs
**Then** `api-spec.yaml` appears in `00_MASTER_INDEX.md`

**Status Counting Uses Text Extensions:**

**Given** `_nest_context/` contains files of varying types
**When** `nest status` analyzes context files
**Then** only files matching `CONTEXT_TEXT_EXTENSIONS` are counted in the context file total
**And** unsupported file types are excluded from counts

**User-Curated Counting Uses Text Extensions:**

**Given** `_nest_context/` contains both manifest-tracked `.md` files and user-added `.txt`/`.yaml`/`.csv` files
**When** orphan service counts user-curated files
**Then** only files matching `CONTEXT_TEXT_EXTENSIONS` (and not in manifest) are counted as user-curated
**And** binary/unsupported files are excluded from user-curated count

**Orphan Detection Unchanged:**

**Given** a user adds `report.txt` directly to `_nest_context/` (not via sync)
**When** `nest sync` runs orphan cleanup
**Then** `report.txt` is NOT removed (not in manifest = user-curated, preserved)

**Agent Template Updated:**

**Given** the VS Code agent template
**When** `nest init` generates the agent file
**Then** the agent instructions mention that context files may be in various text formats (not just Markdown)

**All Existing Tests Pass:**

**Given** all unit, integration, and E2E tests
**When** the changes are complete
**Then** all tests pass with no regressions

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
**And** logged to `.nest/errors.log`

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

**Given** `.nest/manifest.json` is missing
**When** validation runs
**Then** error shows: `Manifest: missing ✗`

**Given** manifest JSON is corrupt or invalid
**When** validation runs
**Then** error shows: `Manifest: invalid JSON ✗`

**Given** `.github/agents/nest.agent.md` is missing
**When** validation runs
**Then** warning shows: `Agent file: missing ✗`

**Given** `_nest_sources/` or `_nest_context/` directories are missing
**When** validation runs
**Then** warning shows: `Folders: _nest_sources/ missing ✗`

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
**And** if Y: scans `_nest_context/` and rebuilds manifest

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
source = "git+https://github.com/jbb10/nest"
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

  What's new: https://github.com/jbb10/nest/blob/main/CHANGELOG.md
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

---

## Epic 5: Index Intelligence & Agent Enrichment

As a user who has synced documents, I want the master index to contain short, LLM-generated descriptions per file and a project-specific glossary, so the @nest agent can quickly identify relevant documents and understand project terminology.

### Story 5.1: Index Enrichment Pipeline

**As a** user who has synced project documents,
**I want** the master index to contain a short description per file,
**So that** the @nest agent (and I) can quickly identify which file to read without opening every document.

*(Full acceptance criteria in implementation artifact: `5-1-index-enrichment-pipeline.md`)*

---

### Story 5.2: Glossary Agent Integration

**As a** user starting work on a new project,
**I want** an AI-powered glossary agent that extracts and maintains a glossary of project-specific terms, abbreviations, stakeholder names, and domain jargon from my project documents,
**So that** I (and the @nest agent) can quickly understand project-specific language without manually compiling a dictionary.

**Acceptance Criteria:**

**Given** `nest sync` processes documents
**When** sync completes and glossary hints extraction runs
**Then** `_nest_context/00_GLOSSARY_HINTS.yaml` is created/updated with candidate terms:
```yaml
# Auto-generated by nest sync — do not edit manually
terms:
  - term: "PDC"
    category: "abbreviation"
    occurrences: 12
    source_files:
      - "contracts/alpha.md"
      - "reports/q3.md"
    context_snippets:
      - "The PDC review board meets weekly..."
  - term: "Sarah Mitchell"
    category: "proper_noun"
    occurrences: 8
    source_files:
      - "stakeholder-map.md"
    context_snippets:
      - "Sarah Mitchell, VP of Engineering..."
```

**Given** `nest init` creates the project
**When** agent files are generated
**Then** `.github/agents/nest-glossary.agent.md` is created alongside the existing `nest.agent.md`
**And** the glossary agent instructions tell it to:
1. Read `_nest_context/00_GLOSSARY_HINTS.yaml` for candidate terms with context
2. Read `_nest_context/glossary.md` if it already exists (to preserve human edits)
3. For each candidate term, determine if it is project-specific (not generic industry/tech terms)
4. Write a definition (1-2 sentences) for each qualifying term
5. Categorize terms (Abbreviation, Stakeholder, Domain Term, Project Name, etc.)
6. Never modify or delete definitions that already exist in `glossary.md` (human curation is sacred)
7. Sort the final glossary alphabetically by Term
8. Write the updated `glossary.md`

**Given** the glossary agent produces output
**When** `glossary.md` is written to `_nest_context/`
**Then** the file has this format:
```markdown
# Project Glossary

<!-- nest:glossary-start -->
| Term | Category | Definition | Source(s) |
|------|----------|------------|-----------|
| PDC | Abbreviation | Project Delivery Committee — the governance board responsible for... | contracts/alpha.md, reports/q3.md |
| Sarah Mitchell | Stakeholder | VP of Engineering, primary technical decision-maker for... | stakeholder-map.md |
<!-- nest:glossary-end -->
```

**Given** a `glossary.md` already exists with human-edited definitions
**When** the glossary agent is re-invoked after a new sync
**Then** existing definitions are preserved verbatim
**And** only new terms (not already in the table) are added
**And** no terms are ever deleted automatically

**Given** sync completes and `00_GLOSSARY_HINTS.yaml` contains candidate terms
**When** the sync summary is displayed
**Then** an informational message is shown:
```
ℹ {N} candidate glossary term(s) discovered.
  Run the @nest-glossary agent in VS Code chat to generate/update the glossary.
```
**And** if no new candidate terms were found, no glossary message is shown

**Given** `glossary.md` exists in `_nest_context/`
**When** the master index is generated
**Then** `glossary.md` is listed in the index like any other context file
**And** the @nest agent can reference it for terminology lookups

**Given** `00_GLOSSARY_HINTS.yaml` exists in `_nest_context/`
**When** index generation scans the context directory
**Then** `00_GLOSSARY_HINTS.yaml` is excluded from the master index (like `00_INDEX_HINTS.yaml`)

**Given** sync runs with `--dry-run`
**When** glossary hints would be generated
**Then** no hints file is written (consistent with dry-run behavior)

**Given** all unit, integration, and E2E tests
**When** the changes are complete
**Then** all tests pass with no regressions

**Dependencies:** Story 5.1 (establishes hints file pattern, metadata extraction, agent template shipping)

---

## Epic 6: Built-in AI Enrichment

As a user who syncs documents, I want Nest to automatically generate file descriptions and a project glossary using my existing AI API keys, so that my index is enriched and terminology is catalogued without manual agent invocations.

### Story 6.1: LLM Provider Adapter & AI Detection

**As a** developer building AI-powered features for Nest,
**I want** a protocol-based LLM adapter that auto-detects API credentials from environment variables,
**So that** all AI features have a consistent, testable interface to call LLMs with zero per-project configuration.

**Acceptance Criteria:**

**Given** `NEST_API_KEY` is set in the environment
**When** the LLM provider is initialized
**Then** it uses `NEST_API_KEY` as the API key
**And** checks `NEST_BASE_URL` for the base URL (default: `https://api.openai.com/v1`)
**And** checks `NEST_TEXT_MODEL` for the model name (default: `gpt-4o-mini`)

**Given** `NEST_API_KEY` is NOT set but `OPENAI_API_KEY` IS set
**When** the LLM provider is initialized
**Then** it falls back to `OPENAI_API_KEY`
**And** falls back to `OPENAI_BASE_URL` for endpoint
**And** falls back to `OPENAI_MODEL` for model name

**Given** neither `NEST_API_KEY` nor `OPENAI_API_KEY` is set
**When** the LLM provider is initialized
**Then** it returns `None` (AI is not available)
**And** no error is raised

**Given** a valid LLM provider is created
**When** `complete(system_prompt, user_prompt)` is called
**Then** it sends a chat completion request to the configured endpoint
**And** returns the response text and token usage (prompt_tokens, completion_tokens)

**Given** the LLM API call fails (network error, auth error, timeout)
**When** the error is caught
**Then** the error is logged via Python logging
**And** a `None` result is returned (caller handles graceful degradation)
**And** no exception propagates to the user

**Given** the adapter is used in tests
**When** `LLMProviderProtocol` is referenced
**Then** it is a `@runtime_checkable` Protocol in `adapters/protocols.py`
**And** test doubles can be injected via standard DI pattern

**Given** the `openai` Python SDK is added as a dependency
**When** `pyproject.toml` is updated
**Then** `openai>=1.0.0` is listed in the project dependencies

---

### Story 6.2: AI Index Enrichment in Sync

**As a** user who has synced project documents,
**I want** Nest to automatically generate short descriptions for each file in the master index during sync,
**So that** the index is immediately useful for finding relevant documents without manually running an agent.

**Acceptance Criteria:**

**Given** sync completes processing and AI is configured (API key detected in environment)
**When** the index generation phase runs
**Then** an `AIEnrichmentService` is called with the metadata hints (`00_INDEX_HINTS.yaml` data) for files needing descriptions
**And** for each file with an empty or changed description, a single LLM call generates a ≤15-word description
**And** the generated descriptions are written into the `00_MASTER_INDEX.md` table

**Given** a file's `content_hash` has NOT changed since last sync
**When** AI enrichment runs
**Then** the existing description is carried forward (no LLM call made)
**And** tokens are not wasted on unchanged files

**Given** a file's `content_hash` HAS changed since last sync
**When** AI enrichment runs
**Then** the old description is discarded
**And** a new LLM call generates a fresh description based on updated hints

**Given** a file is brand new (not in previous index)
**When** AI enrichment runs
**Then** an LLM call generates a description for the new file

**Given** the LLM call fails for a specific file
**When** the error is caught
**Then** the description for that file remains empty (same as unenriched state)
**And** a warning is logged
**And** sync continues processing remaining files

**Given** AI is NOT configured (no API key in environment)
**When** sync runs
**Then** the index is generated without descriptions (same behavior as before Epic 6)
**And** no error or warning about AI is shown

**Given** the `--no-ai` flag is passed to `nest sync`
**When** sync runs with AI configured
**Then** AI enrichment is skipped entirely
**And** existing descriptions from previous syncs are still carried forward via content hash logic

**Given** the system prompt for index enrichment
**When** constructing the LLM call
**Then** the prompt instructs the model to write a description of at most 15 words
**And** the prompt provides the file's headings, first paragraph, and line count from the hints
**And** the prompt forbids pipe characters in the output (Markdown table safety)

**Given** all unit and integration tests
**When** the changes are complete
**Then** all tests pass with LLM calls mocked via `LLMProviderProtocol` test doubles

**Dependencies:** Story 6.1 (LLM Provider Adapter)

---

### Story 6.3: AI Glossary Generation in Sync

**As a** user who has synced project documents,
**I want** Nest to automatically generate and maintain a project glossary of terms, abbreviations, and stakeholder names during sync,
**So that** I and the @nest agent can understand project-specific language without running a separate agent.

**Acceptance Criteria:**

**Given** sync completes processing and AI is configured (API key detected in environment)
**When** glossary candidate terms exist in `00_GLOSSARY_HINTS.yaml`
**Then** an `AIGlossaryService` is called with the candidate terms
**And** for each new candidate term (not already defined in `glossary.md`), an LLM call determines:
  - Whether the term is truly project-specific (skip generic industry terms)
  - A 1-2 sentence definition based on context snippets
  - A category (Abbreviation, Stakeholder, Domain Term, Project Name, Tool/System, Other)
**And** the results are written into `_nest_context/glossary.md` between `<!-- nest:glossary-start -->` and `<!-- nest:glossary-end -->` markers

**Given** `glossary.md` already exists with human-edited definitions
**When** AI glossary generation runs
**Then** existing definitions are preserved verbatim (never modified or deleted)
**And** only new terms are added to the table
**And** the table is kept sorted alphabetically by Term

**Given** no candidate terms have changed since last sync
**When** AI glossary generation runs
**Then** no LLM calls are made
**And** `glossary.md` is not modified

**Given** new candidate terms are discovered from changed/new files
**When** AI glossary generation runs
**Then** only the new terms trigger LLM calls
**And** terms from unchanged files are not re-processed

**Given** the LLM determines a candidate term is generic (e.g., common industry jargon)
**When** the filtering decision is made
**Then** the term is skipped and not added to the glossary

**Given** the LLM call fails for a specific term
**When** the error is caught
**Then** that term is skipped (can be retried on next sync)
**And** a warning is logged
**And** other terms continue processing

**Given** AI is NOT configured (no API key in environment)
**When** sync runs
**Then** no `glossary.md` is generated or modified
**And** candidate terms are still extracted to `00_GLOSSARY_HINTS.yaml` (the deterministic Phase 1 continues)

**Given** the `--no-ai` flag is passed to `nest sync`
**When** sync runs
**Then** AI glossary generation is skipped
**And** existing `glossary.md` is not modified

**Given** `glossary.md` does not yet exist
**When** AI glossary generation runs for the first time
**Then** the file is created with the standard header and table markers
**And** all qualifying candidate terms are added

**Given** the system prompt for glossary generation
**When** constructing each LLM call
**Then** the prompt provides the term, its category hint, occurrence count, source files, and context snippets
**And** the prompt instructs the model to return: is_project_specific (bool), definition (1-2 sentences), category
**And** the prompt forbids pipe characters in the definition

**Given** all unit and integration tests
**When** the changes are complete
**Then** all tests pass with LLM calls mocked via `LLMProviderProtocol` test doubles

**Dependencies:** Story 6.1 (LLM Provider Adapter)

---

### Story 6.4: Parallel AI Execution & Token Reporting

**As a** user running `nest sync` with AI enrichment,
**I want** the index enrichment and glossary generation to run in parallel and see how many tokens were used,
**So that** sync completes faster and I can track AI usage costs.

**Acceptance Criteria:**

**Given** AI is configured and both index enrichment and glossary generation have work to do
**When** sync reaches the AI phase (after document processing, manifest commit, and orphan cleanup)
**Then** index enrichment and glossary generation run concurrently via `concurrent.futures.ThreadPoolExecutor` with `max_workers=2`
**And** both tasks complete before the sync summary is displayed

**Given** one AI task fails (e.g., glossary times out) while the other succeeds
**When** parallel execution completes
**Then** the successful task's results are applied normally
**And** the failed task degrades gracefully (partial results or empty)
**And** errors are logged

**Given** only one AI task has work (e.g., no new glossary terms but index needs enrichment)
**When** sync reaches the AI phase
**Then** only the task with work runs (no unnecessary thread spawning)

**Given** AI enrichment runs (either or both tasks)
**When** sync summary is displayed
**Then** token usage is reported:
```
  AI tokens:    1,247 (prompt: 983, completion: 264)
```
**And** the token counts are aggregated across both enrichment and glossary calls

**Given** AI enrichment runs but generates zero descriptions and zero glossary terms (all cached)
**When** sync summary is displayed
**Then** no token usage line is shown (nothing to report)

**Given** the first time AI is detected during sync
**When** sync summary is displayed
**Then** a one-time informational tip is shown:
```
  🤖 AI enrichment enabled (found OPENAI_API_KEY)
```
**And** a tip is shown: `💡 Run 'nest config ai' to change AI settings. Use --no-ai to skip.`

**Given** AI has been used in previous syncs for this project
**When** subsequent syncs run
**Then** the "AI enrichment enabled" discovery message is NOT repeated
**And** only token usage is reported (if tokens were consumed)

**Given** progress display is active during sync
**When** the AI phase runs
**Then** a progress indicator shows AI activity: `🤖 AI enrichment...`
**And** completion shows counts: `4 descriptions, 3 glossary terms`

**Given** all unit and integration tests
**When** the changes are complete
**Then** parallel execution is tested with both tasks mocked
**And** token aggregation is tested
**And** all tests pass with no regressions

**Dependencies:** Story 6.2 (AI Index Enrichment), Story 6.3 (AI Glossary Generation)

---

### Story 6.5: `nest config ai` Shell RC Writer

**As a** user who wants to set up AI enrichment,
**I want** a `nest config ai` command that writes my API credentials to my shell RC file,
**So that** the keys are available as environment variables in all future terminal sessions without manual editing.

**Acceptance Criteria:**

**Given** the user runs `nest config ai`
**When** the command starts
**Then** it detects the user's shell from the `$SHELL` environment variable
**And** resolves the correct RC file:
  - zsh → `~/.zshrc`
  - bash (macOS) → `~/.bash_profile` if it exists, else `~/.bashrc`
  - bash (Linux) → `~/.bashrc`
  - fish → `~/.config/fish/config.fish`
  - fallback → `~/.profile`

**Given** the shell RC file is identified
**When** the interactive prompt runs
**Then** it asks for:
  - API endpoint (with default: `https://api.openai.com/v1`)
  - Model/deployment name (with default: `gpt-4o-mini`)
  - API key (input masked with `••••` style)

**Given** the user provides all values
**When** the config is saved
**Then** the following block is written to the shell RC file:
```bash
# --- Nest AI Configuration (managed by `nest config ai`) ---
export NEST_BASE_URL="https://..."
export NEST_TEXT_MODEL="gpt-4o-mini"
export NEST_API_KEY="sk-..."
# --- End Nest AI Configuration ---
```
**And** a success message is shown: `✓ Added to ~/.zshrc`
**And** a reminder is shown: `⚠ Run 'source ~/.zshrc' or open a new terminal to activate.`

**Given** the Nest AI config block already exists in the RC file
**When** `nest config ai` runs again
**Then** the existing block is replaced (not duplicated)
**And** all other content in the RC file is preserved

**Given** the RC file does not exist
**When** `nest config ai` runs
**Then** the file is created with the config block
**And** the parent directory is created if needed (e.g., `~/.config/fish/`)

**Given** AI env vars are already set in the environment (from any source)
**When** `nest config ai` runs
**Then** it shows the current values as defaults in the prompts:
```
  API endpoint [https://my-corp.openai.azure.com/]: 
  Model [gpt-4o-mini]: 
  API key [••••sk-1234]: 
```
**And** the user can press Enter to keep existing values or type new ones

**Given** the user wants to remove AI configuration
**When** running `nest config ai --remove`
**Then** the Nest AI config block is removed from the RC file
**And** all other content is preserved
**And** a message confirms: `✓ AI configuration removed from ~/.zshrc`

**Given** fish shell is detected
**When** config is written
**Then** fish-compatible syntax is used:
```fish
# --- Nest AI Configuration (managed by `nest config ai`) ---
set -gx NEST_BASE_URL "https://..."
set -gx NEST_TEXT_MODEL "gpt-4o-mini"
set -gx NEST_API_KEY "sk-..."
# --- End Nest AI Configuration ---
```

**Given** all unit tests
**When** the changes are complete
**Then** RC file detection is tested for all shell types
**And** idempotent write/replace is tested
**And** fish syntax generation is tested
**And** all tests pass with no regressions

---

### Story 6.6: Remove Enricher & Glossary Agents

**As a** user,
**I want** the separate enricher and glossary agents removed from the project,
**So that** I'm not confused by multiple agents and all AI enrichment happens automatically during sync.

**Acceptance Criteria:**

**Given** `nest init` runs to create a new project
**When** agent files are generated
**Then** only `.github/agents/nest.agent.md` is created
**And** `nest-enricher.agent.md` is NOT created
**And** `nest-glossary.agent.md` is NOT created

**Given** the codebase is updated
**When** agent template files are reviewed
**Then** `src/nest/agents/templates/enricher.md.jinja` is deleted
**And** `src/nest/agents/templates/glossary.md.jinja` is deleted

**Given** `VSCodeAgentWriter` in `src/nest/agents/vscode_writer.py`
**When** the class is reviewed
**Then** `render_enricher()` method is removed
**And** `generate_enricher()` method is removed
**And** `render_glossary()` method is removed
**And** `generate_glossary()` method is removed
**And** only `render()` and `generate()` methods remain (for the primary nest agent)

**Given** `init_cmd.py` wires up agent generation
**When** init runs
**Then** any calls to `generate_enricher()` or `generate_glossary()` are removed
**And** only the primary `nest.agent.md` is generated

**Given** sync completes and AI is NOT configured
**When** the sync summary is displayed
**Then** NO message about running `@nest-enricher` or `@nest-glossary` agents is shown
**And** the old prompt messages are removed from `_display_sync_summary` in `sync_cmd.py`

**Given** sync completes and AI IS configured
**When** the sync summary is displayed
**Then** enrichment results are shown inline (descriptions generated, glossary terms defined, token usage)
**And** no reference to agent invocation is made

**Given** `ProjectChecker` validates project state
**When** agent file checks run
**Then** only `nest.agent.md` presence is checked
**And** no checks for `nest-enricher.agent.md` or `nest-glossary.agent.md` exist

**Given** all existing tests reference enricher or glossary agents
**When** tests are updated
**Then** tests for `render_enricher`, `generate_enricher`, `render_glossary`, `generate_glossary` are removed
**And** tests for `init_cmd` no longer assert enricher/glossary agent file creation
**And** tests for sync summary no longer assert agent prompt messages
**And** all remaining tests pass with no regressions

**Dependencies:** Story 6.2 (AI Index Enrichment), Story 6.3 (AI Glossary Generation) — remove the old mechanism only after the replacement is in place

---

### Story 6.8: Unified LLM Glossary Pipeline

**As a** user who syncs project documents,
**I want** Nest to extract and define glossary terms in a single LLM pass per document (instead of regex extraction → per-term LLM calls),
**So that** the glossary captures all term types (not just abbreviations and proper nouns), the pipeline is simpler, and ~400 lines of regex/merge/threshold code are eliminated.

**Acceptance Criteria:**

**Given** sync completes processing and AI is configured
**When** changed/new context files exist
**Then** `AIGlossaryService.generate()` is called with changed file paths
**And** for each file (or chunk), a single LLM call extracts AND defines all glossary-worthy terms in Markdown table row format
**And** new terms are appended to `glossary.md` with Source(s) populated from the filename
**And** existing definitions are preserved verbatim (human-edit safe)
**And** only changed/new files are sent to the LLM (incremental)

**Given** a context file exceeds ~40K tokens
**When** the file is processed
**Then** it is split into chunks on paragraph boundaries
**And** terms are deduplicated across chunks

**Given** all code changes are complete
**When** searching the codebase
**Then** `GlossaryHintsService`, `CandidateTerm`, `GlossaryHints`, `GLOSSARY_HINTS_FILE`, and `00_GLOSSARY_HINTS.yaml` are fully removed from `src/` and `tests/`

**Given** `00_GLOSSARY_HINTS.yaml` exists from a previous sync
**When** the first new-style sync runs
**Then** the file is deleted (legacy cleanup)

**Dependencies:** Story 6.3 (AI Glossary Generation in Sync), Story 5.2 (Glossary Agent Integration)

---

## Epic 7: Image Description via Vision LLM

As a user syncing documents that contain images and diagrams, I want those images automatically described by a vision-capable LLM, so that the @nest agent can understand and reference visual content — not just text.

**Reference:** `docs/docling-picture-description-guide.md`

### Story 7.1: Vision-Capable LLM Adapters

**As a** developer extending the LLM infrastructure,
**I want** existing LLM adapters to support multi-modal (image + text) messages,
**So that** images can be sent to vision-capable models for description.

**Acceptance Criteria:**

**Given** `adapters/protocols.py`
**When** `VisionLLMProviderProtocol` is defined
**Then** it exposes: `complete_with_image(prompt: str, image_base64: str, mime_type: str) -> LLMCompletionResult | None`
**And** it is separate from the existing `LLMProviderProtocol`

**Given** `OpenAIAdapter` and `AzureOpenAIAdapter`
**When** vision variants are created (`OpenAIVisionAdapter`, `AzureOpenAIVisionAdapter`)
**Then** they construct multi-modal message payloads with `image_url` content blocks:
```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
        ],
    }
]
```
**And** they use the vision model name (not the text enrichment model)
**And** they track `prompt_tokens` and `completion_tokens` in `LLMCompletionResult`
**And** they return `None` on failure (never raise)

**Given** `NEST_VISION_MODEL` env var is set
**When** `create_llm_provider()` runs
**Then** a vision adapter is created alongside the text adapter
**And** fallback chain is: `NEST_VISION_MODEL` → `OPENAI_VISION_MODEL` → default `"gpt-4.1"`
**And** the vision adapter uses the same API key and endpoint as the text adapter

**Given** no API key is configured
**When** vision adapter creation is attempted
**Then** `vision_provider` is `None`
**And** no error is raised

---

### Story 7.2: Docling Two-Pass Image Pipeline

**As a** developer modifying the document processor,
**I want** `DoclingProcessor` to classify images locally during conversion,
**So that** we can send the right prompt to the right image type.

**Acceptance Criteria:**

**Given** AI is configured and vision provider is available
**When** `DoclingProcessor` initializes `PdfPipelineOptions`
**Then** options include:
- `do_picture_classification=True` (local model, no API calls)
- `do_picture_description=False` (we handle this in pass 2)
- `generate_picture_images=True`
- `images_scale=2.0`

**Given** AI is NOT configured (or `--no-ai` flag is set)
**When** `DoclingProcessor` initializes
**Then** classification and image extraction are disabled
**And** export uses `ImageRefMode.PLACEHOLDER` (current behavior)

**Given** `DoclingProcessor`'s `process()` method is refactored
**When** called with vision support enabled
**Then** it returns/exposes the `ConversionResult` object
**So that** the `PictureDescriptionService` can iterate pictures

**Given** conversion completes with classification enabled
**When** `PictureItem` elements are inspected
**Then** each has `meta.classification.predictions` with `class_name` + `confidence`
**And** labels include: `flow_chart`, `block_diagram`, `natural_image`, `bar_chart`, `line_chart`, `pie_chart`, `scatter_plot`, `table`, `map`, `logo`, `signature`

---

### Story 7.3: Picture Description Service

**As a** developer building the image description pipeline,
**I want** a `PictureDescriptionService` that classifies, routes, and describes images in parallel,
**So that** diagrams produce Mermaid, photos get descriptions, and logos/signatures are skipped.

**Acceptance Criteria:**

**Given** `PictureDescriptionService` receives a `ConversionResult` with classified `PictureItem` elements
**When** `describe()` is called
**Then** it iterates all `PictureItem` elements and categorizes:
- `flow_chart`, `block_diagram` (confidence ≥ 0.5) → `MERMAID_PROMPT`
- `logo`, `signature` (confidence ≥ 0.5) → SKIP (no API call)
- All others (`natural_image`, `bar_chart`, `line_chart`, `pie_chart`, etc.) → `DESCRIPTION_PROMPT`

**Given** prompt templates
**Then** `MERMAID_PROMPT` instructs the model to produce a fenced ` ```mermaid ` code block with the correct diagram type (flowchart, sequenceDiagram, classDiagram, etc.) capturing all nodes, edges, and labels
**And** `DESCRIPTION_PROMPT` instructs the model to describe the image concisely, summarize chart data points and trends, and focus on technical document context

**Given** images are categorized for description
**When** LLM calls are made
**Then** up to 50 concurrent calls via `ThreadPoolExecutor`
**And** each call uses `complete_with_image()` on the vision adapter

**Given** LLM calls complete for a `PictureItem`
**When** result is returned
**Then** `element.meta.description = PictureDescriptionData(text=response, created_by="azure-{model}")`
**And** description is stored in-place on the Docling document model

**Given** `export_to_markdown()` is called after description
**When** markdown is generated
**Then** descriptions and Mermaid blocks appear inline where images were
**And** no `[Image: ...]` placeholders remain for described images

**Given** a document has > 50 describable images (excluding skipped logos/signatures)
**When** the cap is reached
**Then** only the first 50 describable images get LLM calls
**And** remaining images produce placeholder markers

**Given** an individual LLM call fails
**When** `None` is returned
**Then** that image keeps its placeholder marker
**And** a warning is logged
**And** other images are not affected

**Given** `describe()` completes
**When** results are tallied
**Then** `PictureDescriptionResult` includes:
- `images_described: int`
- `images_mermaid: int`
- `images_skipped: int` (logos + signatures)
- `images_failed: int`
- `prompt_tokens: int`
- `completion_tokens: int`

---

### Story 7.4: Sync Pipeline Integration & Cross-File Parallelism

**As a** user running `nest sync` on documents with images,
**I want** image descriptions generated during sync without blocking other files,
**So that** my sync completes as fast as possible.

**Acceptance Criteria:**

**Given** `nest sync` processes file A (10 images) and file B (5 images)
**When** both files are converted by Docling
**Then** image description for file A and file B can run concurrently
**And** file B's markdown output is written as soon as file B's descriptions complete (does not wait for file A)

**Given** the sync loop processes a file with images
**When** AI is configured and vision provider is available
**Then** the flow is:
1. Docling converts document with classification + image extraction (pass 1)
2. `PictureDescriptionService.describe()` runs on the `ConversionResult` (pass 2, parallel LLM calls)
3. Descriptions stored in-place on `PictureItem` elements via `PictureDescriptionData`
4. `result.document.export_to_markdown()` produces final markdown with descriptions inline
5. Markdown written to output
6. Manifest updated

**Given** `--no-ai` flag is passed
**When** sync runs
**Then** image extraction and classification are disabled
**And** `ImageRefMode.PLACEHOLDER` is used (existing behavior)
**And** no vision LLM calls are made

**Given** sync completes with image descriptions
**When** summary is displayed
**Then** output includes: `"Images described: N (M as Mermaid diagrams)"`
**And** `"Images skipped: N (logos/signatures)"` when applicable
**And** vision tokens are aggregated into the existing token usage totals

**Given** all existing tests
**When** this change is integrated
**Then** all unit, integration, and E2E tests pass
**And** new tests cover: image extraction, description service, sync integration, parallel behavior

---

### Story 7.5: E2E Tests for Image Description

**As a** developer working on image description,
**I want** end-to-end tests that validate the full image description pipeline with real Docling processing and CLI invocation,
**So that** I can catch integration bugs between Docling image extraction, classification, vision LLM calls, and markdown output.

**Background:**
Following the E2E testing pattern established in Story 2.9. E2E tests use real file I/O, real Docling processing, and subprocess CLI invocation. Vision LLM calls are the only component that MUST be mocked (no real API calls in tests).

**Acceptance Criteria:**

**Test Fixtures:**

**Given** E2E test fixtures are needed for image description
**When** documents are created in `tests/e2e/fixtures/`
**Then** a PDF with at least one embedded image (photo/diagram) is included
**And** the fixture is under 200KB for fast processing
**And** `.gitattributes` marks the fixture as binary

**Image Description E2E (AI configured with mocked vision LLM):**

**Given** a Nest project is initialized
**And** a PDF containing images is placed in `_nest_sources/`
**And** AI environment variables are configured (API key, endpoint, vision model)
**And** the vision LLM adapter is mocked to return a canned description string
**When** `nest sync` is run
**Then** exit code is 0
**And** the output markdown in `_nest_context/` contains the canned description text
**And** the output markdown does NOT contain `[Image:` placeholder markers for described images
**And** stdout includes `"Images described:"` in the sync summary

**Mermaid Diagram E2E:**

**Given** a Nest project is initialized
**And** a PDF containing a flowchart or block diagram is placed in `_nest_sources/`
**And** the vision LLM adapter is mocked to return a fenced ` ```mermaid ` code block
**When** `nest sync` is run
**Then** exit code is 0
**And** the output markdown contains a ` ```mermaid ` code block
**And** the mermaid block includes diagram elements (nodes, edges)

**No-AI Fallback E2E:**

**Given** a Nest project is initialized
**And** a PDF containing images is placed in `_nest_sources/`
**And** NO AI environment variables are configured
**When** `nest sync` is run
**Then** exit code is 0
**And** the output markdown contains `[Image:` placeholder markers
**And** stdout does NOT include `"Images described:"`
**And** no vision LLM calls were attempted

**--no-ai Flag E2E:**

**Given** a Nest project is initialized
**And** a PDF containing images is placed in `_nest_sources/`
**And** AI environment variables ARE configured
**When** `nest sync --no-ai` is run
**Then** exit code is 0
**And** the output markdown contains `[Image:` placeholder markers
**And** no vision LLM calls were attempted

**Logo/Signature Skip E2E:**

**Given** a Nest project is initialized
**And** a PDF is placed in `_nest_sources/`
**And** Docling classifies an image as `logo` with confidence ≥ 0.5
**And** the vision LLM adapter is mocked
**When** `nest sync` is run
**Then** the mocked vision LLM was NOT called for the logo image
**And** stdout indicates images were skipped

**Token Reporting E2E:**

**Given** a Nest project is initialized
**And** a PDF containing images is placed in `_nest_sources/`
**And** the vision LLM adapter is mocked to return results with token counts
**When** `nest sync` is run
**Then** stdout sync summary includes token usage numbers
**And** the reported tokens include vision description tokens

**Incremental Sync E2E (no re-description on unchanged files):**

**Given** a Nest project has already synced a PDF with images (descriptions generated)
**When** `nest sync` is run again without modifying the source PDF
**Then** the file is skipped (unchanged checksum)
**And** no vision LLM calls are made for the already-processed file
**And** existing descriptions are preserved in the output markdown

---

## Epic 8: Developer Experience Polish

As a Nest user, I want the CLI to feel clean and professional, so I can focus on my documents rather than fighting tool friction.

**FRs covered:** FR39, FR40

**Scope:**
- Remove project name concept from `nest init` (no positional arguments)
- Suppress noisy third-party logging (Docling, httpx, openai) by default
- Add `--verbose` / `-v` flag to restore detailed logs for troubleshooting
- Clean console output: progress bar + summary only

**Dependencies:** Epic 2 (sync CLI), Epic 6 (AI enrichment), Epic 7 (vision pipeline)

---

### Story 8.1: Remove Project Name Concept

**As a** developer initialising a Nest project,
**I want** `nest init` to require no arguments,
**so that** I can run `nest init` from any folder and get going immediately.

**Acceptance Criteria:**

1. `nest init` takes no positional arguments and initializes successfully (exit 0)
2. `nest init some-name` exits with error code 2 (unexpected argument)
3. `--dir` flag still works
4. Manifest has no `project_name` field
5. Agent file uses generic description ("Expert analyst for documents in this project folder")
6. Master index header reads "# Nest Project Index"
7. `nest status` root label reads "📁 Nest Project"
8. `nest doctor --fix` rebuilds manifest without `project_name`

---

### Story 8.2: Suppress Third-Party Log Noise

**As a** Nest user running `nest sync`,
**I want** the terminal output to show only the progress bar and summary,
**so that** I'm not overwhelmed by hundreds of lines of framework internals.

**Acceptance Criteria:**

1. Third-party loggers (`docling`, `httpx`, `openai`, `PIL`, `urllib3`) suppressed to WARNING at CLI startup
2. `nest sync` shows only Rich progress bar and summary — no `INFO - Loading plugin`, `INFO - HTTP Request:`, etc.
3. `nest sync --verbose` (or `-v`) restores INFO-level logging for all namespaces
4. WARNING and ERROR logs still surface on console (only INFO noise removed)
5. Error log file (`.nest/errors.log`) unaffected — `setup_error_logger()` uses `propagate=False`

**Files Changed:**
- `src/nest/cli/main.py` — `_suppress_third_party_loggers()` called from `main()`
- `src/nest/cli/sync_cmd.py` — `--verbose` / `-v` flag added

---

## Epic 10: Multi-Agent Architecture

As a user working with project documents, I want a team of specialized AI agents instead of a single generalist, so that document research, synthesis, and planning tasks are handled by dedicated experts with better quality and reduced token usage.

**FRs covered:** FR41, FR42, FR43

**Scope:**
- Replace single `nest.agent.md` with a coordinator + 3 subagent architecture
- Coordinator orchestrates and delegates to: researcher, synthesizer, planner
- Subagents run in isolated VS Code context windows (parallel-capable)
- All 4 files generated during `nest init`, validated by `nest doctor`, migrated during `nest update`
- Legacy projects (single agent file) seamlessly upgraded via migration service

**Dependencies:** Epic 4 (agent migration infrastructure), Epic 8 (project name removal)

---

### Story 10.1: Multi-Agent Template Bundle

**As a** developer maintaining the Nest agent system,
**I want** the single agent template replaced with a coordinator + three subagent templates,
**so that** generated agent files use the new multi-agent architecture.

**Acceptance Criteria:**

1. Four Jinja templates exist: `coordinator.md.jinja`, `researcher.md.jinja`, `synthesizer.md.jinja`, `planner.md.jinja`
2. Old `vscode.md.jinja` is removed
3. Coordinator frontmatter includes `agents: ['nest-master-researcher', 'nest-master-synthesizer', 'nest-master-planner']`
4. All templates reference `.nest/00_MASTER_INDEX.md` for index and `.nest/glossary.md` for terminology
5. Subagent templates have `user-invokable: false` in frontmatter
6. `VSCodeAgentWriter` gains `render_all()` and `generate_all()` methods
7. Existing `render()` and `generate()` remain backward compatible
8. `AgentWriterProtocol` updated with new method signatures

---

### Story 10.2: Init & Doctor Multi-Agent Integration

**As a** user running `nest init` or `nest doctor --fix`,
**I want** all four agent files created and validated,
**so that** my project uses the full multi-agent architecture from day one.

**Acceptance Criteria:**

1. `nest init` creates all 4 agent files in `.github/agents/`
2. Init CLI output mentions multi-agent setup
3. `ProjectChecker.agent_file_exists()` returns `True` only when ALL 4 files exist
4. Doctor detects and reports which specific agent files are missing
5. `nest doctor --fix` regenerates all agent files (overwrites directly, no backups)
6. Legacy projects (single file) handled gracefully

---

### Story 10.3: Multi-Agent Migration Service

**As a** user running `nest update`,
**I want** the migration check to cover all four agent files,
**so that** after a version update, all my agent files stay in sync with the latest templates.

**Acceptance Criteria:**

1. `check_migration_needed()` compares ALL 4 local files against rendered templates
2. Result reports which specific files are outdated or missing
3. `execute_migration()` only regenerates changed/missing files (up-to-date files untouched)
4. No .bak backup files created (clean upgrade, no leftover files in agents directory)
5. Legacy projects with old single-file agent: old agent replaced with coordinator, 3 subagents created
6. CLI shows file-level detail (Replace/Create), single batch confirmation prompt
7. No-manifest scenario still skips check gracefully

---

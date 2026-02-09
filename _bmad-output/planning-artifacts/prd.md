# Product Requirement Document: Nest

| **Project Name** | Nest |
| :--- | :--- |
| **Version** | 1.0.0 |
| **Status** | **Draft / Ready for Development** |
| **Target User** | Project Teams, Analysts, Developers |
| **Platform** | macOS / Linux / Windows (via Python CLI) |
| **Integration** | VS Code (GitHub Copilot) |

---

## 1. Executive Summary
**Nest** is a lightweight CLI tool that creates a "Project Brain" from raw documents. It ingests project files (PDF, Excel, PPTX), converts them into AI-optimized Markdown, and generates a specialized **VS Code Copilot Agent** (`@nest`) that has deep knowledge of that specific project.

**Core Philosophy:** "Global Tool, Local Intelligence." The logic lives on the user's machine; the intelligence lives in the project's folder.

---

## 2. User Stories

### 2.1 The Setup
> As a user starting a new project, I want to run a single command to scaffold a "smart" folder structure so that I don't have to manually organize my files or write prompt instructions.

### 2.2 The Ingestion
> As a user with 50+ project PDFs, I want to drop them into a folder and have them automatically converted into clean, readable text so that my AI agent can actually understand them without hallucinations.

### 2.3 The Interaction
> As a developer working in VS Code, I want to select a `@nest` agent from my Copilot dropdown when I have a specific question about the project's documents, but I want to switch back to the standard `@workspace` agent when I am just writing Python code, so I don't get irrelevant context.

---

## 3. Technical Architecture

### 3.1 The "Sidecar" Pattern
Nest operates as a global CLI that manages local files. It does not run a background daemon.

```text
my-project/
├── .github/
│   └── agents/
│       └── nest.agent.md       <-- The "Persona" (VS Code picks this up automatically)
├── _nest_sources/              <-- User Input (PDFs, XLSX, etc. for processing)
└── _nest_context/              <-- AI Knowledge Base (Generated + User-Curated)
    ├── 00_MASTER_INDEX.md      <-- The Map
    ├── policy_v1.md            <-- Generated from sources
    ├── developer-guide.md      <-- User-added (.md, no processing needed)
    ├── api-reference.yaml      <-- User-added (.yaml, included in index)
    ├── meeting-notes.txt       <-- User-added (.txt, included in index)
    └── financial_data.md       <-- Generated from sources
```

### 3.2 The Technology Stack
* **Language:** Python 3.10+
* **Distribution:** `uv` (for isolated, single-command installation).
* **PDF/Doc Engine:** **Docling** (IBM) – *Chosen for local-first, privacy-safe, superior table extraction.*
* **CLI Framework:** `Typer` + `Rich` (for beautiful terminal output).

### 3.3 Distribution & Installation

**Prerequisites:**
* `uv` must be installed on the user's machine. Users without `uv` should follow [uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/).

**Distribution Channel:**
* Primary: Public GitHub repository.
* Installation command: `uv tool install git+https://github.com/jbjornsson/nest`

**First-Run Model Download:**
* Docling requires ML models (~1.5-2GB) for document processing.
* Models are downloaded **once** during `nest init` and cached locally.
* Subsequent projects reuse cached models (no re-download).
* If models are already cached, `nest init` completes in seconds.

**Model Cache Location:**
* macOS/Linux: `~/.cache/docling/`
* Windows: `%LOCALAPPDATA%\docling\`

---

## 4. Feature Specifications

### 4.1 Command: `nest init`
**Trigger:** `nest init "Project Name" [OPTIONS]`

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--dir`, `-d` | Current directory | Target directory for project initialization |

**Behavior:**
1.  Creates directories: `_nest_sources/`, `_nest_context/`.
2.  Creates `.github/agents/nest.agent.md`.
3.  Creates `.nest_manifest.json` (empty manifest).
4.  Downloads Docling ML models if not already cached (first-time only, ~1.5-2GB).
5.  **Crucial:** The agent file must use the specific **VS Code Custom Agent** format (Frontmatter + Instructions).

**First-Run Experience:**
```
$ nest init "Nike"
[•] Creating project structure... ✓
[•] Downloading ML models (first-time setup)...
    ├─ TableFormer: 892MB [████████████████████] 100%
    └─ LayoutLM: 645MB [████████████████████] 100%
[•] Models cached at ~/.cache/docling/
[✓] Project "Nike" initialized. Ready to sync!
```

**Output File (`.github/agents/nest.agent.md`):**
```markdown
---
name: nest
description: Expert analyst for [Project Name] project documents
icon: book
---

# Nest — Project Document Analyst

You are an expert document analyst specialized in the [Project Name] project. Your role is to help users understand, search, and extract insights from project documents.

## Core Responsibilities

1. **Start with the Index:** Always begin by reading `_nest_context/00_MASTER_INDEX.md` to understand available documents
2. **Cite Sources:** When answering, always cite the specific filename(s) used
3. **Navigate Structure:** Documents mirror the structure in `_nest_sources/` — use this to find related files
4. **Stay Focused:** Never read `_nest_sources/` (raw documents) or system files (`.nest_manifest.json`, `.nest_errors.log`)

## Response Guidelines

- **Found Information:** Provide answer with clear citations: "According to contracts/acme-sow-v2.md..."
- **Not Found:** Be honest: "I cannot find information about X in the available documents. I checked: [list files]."
- **Multiple Sources:** When information spans files, cite all relevant sources
- **Clarification Needed:** Ask clarifying questions if the user's query is ambiguous

## Technical Context

- All files in `_nest_context/` are Markdown conversions of original documents or user-curated content
- Tables from PDFs/Excel are converted to Markdown table format
- File paths are relative to `_nest_context/` directory
- The index is regenerated after each `nest sync` command
- User-curated files may be any supported text format: `.md`, `.txt`, `.text`, `.rst`, `.csv`, `.json`, `.yaml`, `.yml`, `.toml`, `.xml`

## Example Interactions

**User:** "What's the T&M rate cap in the SOW?"
**You:** "According to `contracts/acme-sow-v2.md` (Section 4.2), the blended T&M rate is capped at $185/hour, with a 3% annual escalation clause. (Source: contracts/acme-sow-v2.md)"

**User:** "What did we commit to in the RFP response about data migration?"
**You:** "In `rfp-response/technical-approach.md` (Section 3.4), we committed to: 1) Full historical data migration for the past 7 years, 2) Data validation with <0.1% error tolerance, 3) Parallel run period of 30 days. (Source: rfp-response/technical-approach.md)"

**User:** "What were the key risks identified in discovery?"
**You:** "I found risk assessments in `discovery/current-state-assessment.md` and `discovery/stakeholder-interviews.md`. The top risks identified were: [details from both sources]."

**User:** "When is the go-live date?"
**You:** "I cannot find a specific go-live date in the available documents. I checked the SOW, project charter, and status reports. Would you like me to search for milestone or timeline information instead?"

---

**Remember:** Your strength is thorough document analysis with accurate citations. Always be precise, cite sources, and honest about limitations.
```

### 4.2 Command: `nest sync`
**Trigger:** `nest sync [OPTIONS]`

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--on-error` | `skip` | Error handling: `skip` (continue processing), `fail` (abort on first error) |
| `--no-clean` | (clean is ON) | Disable orphan cleanup (by default, files are removed from `_nest_context/` when source is deleted) |
| `--dry-run` | `false` | Show what would be processed without making changes |
| `--force` | `false` | Re-process all files regardless of checksum (ignore manifest) |
| `--dir`, `-d` | Current directory | Target directory for sync operation |

**Behavior:**
1.  **Scan:** Recursively scans `_nest_sources/` for supported files (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`).
2.  **Checksum Comparison:** For each file, compute SHA-256 hash and compare against `.nest_manifest.json`:
    * **New file** (not in manifest) → Process and save.
    * **Modified file** (hash differs) → Re-process and overwrite.
    * **Unchanged file** (hash matches) → Skip (saves time).
3.  **Processing Loop:**
    * Runs `Docling` to convert file → Markdown.
    * Saves plain Markdown to `_nest_context/` **mirroring the source folder hierarchy**.
    * (No YAML header in output — metadata lives only in manifest.)
4.  **Orphan Cleanup:** By default, removes files from `_nest_context/` **that are tracked in the manifest** whose source no longer exists in `_nest_sources/`. Files not in the manifest (user-curated) are never touched. Disable with `--no-clean`.
5.  **Index Generation:** Regenerates `00_MASTER_INDEX.md` with file listing from entire `_nest_context/` directory. Includes both Docling-generated files and user-curated plain text files. Supported context text extensions: `.md`, `.txt`, `.text`, `.rst`, `.csv`, `.json`, `.yaml`, `.yml`, `.toml`, `.xml`. Binary or unsupported file types placed in `_nest_context/` are excluded from the index.
6.  **Manifest Update:** Updates `.nest_manifest.json` with processed file metadata.

**Directory Mirroring Example:**
```
_nest_sources/                  _nest_context/
├── contracts/                  ├── contracts/
│   ├── 2024/                   │   ├── 2024/
│   │   └── alpha.pdf     →     │   │   └── alpha.md
│   └── 2025/                   │   └── 2025/
│       └── beta.pdf      →     │       └── beta.md
├── reports/                    ├── reports/
│   └── Q3_summary.xlsx   →     │   └── Q3_summary.md
└── (manual text files go       └── developer-guide.md  <-- User-curated (.md)
    directly in _nest_context/)    onboarding.txt      <-- User-curated (.txt)
                                   api-spec.yaml       <-- User-curated (.yaml)
```

**Manifest Schema (`.nest_manifest.json`):**
```json
{
  "nest_version": "1.0.0",
  "project_name": "Nike",
  "last_sync": "2026-01-11T14:30:00Z",
  "files": {
    "contracts/2024/alpha.pdf": {
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "processed_at": "2026-01-11T14:30:00Z",
      "output": "_nest_context/contracts/2024/alpha.md",
      "status": "success"
    },
    "reports/Q3_summary.xlsx": {
      "sha256": "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592",
      "processed_at": "2026-01-11T14:30:00Z",
      "output": "_nest_context/reports/Q3_summary.md",
      "status": "success"
    }
  }
}
```

### 4.3 Command: `nest status`
**Trigger:** `nest status [OPTIONS]`

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--dir`, `-d` | Current directory | Target directory for status operation |
**Behavior:** Displays current project state at a glance.

**Example Output:**
```
📁 Project: Nike
   Nest Version: 1.0.0

   Sources:
   ├─ Total files: 47
   ├─ New: 12
   ├─ Modified: 3
   └─ Unchanged: 32

   Context:
   ├─ Files: 32
   ├─ Orphaned: 2
   └─ Last sync: 2 hours ago

   Run `nest sync` to process 15 pending files.
```

**Implementation Note (DRY Principle):**
The following operations must be implemented as **reusable internal components** shared across commands:
| Component | Used By |
|-----------|---------|
| `download_models()` | `nest init` |
| `build_manifest()` | `nest init`, `nest sync` |
| `generate_agent_file()` | `nest init` |
| `compute_checksum()` | `nest sync`, `nest status` |
| `generate_index()` | `nest sync` |
| `CONTEXT_TEXT_EXTENSIONS` | `nest sync` (index), `nest status` (counting), orphan service (user-curated counting) |

---

## 5. User Experience (UX) Flow

**Step 1: Installation (One-time)**
User runs:
`curl -LsSf https://.../install.sh | sh`

**Step 2: Starting a Project**
```bash
mkdir nike-project
cd nike-project
nest init "Nike"
```
*Result:* Folders created. Agent installed.

**Step 3: Adding Data**
* User drags 10 PDF contracts into `_nest_sources`.
* User runs: `nest sync`
* *Terminal:* `[Green Check] Processed 10 files. Master Index updated.`

**Step 4: Using the Agent**
* User opens VS Code.
* User opens Copilot Chat.
* User types `@nest What is the termination clause in the Alpha contract?`
* **Result:** Copilot (acting as `@nest`) reads the Master Index, finds `contract_alpha.md`, reads it, and answers with citations.

---

## 6. Implementation Guidelines (For the Analyst Agent)

### 6.1 Docling Implementation Details
* **Tables:** Enable `TableFormer` mode in Docling to ensure Excel/PDF tables are converted to Markdown tables, not just raw text.
* **Chunking:** For V1, do **not** chunk files. Save 1 Source File = 1 Markdown File. Rely on Gemini/Copilot's long context window (128k+) to read the full file.
* **Images:** Ignore images for V1 to keep speed high. (Roadmap Item: Use GPT-4o to caption images).

### 6.2 Agent File Naming
* **Must use:** `.github/agents/*.agent.md`
* **Reason:** This is the specific path VS Code looks for to populate the "Participant" dropdown (the `@` menu).

### 6.3 Security & Privacy
* **Local Only:** Ensure `Docling` is running with `artifacts_path` set to a local cache, so it doesn't try to download models every run.
* **Gitignore:** The `init` command should check if a `.gitignore` exists. If so, it should append:
    ```text
    _nest_sources/
    # We commit _nest_context/ so the team shares the brain
    # We DO NOT commit _nest_sources/ (often too large/sensitive)
    ```

### 6.4 Error Handling

| Scenario | Default Behavior | `--on-error=fail` Behavior |
|----------|------------------|---------------------------|
| Corrupt/unparseable PDF | Log warning, skip file, continue | Abort sync, exit code 1 |
| Password-protected file | Log warning, skip file, continue | Abort sync, exit code 1 |
| Encoding issues (non-UTF8) | Attempt fallback encodings, then skip | Abort sync, exit code 1 |
| Disk full | Abort sync, exit code 1 | Abort sync, exit code 1 |
| `nest sync` outside project | Error: "No Nest project found. Run `nest init` first." | Same |
| File already in output | Overwrite (default), or respect `--on-conflict` flag | Same |
| Network timeout (model download) | Retry 3x, then fail with instructions | Same |

**Error Logging:**
* All errors are logged to `.nest_errors.log` in the project root.
* Summary shown at end of sync: `Processed 45/47 files. 2 errors (see .nest_errors.log)`

### 6.5 E2E Testing Requirements

**NFR11: End-to-End Testing**

Nest requires E2E tests that validate full CLI command flows with real file I/O and actual Docling processing.

| Test Layer | Purpose | Required |
|------------|---------|----------|
| Unit | Pure functions, business logic | ✅ |
| Integration | Service orchestration with mocked I/O | ✅ |
| **E2E** | Full CLI invocation, real Docling | ✅ |

**E2E Test Commands:**
- `pytest -m "not e2e"` — Fast tests for dev loop
- `pytest -m "e2e" --timeout=60` — Full E2E validation

**Story Completion Gate:** A story is NOT complete until all E2E tests pass. When adding new CLI logic, developers MUST evaluate if new E2E tests are needed.

**Skip Condition:** E2E tests automatically skip if Docling models are not downloaded, preventing CI failures in environments without models.

---

### 6.6 Team Usage Guidance

**Recommended Workflow:**
1. **Commit `processed_context/`** — This is the shared "brain" for the team.
2. **Do NOT commit `raw_inbox/`** — Often contains large/sensitive source files.
3. **One sync at a time** — Avoid running `nest sync` simultaneously from multiple machines on the same repo.
4. **Pull before sync** — When teammates have added new processed files, `git pull` first to avoid conflicts.

**Conflict Resolution:**
* If two teammates process the same new file, Git will show a merge conflict in `processed_context/`.
* Resolution: Keep either version (content should be identical) or re-run `nest sync --clean`.

### 6.6 Agent Context Management

**The Problem:** LLMs have limited context windows. Reading a large index file on every query wastes tokens.

**Solution: Lazy Index Loading**
The agent instructions are designed so that:
1. The `00_MASTER_INDEX.md` is read **once** when the user first invokes `@nest`.
2. The index remains in the conversation context for subsequent queries.
3. The agent only fetches specific files as needed.

**Master Index Format (Optimized for Token Efficiency):**
```markdown
# Nest Project Index: Nike
Generated: 2026-01-11T14:30:00Z | Files: 47

## File Listing
contracts/2024/alpha.md
contracts/2024/beta.md
contracts/2025/gamma.md
reports/Q3_summary.md
reports/Q4_forecast.md
policies/hr_handbook.md
```

**Design Rationale:**
* One file per line — minimal tokens, easy to scan.
* No summaries in V1 — keeps index small (<1KB for 100 files).
* Flat list with paths — agent can infer structure from path names.
* Timestamp + count — helps agent understand freshness.

**Context Window Math:**
* 100 files × ~40 chars avg path = ~4KB = ~1,000 tokens
* Well within single-read budget for 128K context models.

---

## 7. Roadmap (Post-V1)
* **`nest doctor` Command:** Validate environment, ML models, manifest integrity, and agent file presence. Offer to fix detected issues.
* **`nest upgrade` Command:** Run `uv tool upgrade nest`, check for agent template updates, and handle manifest migrations.
* **Image Captioning:** Use a local VLM or API to describe charts in PDFs.
* **Recursive Sync:** Watch the folder for changes automatically (Daemon mode).
* **Semantic Search:** Generate a local vector index (ChromaDB) for projects with >1000 files where linear scanning of `MASTER_INDEX` fails.
# Product Requirement Document: Nest

| **Project Name** | Nest |
| :--- | :--- |
| **Version** | 1.0.0 |
| **Status** | **Draft / Ready for Development** |
| **Target User** | Consultants, Analysts, Developers |
| **Platform** | macOS / Linux / Windows (via Python CLI) |
| **Integration** | VS Code (GitHub Copilot) |

---

## 1. Executive Summary
**Nest** is a lightweight CLI tool that creates a "Project Brain" from raw documents. It ingests client files (PDF, Excel, PPTX), converts them into AI-optimized Markdown, and generates a specialized **VS Code Copilot Agent** (`@nest`) that has deep knowledge of that specific project.

**Core Philosophy:** "Global Tool, Local Intelligence." The logic lives on the user's machine; the intelligence lives in the client's folder.

---

## 2. User Stories

### 2.1 The Setup
> As a consultant starting a new project, I want to run a single command to scaffold a "smart" folder structure so that I don't have to manually organize my files or write prompt instructions.

### 2.2 The Ingestion
> As a user with 50+ client PDFs, I want to drop them into a folder and have them automatically converted into clean, readable text so that my AI agent can actually understand them without hallucinations.

### 2.3 The Interaction
> As a developer working in VS Code, I want to select a `@nest` agent from my Copilot dropdown when I have a specific question about the client's documents, but I want to switch back to the standard `@workspace` agent when I am just writing Python code, so I don't get irrelevant context.

---

## 3. Technical Architecture

### 3.1 The "Sidecar" Pattern
Nest operates as a global CLI that manages local files. It does not run a background daemon.

```text
my-client-project/
├── .github/
│   └── agents/
│       └── nest.agent.md       <-- The "Persona" (VS Code picks this up automatically)
├── raw_inbox/                  <-- User Input (PDFs, XLSX)
└── processed_context/          <-- System Output (AI Knowledge Base)
    ├── 00_MASTER_INDEX.md      <-- The Map
    ├── policy_v1.md
    └── financial_data.md
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
* Primary: Corporate Azure DevOps Git repository (internal distribution).
* Installation command: `uv tool install git+https://dev.azure.com/org/project/_git/nest`

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
**Trigger:** `nest init "Client Name"`
**Behavior:**
1.  Creates directories: `raw_inbox/`, `processed_context/`.
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
description: Expert analyst for [Client Name] project documents
icon: book
---
# ROLE
You are the dedicated AI analyst for [Client Name].
Your goal is to assist the user by navigating and synthesizing the project documentation located in `processed_context/`.

# KNOWLEDGE BASE
- Your entire world of knowledge is located in the `processed_context/` directory.
- **STEP 1:** Always read `processed_context/00_MASTER_INDEX.md` first to understand what files are available.
- **STEP 2:** Retrieve the specific files you need to answer the user's question.

# BEHAVIOR
- **Citation:** Always cite the filename you used (e.g. "Source: `Q3_Report.md`").
- **Honesty:** If the information is not in the files, state "I cannot find that in the provided documents."
- **Focus:** Do not offer general coding advice unless it relates to the project context.

# FORBIDDEN FILES (Never Read These)
Your context window is precious. These files contain no useful content for answering user questions:

**Nest System Files:**
- `.nest_manifest.json` — CLI metadata, just checksums and timestamps
- `.nest_errors.log` — Internal error log

**Raw Source Files:**
- `raw_inbox/**` — Never read files from this folder. Always use the processed Markdown versions in `processed_context/` instead. The raw files are PDFs/Excel/etc. that you cannot parse properly.

**If you find yourself wanting to read any of these, STOP and reconsider. The answer to the user's question is in `processed_context/`.**
```

### 4.2 Command: `nest sync`
**Trigger:** `nest sync [OPTIONS]`

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--on-error` | `skip` | Error handling: `skip` (continue processing), `fail` (abort on first error) |
| `--no-clean` | (clean is ON) | Disable orphan cleanup (by default, files are removed from `processed_context/` when source is deleted) |
| `--dry-run` | `false` | Show what would be processed without making changes |
| `--force` | `false` | Re-process all files regardless of checksum (ignore manifest) |

**Behavior:**
1.  **Scan:** Recursively scans `raw_inbox/` for supported files (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`).
2.  **Checksum Comparison:** For each file, compute SHA-256 hash and compare against `.nest_manifest.json`:
    * **New file** (not in manifest) → Process and save.
    * **Modified file** (hash differs) → Re-process and overwrite.
    * **Unchanged file** (hash matches) → Skip (saves time).
3.  **Processing Loop:**
    * Runs `Docling` to convert file → Markdown.
    * Saves plain Markdown to `processed_context/` **mirroring the source folder hierarchy**.
    * (No YAML header in output — metadata lives only in manifest.)
4.  **Orphan Cleanup:** By default, removes files from `processed_context/` whose source no longer exists in `raw_inbox/`. Disable with `--no-clean`.
5.  **Index Generation:** Regenerates `00_MASTER_INDEX.md` with file listing.
6.  **Manifest Update:** Updates `.nest_manifest.json` with processed file metadata.

**Directory Mirroring Example:**
```
raw_inbox/                      processed_context/
├── contracts/                  ├── contracts/
│   ├── 2024/                   │   ├── 2024/
│   │   └── alpha.pdf     →     │   │   └── alpha.md
│   └── 2025/                   │   └── 2025/
│       └── beta.pdf      →     │       └── beta.md
└── reports/                    └── reports/
    └── Q3_summary.xlsx   →         └── Q3_summary.md
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
      "output": "processed_context/contracts/2024/alpha.md",
      "status": "success"
    },
    "reports/Q3_summary.xlsx": {
      "sha256": "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592",
      "processed_at": "2026-01-11T14:30:00Z",
      "output": "processed_context/reports/Q3_summary.md",
      "status": "success"
    }
  }
}
```

### 4.3 Command: `nest upgrade`
**Trigger:** `nest upgrade`
**Behavior:**
1.  Runs `uv tool upgrade nest`.
2.  Checks if the local `.github/agents/nest.agent.md` is outdated compared to the latest template.
3.  If outdated, prompts: `Agent template has changed. Update? [y/N]`
4.  Checks manifest version and warns if migration is needed.

### 4.4 Command: `nest status`
**Trigger:** `nest status`
**Behavior:** Displays current project state at a glance.

**Example Output:**
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
   ├─ Orphaned:        2  (source deleted, run --clean to remove)
   └─ Last sync:       2 hours ago

   Run `nest sync` to process 15 pending files.
```

### 4.5 Command: `nest doctor`
**Trigger:** `nest doctor`
**Behavior:** Validates environment and dependencies.

**Example Output:**
```
🩺 Nest Doctor

   Environment:
   ├─ Python:         3.11.4 ✓
   ├─ uv:             0.4.12 ✓
   └─ Nest:           1.0.0 ✓

   ML Models:
   ├─ TableFormer:    cached ✓ (892MB)
   ├─ LayoutLM:       cached ✓ (645MB)
   └─ Cache path:     ~/.cache/docling/

   Project:
   ├─ Manifest:       valid ✓
   ├─ Agent file:     present ✓
   └─ Folders:        intact ✓

   ✓ All systems operational.
```

**Error States Detected:**
* Missing ML models → offers to download
* Corrupt manifest → offers to rebuild
* Missing agent file → offers to regenerate
* Version mismatch → suggests `nest upgrade`

**Implementation Note (DRY Principle):**
The following operations must be implemented as **reusable internal components** shared across commands:
| Component | Used By |
|-----------|---------|
| `download_models()` | `nest init`, `nest doctor` |
| `build_manifest()` | `nest init`, `nest sync`, `nest doctor` |
| `generate_agent_file()` | `nest init`, `nest doctor`, `nest upgrade` |
| `compute_checksum()` | `nest sync`, `nest status` |
| `generate_index()` | `nest sync` |

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
* User drags 10 PDF contracts into `raw_inbox`.
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
    raw_inbox/
    # We commit processed_context so the team shares the brain
    # We DO NOT commit raw_inbox (often too large/sensitive)
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

### 6.5 Team Usage Guidance

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
* **Image Captioning:** Use a local VLM or API to describe charts in PDFs.
* **Recursive Sync:** Watch the folder for changes automatically (Daemon mode).
* **Semantic Search:** Generate a local vector index (ChromaDB) for projects with >1000 files where linear scanning of `MASTER_INDEX` fails.
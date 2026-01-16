# Nest 🪺

**Turn your project documents into an AI-powered knowledge base for VS Code Copilot.**

Drop PDFs, Excel files, and PowerPoints into a folder. Nest converts them to Markdown and creates a custom **Nest** agent that knows your project inside and out.

```
[Copilot Chat with Nest agent selected]

You: What authentication method did we agree on for the partner API?
AI:  The integration spec requires OAuth 2.0 with client credentials flow.
     Token lifetime is 1 hour, refresh not supported... [Source: specs/partner-api-v2.md]
```

---

## What Nest Does

1. **Converts documents** — PDFs, DOCX, PPTX, XLSX, HTML → clean Markdown
2. **Creates a VS Code agent** — Select "Nest" from the Copilot Chat agent dropdown
3. **Tracks changes** — Only re-processes modified files (fast incremental syncs)
4. **Builds an index** — Your AI agent knows exactly what files exist and where

**Core Philosophy:** *"Global tool, local intelligence."* Nest runs on your machine; the knowledge lives in your project folder.

---

## Prerequisites

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — Astral's fast Python package manager

---

## Installation

```bash
uv tool install git+https://github.com/jbb10/nest
```

---

## Quick Start

```bash
# 1. Create and enter your project folder
mkdir acme-digital-transformation && cd acme-digital-transformation

# 2. Initialize Nest (downloads ML models on first run)
nest init "Acme Digital Transformation"

# 3. Drop documents into raw_inbox/
cp ~/Downloads/acme-sow.pdf ~/Downloads/acme-msa.pdf raw_inbox/
cp -r ~/Downloads/rfp-response/ raw_inbox/

# 4. Process everything
nest sync

# 5. Open VS Code, launch Copilot Chat, select "Nest" from the agent dropdown
```

### First-Run Note
The first time you run `nest init`, Docling downloads ML models (~1.5-2GB). This is a **one-time download** cached at `~/.cache/docling/`. Subsequent projects start instantly.

---

## Commands

### `nest init "Project Name"`

Scaffolds a new Nest project:

```
my-project/
├── .github/agents/nest.agent.md   ← VS Code shows this in agent dropdown
├── raw_inbox/                      ← Put your source documents here
├── processed_context/              ← AI-readable Markdown output
└── .nest_manifest.json             ← Tracks what's been processed
```

### `nest sync`

Processes new and changed documents.

| Flag | Default | Description |
|------|---------|-------------|
| `--on-error` | `skip` | `skip` = continue on errors, `fail` = abort on first error |
| `--no-clean` | clean ON | Disable orphan cleanup (keeps output files when source is deleted) |
| `--dry-run` | `false` | Preview what would be processed without making changes |
| `--force` | `false` | Re-process all files, ignoring checksums |

**Examples:**
```bash
nest sync                    # Normal incremental sync
nest sync --dry-run          # See what would happen
nest sync --force            # Re-process everything
nest sync --on-error fail    # Stop on first error
```

### `nest status`

Shows project state at a glance:

```
📁 Project: Acme Digital Transformation
   
   Raw Inbox:
   ├─ Total files:    47
   ├─ New:            12  (not yet processed)
   ├─ Modified:        3  (changed since last sync)
   └─ Unchanged:      32

   Processed Context:
   ├─ Files:          32
   └─ Last sync:       2 hours ago

   Run `nest sync` to process 15 pending files.
```

### `nest doctor`

Validates your environment:

```
🩺 Nest Doctor

   Environment:
   ├─ Python:         3.11.4 ✓
   ├─ uv:             0.4.12 ✓
   └─ Nest:           1.0.0 ✓

   ML Models:
   ├─ TableFormer:    cached ✓
   ├─ LayoutLM:       cached ✓
   └─ Cache path:     ~/.cache/docling/

   ✓ All systems operational.
```

### `nest update`

Updates Nest and migrates your agent file if the template has changed.

---

## Getting the Most Out of Nest

### Supported File Types
- PDF (including scanned documents with tables)
- Microsoft Word (.docx)
- Microsoft Excel (.xlsx)
- Microsoft PowerPoint (.pptx)
- HTML

### Directory Structure is Preserved

```
raw_inbox/                          processed_context/
├── contracts/                      ├── contracts/
│   ├── acme-msa.pdf          →     │   ├── acme-msa.md
│   └── acme-sow-v2.pdf       →     │   └── acme-sow-v2.md
├── discovery/                      ├── discovery/
│   ├── stakeholder-interviews.docx │   ├── stakeholder-interviews.md
│   └── current-state-assessment.pptx│   └── current-state-assessment.md
└── status-reports/                 └── status-reports/
    └── steering-committee-jan.pptx →   └── steering-committee-jan.md
```

Organize your `raw_inbox/` however you like—Nest mirrors the structure in `processed_context/`.

### Team Workflow

| Do | Don't |
|----|-------|
| ✅ Commit `processed_context/` | ❌ Commit `raw_inbox/` (too large for git) |
| ✅ `git pull` before `nest sync` | ❌ Run `nest sync` simultaneously from multiple machines |
| ✅ Share the "brain" with your team | ❌ Keep processed files only locally |

### Tips for Better Results

1. **Use descriptive filenames** — `acme-sow-v2.pdf` beats `Document1.pdf`
2. **Organize by workstream** — `discovery/`, `contracts/`, `deliverables/`, `status-reports/`
3. **Include RFP responses** — Great for remembering what you promised the client
4. **Add meeting decks** — Steering committee slides often contain key decisions
5. **Check the master index** — `processed_context/00_MASTER_INDEX.md` shows everything available

---

## How It Works

```
┌─────────────────┐     ┌─────────────┐     ┌──────────────────────┐
│   raw_inbox/    │ ──► │   Docling   │ ──► │  processed_context/  │
│  (PDF, XLSX..)  │     │  (local ML) │     │     (Markdown)       │
└─────────────────┘     └─────────────┘     └──────────────────────┘
                                                      │
                                                      ▼
                                            ┌──────────────────────┐
                                            │   Nest agent reads   │
                                            │  00_MASTER_INDEX.md  │
                                            │  then fetches files  │
                                            └──────────────────────┘
```

**Privacy:** All processing happens locally via [Docling](https://github.com/DS4SD/docling). No documents are sent to external services.

---

## Development

```bash
# Clone and install
git clone https://github.com/jbb10/nest
cd nest
uv sync

# Run tests
pytest

# Linting
ruff check .

# Type checking
pyright
```

---

## License

MIT

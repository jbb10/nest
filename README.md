# Nest

**Turn your project documents into an AI-powered knowledge base for VS Code Copilot.**

Drop PDFs, Excel files, and PowerPoints into a folder. Nest converts them to Markdown and creates a custom **Nest** agent that knows your project inside and out.

```
[Copilot Chat with Nest agent selected]

You: What authentication method did we agree on for the partner API?
Nest: The integration spec requires OAuth 2.0 with client credentials flow.
      Token lifetime is 1 hour, refresh not supported... [Source: specs/partner-api-v2.md]

You: Build me a migration plan from the legacy system
Nest: [Delegates to researcher → synthesizer → planner agents automatically]
      Here's a phased migration plan based on your SOW and architecture docs...
```

---

## What It Does

- **Converts documents** — PDFs, DOCX, PPTX, XLSX, HTML → clean Markdown (via [Docling](https://github.com/DS4SD/docling), fully local)
- **Creates VS Code agents** — A multi-agent team: coordinator, researcher, synthesizer, and planner
- **Tracks changes** — Only re-processes modified files (fast incremental syncs)
- **AI-powered context** — Optionally connects to an LLM to generate image descriptions and a project glossary, giving your agents richer understanding of your documents
- **Self-updates** — `nest update` keeps the tool and agent template current

All processing happens on your machine. No documents are sent to external services.

---

## Installation

**Requires [Python 3.10+](https://www.python.org/) and [uv](https://docs.astral.sh/uv/getting-started/installation/).**

```bash
uv tool install git+https://github.com/jbb10/nest
```

### Updating

```bash
# Recommended
nest update

# Or manually via uv
uv tool upgrade nest
```

---

## Quick Start

```bash
# 1. Create and enter your project folder
mkdir acme-project && cd acme-project

# 2. Initialize Nest (downloads ML models on first run, ~1.5 GB one-time)
nest init

# 3. Drop documents into _nest_sources/
cp ~/Downloads/acme-sow.pdf ~/Downloads/acme-msa.pdf _nest_sources/
cp -r ~/Downloads/rfp-response/ _nest_sources/

# 4. Process everything
nest sync

# 5. Open VS Code → Copilot Chat → select "Nest" from the agent dropdown
#    (The coordinator automatically delegates to researcher, synthesizer, and planner agents)
```

---

## Commands

### `nest init`

Scaffolds a new Nest project in the current directory:

```
my-project/
├── .github/agents/
│   ├── nest.agent.md                        ← Coordinator (select from agent dropdown)
│   ├── nest-master-researcher.agent.md      ← Deep document research
│   ├── nest-master-synthesizer.agent.md     ← Cross-document synthesis
│   └── nest-master-planner.agent.md         ← Action plans and roadmaps
├── _nest_sources/                           ← Put ALL your documents here (PDFs, text files, etc.)
├── _nest_context/                           ← AI-readable output (converted Markdown + passthrough copies)
└── .nest/                                   ← Metadata directory
    ├── manifest.json                        ← Tracks what's been processed
    ├── errors.log                           ← Error diagnostics
    └── 00_MASTER_INDEX.md                   ← Auto-generated index of all context files
```

### `nest sync`

Processes new and changed documents.

AI description generation and glossary creation run automatically only when AI is configured.
Use `nest config ai` or set `NEST_API_KEY` or `OPENAI_API_KEY` before running `nest sync`.
Without AI configuration, sync still completes, but index descriptions may be blank and `glossary.md` will not be created.

| Flag | Default | Description |
|------|---------|-------------|
| `--on-error` | `skip` | `skip` = continue on errors, `fail` = abort on first error |
| `--no-clean` | clean ON | Disable orphan cleanup (keeps output when source is deleted) |
| `--dry-run` | off | Preview what would be processed without making changes |
| `--force` | off | Re-process all files, ignoring checksums |
| `--no-ai` | off | Skip AI enrichment even when AI credentials are configured |

```bash
nest sync                    # Normal incremental sync
nest sync --dry-run          # See what would happen
nest sync --force            # Re-process everything
nest sync --on-error fail    # Stop on first error
```

### `nest status`

Shows project state at a glance — pending files, last sync time, and what to do next.

### `nest doctor`

Validates your environment, ML models, and project state.

| Flag | Description |
|------|-------------|
| `--fix` | Automatically fix detected issues (re-download models, regenerate manifest, etc.) |

### `nest update`

Checks for new versions, updates Nest, and migrates your agent file if the template has changed.

| Flag | Description |
|------|-------------|
| `--check` | Only check for updates without installing |
| `--dir` | Specify project directory for agent migration check |

### `nest config ai`

Interactively configures AI enrichment by writing API credentials to your shell RC file (e.g. `~/.zshrc`). Prompts for API endpoint, model name, and API key.

Once configured, `nest sync` will automatically generate file descriptions and a project glossary that help your agents understand your documents better.

```bash
nest config ai            # Set up AI credentials
nest config ai --remove   # Remove AI configuration
```

| Flag | Description |
|------|-------------|
| `--remove` | Remove Nest AI configuration from your shell RC file |

---

## Supported File Types

| Format | Extensions |
|--------|-----------|
| PDF | `.pdf` (including scanned documents with tables) |
| Microsoft Word | `.docx` |
| Microsoft Excel | `.xlsx` |
| Microsoft PowerPoint | `.pptx` |
| HTML | `.html` |

You can also place Markdown, text, CSV, JSON, YAML, and other text files into `_nest_sources/` — they'll be copied through to `_nest_context/` as-is and picked up by the master index automatically.

---

## How It Works

```
┌──────────────────┐     ┌─────────────┐     ┌───────────────────┐
│  _nest_sources/  │ ──► │   Docling   │ ──► │  _nest_context/   │
│  (PDF, XLSX..)   │     │  (local ML) │     │   (Markdown)      │
└──────────────────┘     └─────────────┘     └───────────────────┘
                                                      │
                                                      ▼
                                            ┌───────────────────┐
                                            │  Nest agent reads │
                                            │ 00_MASTER_INDEX.md│
                                            │ then fetches files│
                                            └───────────────────┘
```

Directory structure is preserved — organize `_nest_sources/` however you like and Nest mirrors it in `_nest_context/`.

### Tips

- **Use descriptive filenames** — `acme-sow-v2.pdf` beats `Document1.pdf`
- **Organize by area/domain** — `discovery/`, `contracts/`, `deliverables/`

### Team Workflow

Nest projects are designed to be committed to git. The source documents, manifest, context output, and agent file should all be version-controlled so the whole team shares the same knowledge base.

Pull before syncing to avoid conflicts when multiple people add documents.

---

## Contributing

This project uses the [BMad Method](https://github.com/bmadcode/BMAD-METHOD) for planning and development. All contributions must follow the BMad workflow — epics, stories, and sprint status are tracked in `_bmad-output/`, and work is driven through the SM and Dev agents.

```bash
# Clone and install
git clone https://github.com/jbb10/nest
cd nest
uv sync

# Run tests (581 tests)
uv run pytest

# Lint
uv run ruff check .

# Type check
uv run pyright
```

The codebase uses a **protocol-based dependency injection** pattern — adapters implement protocols, services consume them. See `src/nest/adapters/protocols.py` for the interface definitions.

**Branching:** Feature branches off `main`, merged via PR. Use `feat/`, `fix/`, or `chore/` prefixes.

---

## License

MIT

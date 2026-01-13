# Nest

AI-powered document context tool for consultants.

## Overview

Nest processes project documents (PDFs, Excel, PowerPoint) into Markdown format and creates an intelligent index for AI-powered document analysis.

## Features

- Document processing with Docling
- Project initialization with VS Code Custom Agent support
- Manifest-based change tracking
- Markdown conversion and indexing

## Installation

```bash
pip install nest
```

## Usage

```bash
# Initialize a new project
nest init "Project Name"

# Sync documents
nest sync

# Check project status
nest status

# Validate environment
nest doctor
```

## Development

```bash
# Install dependencies
uv sync

# Run tests
pytest

# Run linting
ruff check .

# Run type checking
pyright
```

## License

MIT

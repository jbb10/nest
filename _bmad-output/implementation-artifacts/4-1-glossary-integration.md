# Story 4.1: [CLI] Auto-Generated Project Glossary Integration

Status: ready-for-dev
Branch: feat/4-1-glossary-integration

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **the system to automatically generate and maintain a `glossary.md` file from project documents**,
So that **I can easily understand project-specific jargon, acronyms, and proper nouns without manual documentation effort.**

## Business Context

The `nest` tool currently builds a knowledge base from raw documents. However, understanding a new project often requires learning specific terminology that isn't explicitly defined in standard documentation.

This feature adds a "Glossary" capability that:
1.  **Extracts terms** using Azure OpenAI (LLM) during the `nest sync` process.
2.  **Populates a global `glossary.md`** file in the project output.
3.  **Respects human curation** (Discovery mode: AI suggests, Humans refine, AI never overwrites human edits).

**Scope for V1 (Discovery Mode):**
- **Additive Only:** New terms found in documents are added. Existing terms are never deleted, even if the source document is removed.
- **Project Specific:** We target Proper Nouns, Acronyms, and internal naming conventions, filtering out generic industry terms via strict prompting.
- **Deterministic:** The process must be stable and predictable.

## Acceptance Criteria

### AC1: Configuration & Environment ("Just Works")
**Given** a Nest project
**When** `nest sync` runs
**Then** the feature activates automatically if these environment variables are detected:
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT_NAME` (or similar)
**And** if these variables are **missing**, the system:
- Logs a friendly warning ("Glossary generation skipped: Azure credentials not found. Set AZURE_OPENAI_... to enable.")
- Continues the sync process without error (Graceful degradation)
**And** if variables are present but invalid (Auth Error), it logs an error and skips glossary generation for this run.

### AC2: Per-File Term Extraction (Discovery)
**Given** `nest sync` is running
**When** a new or modified document is processed
**Then** the system sends the text chunk to Azure OpenAI with a specific system prompt
**And** the prompt instructs the LLM to extract:
  - Acronyms (e.g., "PDC", "SME")
  - Proper Nouns (Project names, specific tools)
  - Domain-specific jargon
**And** ignores generic terms (e.g., "server", "database")
**And** returns a structured JSON list of `{ term: "...", definition_stub: "..." }`.

### AC3: Caching Mechanism
**Given** a file has already been processed for glossary terms
**When** `nest sync` runs again
**Then** the system checks a content hash (checksum)
**And** if the file is unchanged, it **skips** the LLM call and uses the cached terms
**And** if the file is modified, it re-scans the file for new terms.

### AC4: Deterministic Merge Logic & Persistence
**Given** existing terms in `glossary.md` and newly discovered terms
**When** the global glossary is updated
**Then** the logic follows these rules:
1.  **New Term:** If a term does not exist in `glossary.md`, add it.
2.  **Existing Term:** If a term already exists, **DO NOT** update the definition (assume the human has refined it).
3.  **No Deletions:** Never delete a term from `glossary.md` automatically.
4.  **Sorting:** The final table is sorted alphabetically by Term.

### AC5: Output Format (Markdown Table)
**Given** the glossary generation completes
**When** the `glossary.md` file is written
**Then** it contains a standard Markdown table:
```markdown
# Project Glossary

| Term | Definition | Source(s) |
|------|------------|-----------|
| ...  | ...        | ...       |
```
**And** the file content is protected from partial template corruption
**And** the system can parse an existing `glossary.md` back into memory (handling broken tables gracefully).

## Technical Notes

### Architecture & Tech Stack
- **Service:** `GlossaryService` (new core service).
- **LLM Client:** Use `openai` Python library with Azure configuration.
- **Prompt:** Store the system prompt in a file (e.g., `src/nest/resources/prompts/glossary_extraction.txt`) to allow easy iteration without code changes.
- **Parsing:** Use a robust Markdown table parser (regex or simple line splitting). Do not use heavy external dependencies just for this if possible.
- **Integration Point:** Call `GlossaryService.extract_and_merge(file_path, content)` inside the `sync` loop, likely after Docling processing.

### Environment Schema
To avoid hardcoding, ensure `Settings` or `Config` object is updated to load Azure credentials securely.

## Task Breakdown

### Dev Tasks
- [ ] **Scaffold GlossaryService:** Create class structure and dependency injection in `src/nest/core/services/glossary_service.py`.
- [ ] **Implement LLM Client:** Add Azure OpenAI integration with retry logic (backoff).
- [ ] **Implement Extraction Logic:** Create the prompt and JSON parsing for LLM responses.
- [ ] **Implement Caching:** Add a sidecar cache file (e.g., `.nest/glossary_cache.json`) mapping `file_hash -> [terms]`.
- [ ] **Implement Merge & Write:** Logic to read `glossary.md`, merge new terms (preserving old ones), and write back sorted Markdown.
- [ ] **Integrate into Sync:** Update `sync_cmd` or `ProcessService` to call GlossaryService when `NEST_GLOSSARY_ENABLED=true`.

### Testing Tasks
- [ ] **Unit Tests:**
    - Test `merge_terms` logic (ensure no overwrites).
    - Test Markdown table parsing (robustness).
    - Test Cache hit/miss logic.
- [ ] **Integration Tests:**
    - Mock Azure OpenAI response and verify `glossary.md` creation from a dummy file.
- [ ] **E2E Tests:**
    - Full run with a real file (mocked LLM or simple pass-through) to ensure the file appears in output.

### Documentation Tasks
- [ ] Update `README.md` with new Env Var requirements.
- [ ] Add a section on "Auto-Glossary" to the project documentation.

# Sprint Change Proposal: Folder Naming Strategy & User-Curated Context Support

**Date:** 2026-01-21  
**Project:** Nest  
**Epic Affected:** Epic 1 (Done), Epic 2 (In Review)  
**Change Scope:** Minor - Direct Implementation  
**Status:** Awaiting Approval

---

## 1. Issue Summary

### Problem Statement

Users need the ability to include pre-formatted context files (like hand-written guides, existing documentation, READMEs) directly in the agent's knowledge base without running them through Docling processing. 

### Discovery Context

This requirement emerged during real-world usage of Nest while Epic 2 was in review. The user discovered a legitimate workflow pattern: manually adding already-formatted context files alongside Nest's auto-generated output.

### Current Limitation

The existing folder structure (`raw_inbox/` → `processed_context/`) creates three problems:

1. **Folder names don't communicate dual-purpose capability:** `processed_context/` implies "only for Docling output," discouraging users from adding manual files
2. **Orphan cleanup removes manual files:** The cleanup logic treats any file not in the manifest as an orphan and removes it, breaking the manual file workflow
3. **Generic names risk conflicts:** `raw_inbox/` and `processed_context/` are verbose, and future simpler names like `sources/` or `context/` could easily conflict with existing project folders

### Evidence

- User has been manually placing files into `processed_context/`
- Orphan cleanup feature removes these files (not tracked in manifest = orphan)
- Current naming is ambiguous and doesn't support this valid use case

---

## 2. Impact Analysis

### Epic Impact

**Epic 1: Project Initialization (Status: Done)**
- **Affected Stories:** 1.1 (Project Scaffolding), 1.2 (Agent File Generation), 1.4 (CLI Integration)
- **Impact:** Folder names hardcoded in init command and agent template
- **Change Required:** Update folder names in all init-related code and templates

**Epic 2: Document Processing & Sync (Status: In Review)**
- **Affected Stories:** 2.3 (Output Mirroring), 2.5 (Index Generation), 2.6 (Orphan Cleanup), 2.8 (CLI Integration), 2.9 (E2E Testing)
- **Impact:** Multiple stories reference old folder names; orphan cleanup logic needs enhancement
- **Change Required:** 
  - Update folder name references throughout
  - Enhance orphan cleanup to only remove manifest-tracked files
  - Update index generation to scan entire `context/` directory
  - Update E2E tests to reflect new naming

**Epic 3: Project Visibility & Health (Status: Backlog)**
- **Affected Stories:** 3.1 (Status Display), 3.4 (Project Validation), 3.6 (Doctor CLI)
- **Impact:** User-facing messages display folder names
- **Change Required:** Update folder names in status/doctor output

**Epic 4: Tool Updates & Maintenance (Status: Backlog)**
- **Affected Stories:** 4.4 (Agent Template Migration)
- **Impact:** Agent template references folder names
- **Change Required:** Update template migration logic

### Artifact Conflicts

**PRD (prd.md):**
- Section 3.1: Sidecar pattern folder structure diagram
- Section 4.1: `nest init` directory creation description
- Section 4.2: `nest sync` directory mirroring examples and orphan cleanup description
- Section 4.5: `nest doctor` folder validation
- Section 6.3: .gitignore references

**Architecture (architecture.md):**
- FR1 description in Requirements Inventory
- Project structure examples throughout
- Code samples showing path handling
- Directory structure diagrams

**Epics (epics.md):**
- FR1, FR5-FR11 requirement descriptions
- Story acceptance criteria containing folder names

**Agent Template:**
- Forbidden files section references
- Context instructions

**No conflicts with:** Sprint status, UI/UX specs (CLI-only), CI/CD configuration

### MVP Impact

**MVP Status:** ✅ **Not affected**

This is a user experience improvement and naming enhancement. It does not reduce scope or remove features. The MVP remains fully achievable with this change and actually becomes more user-friendly.

---

## 3. Recommended Approach

### Selected Path: Direct Adjustment (Option 1)

**Rationale:**

1. **Low Complexity:** Primarily a naming change with one logic enhancement (orphan cleanup)
2. **Low Risk:** No architectural changes, maintains all existing functionality
3. **Early Discovery:** Caught during Epic 2 review before widespread code proliferation
4. **User Experience Win:** Better folder names improve clarity across all touchpoints
5. **Future-Proof:** Supports legitimate user workflow that should have been considered initially

**Alternatives Considered:**

- **Option 2 (Rollback):** Not applicable - this is an enhancement, not a wrong turn
- **Option 3 (MVP Review):** Not needed - MVP scope unchanged

### Implementation Strategy

**Two-Folder Approach with Smart Cleanup:**

```
my-project/
├── _nest_sources/    # Files that need Docling processing
└── _nest_context/    # ALL context (generated + user-curated)
```

**Key Technical Change:**

Orphan cleanup logic becomes manifest-aware:
- **In manifest + source exists** → Keep (managed file, valid)
- **In manifest + source deleted** → Orphan (remove)
- **NOT in manifest** → User-added (keep, never touch)

**User Mental Model:**
- "I drop documents needing processing in `_nest_sources/`"
- "I drop ready-made context directly in `_nest_context/`"
- "Nest generates into `_nest_context/` and manages its own files"
- "My manual files in `_nest_context/` are safe because they're not tracked"

**Naming Rationale:**
- Underscore prefix prevents conflicts with existing project folders (e.g., `sources/`, `context/`)
- Clear namespace: immediately identifiable as Nest-managed folders
- Follows convention for special/tool-specific directories (`_build/`, `_site/`, etc.)

**Index Generation:**
- Scan entire `context/` directory (manifest-tracked + untracked files)
- No distinction needed in index output - agent treats all files equally
- Simple, elegant solution

---

## 4. Detailed Change Proposals

### Change Group 1: PRD Updates

#### PRD Change 1.1 - Sidecar Pattern Diagram

**File:** `_bmad-output/planning-artifacts/prd.md`  
**Section:** 3.1 The "Sidecar" Pattern

**OLD:**
```
my-project/
├── .github/
│   └── agents/
│       └── nest.agent.md
├── raw_inbox/                  <-- User Input (PDFs, XLSX)
└── processed_context/          <-- System Output (AI Knowledge Base)
    ├── 00_MASTER_INDEX.md
    ├── policy_v1.md
    └── financial_data.md
```

**NEW:**
```
my-project/
├── .github/
│   └── agents/
│   _nest_sources/              <-- User Input (PDFs, XLSX, etc. for processing)
└── _nest_context/              <-- AI Knowledge Base (Generated + User-Curated)
    ├── 00_MASTER_INDEX.md      <-- The Map
    ├── policy_v1.md            <-- Generated from _nest_sources/
    ├── developer-guide.md      <-- User-added (no processing needed)
    └── financial_data.md       <-- Generated from _nest_sources/
```

**Rationale:** Underscore prefix prevents conflicts with existing project folders; shows dual-purpose nature of `_nest_context/`
**Rationale:** Shows dual-purpose nature of `context/` folder

---

#### PRD Change 1.2 - Init Command Behavior

**File:** `_bmad-output/planning-artifacts/prd.md`  
**Section:** 4.1 Command: `nest init`

**OLD:**
```
1.  Creates directories: `raw_inbox/`, `processed_context/`.
```

**NEW:**
```_nest_sources/`, `_nest_context/`.
```

**Rationale:** Update to new folder names with underscore prefix to prevent project folder conflict
**Rationale:** Update to new folder names

---

#### PRD Change 1.3 - Sync Directory Mirroring Example

**File:** `_bmad-output/planning-artifacts/prd.md`  
**Section:** 4.2 Command: `nest sync` - Directory Mirroring Example

**OLD:**
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

**NEW:**
```
_nest_sources/                  _nest_context/
├── contracts/                  ├── contracts/
│   ├── 2024/                   │   ├── 2024/
│   │   └── alpha.pdf     →     │   │   └── alpha.md
│   └── 2025/                   │   └── 2025/
│       └── beta.pdf      →     │       └── beta.md
├── reports/                    ├── reports/
│   └── Q3_summary.xlsx   →     │   └── Q3_summary.md
└── (manual files go           └── developer-guide.md  <-- User-curated
    directly in _nest_context/)    onboarding.md       <-- User-curated
```

**Rationale:** Clarifies that users can add files directly to `_nest_context/` with conflict-safe naming

---

#### PRD Change 1.4 - Sync Behavior and Orphan Cleanup

**File:** `_bmad-output/planning-artifacts/prd.md`  
**Section:** 4.2 Command: `nest sync` - Behavior

**OLD:**
```
1.  **Scan:** Recursively scans `raw_inbox/` for supported files (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`).
[...]
4.  **Orphan Cleanup:** By default, removes files from `processed_context/` whose source no longer exists in `raw_inbox/`. Disable with `--no-clean`.
5.  **Index Generation:** Regenerates `00_MASTER_INDEX.md` with file listing.
```

**NEW:**
```
1.  **Scan:** Recursively scans `_nest_sources/` for supported files (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`).
[...]
4.  **Orphan Cleanup:** By default, removes files from `_nest_context/` **that are tracked in the manifest** whose source no longer exists in `_nest_sources/`. Files not in the manifest (user-curated) are never touched. Disable with `--no-clean`.
5.  **Index Generation:** Regenerates `00_MASTER_INDEX.md` with file listing from entire `_nest_context/` directory (both generated and user-curated files).
```

**Rationale:** Clarifies smart orphan cleanup logic, comprehensive index generation, and conflict-safe folder naming

---

#### PRD Change 1.5 - Security & Privacy (gitignore)

**File:** `_bmad-output/planning-artifacts/prd.md`  
**Section:** 6.3 Security & Privacy

**OLD:**
```text
raw_inbox/
# We commit processed_context so the team shares the brain
# We DO NOT commit raw_inbox (often too large/sensitive)
```

**NEW:**
```text
_nest_sources/
# We commit _nest_context/ so the team shares the brain
# We DO NOT commit _nest_sources/ (often too large/sensitive)
```

**Rationale:** Update folder names in gitignore instructions with conflict-safe naming

---

#### PRD Change 1.6 - Agent Forbidden Files

**File:** `_bmad-output/planning-artifacts/prd.md`  
**Section:** 4.1 nest init - Output File (agent template)

**OLD:**
```markdown
**Raw Source Files:**
- `raw_inbox/**` — Never read files from this folder. Always use the processed Markdown versions in `processed_context/` instead.
[...]
**If you find yourself wanting to read any of these, STOP and reconsider. The answer to the user's question is in `processed_context/`.**
```

**NEW:**
```markdown
**Raw Source Files:**
- `_nest_sources/**` — Never read files from this folder. Always use the processed Markdown versions in `_nest_context/` instead.
[...]
**If you find yourself wanting to read any of these, STOP and reconsider. The answer to the user's question is in `_nest_context/`.**
```

**Rationale:** Update folder references in agent instructions with conflict-safe naming

---

### Change Group 2: Architecture Updates

#### Architecture Change 2.1 - FR1 Description

**File:** `_bmad-output/planning-artifacts/architecture.md`  
**Section:** Requirements Inventory - Functional Requirements

**OLD:**
```
**FR1:** `nest init "Project Name"` creates project structure with `raw_inbox/`, `processed_context/` directories
```

**NEW:**
```
**FR1:** `nest init "Project Name"` creates project structure with `_nest_sources/`, `_nest_context/` directories
```

**Rationale:** Update requirement description with conflict-safe folder naming

---

#### Architecture Change 2.2 - Project Structure Examples

**File:** `_bmad-output/planning-artifacts/architecture.md`  
**Location:** Throughout code examples and path handling patterns

**Action:** Global find/replace in code examples:
- `raw_inbox/` → `_nest_sources/`
- `processed_context/` → `_nest_context/`

**Rationale:** Consistency across all code samples with conflict-safe naming

---

### Change Group 3: Epic & Story Updates

#### Epic Change 3.1 - Epic 1 Scope Description

**File:** `_bmad-output/planning-artifacts/epics.md`  
**Section:** Epic 1: Project Initialization

**OLD:**
```
**Scope:**
- Creates `raw_inbox/`, `processed_context/` directories
```

**NEW:**
```
**Scope:**
- Creates `_nest_sources/`, `_nest_context/` directories
- Supports both auto-generated and user-curated context files
```

**Rationale:** Clarify dual-purpose design with conflict-safe folder naming

---

#### Epic Change 3.2 - Story 1.1 Acceptance Criteria

**File:** `_bmad-output/planning-artifacts/epics.md`  
**Section:** Story 1.1: Project Scaffolding

**OLD:**
```
**Then** the following directories are created:
- `raw_inbox/`
- `processed_context/`
```

**NEW:**
```
**Then** the following directories are created:
- `_nest_sources/`
- `_nest_context/`
```

**OLD:**
```
**Given** a `.gitignore` file exists in the directory
**When** I run `nest init "Nike"`
**Then** `raw_inbox/` is appended to `.gitignore` if not already present
```

**NEW:**
```
**Given** a `.gitignore` file exists in the directory
**When** I run `nest init "Nike"`
**Then** `_nest_sources/` is appended to `.gitignore` if not already present
```

**Rationale:** Update folder names in acceptance criteria with conflict-safe naming

---

#### Epic Change 3.3 - FR5-FR11 Descriptions

**File:** `_bmad-output/planning-artifacts/epics.md`  
**Section:** Requirements Inventory - Functional Requirements

**Action:** Update folder names in:
- FR5: "scans `_nest_sources/`" (was `raw_inbox/`)
- FR8: "mirrors source folder hierarchy in `_nest_context/`" (was `processed_context/`)
- FR9: "removes orphaned files from `_nest_context/` **that are tracked in the manifest**" (add clarification)
- FR10: "regenerates `00_MASTER_INDEX.md` from entire `_nest_context/` directory"

**Rationale:** Align requirement descriptions with new design using conflict-safe naming

---

#### Epic Change 3.4 - Story 2.6 Enhancement

**File:** `_bmad-output/planning-artifacts/epics.md`  
**Section:** Story 2.6: Orphan Cleanup

**Add New Acceptance Criterion:**

```
**Given** I have manually added `developer-guide.md` to `_nest_context/` (not in manifest)
**When** I run `nest sync --clean`
**Then** `developer-guide.md` is NOT removed (not tracked, therefore not an orphan)
**And** console confirms: "User-curated files: 1 (preserved)"
```

**Rationale:** Verify smart cleanup logic preserves user files with conflict-safe naming

---

### Change Group 4: Implementation Files

**Note:** These changes will be made during implementation, not in planning docs:

- Update all hardcoded path references: `"raw_inbox"` → `"_nest_sources"`, `"processed_context"` → `"_nest_context"`
- Enhance orphan cleanup logic in sync service
- Update index generation to scan full `_nest_context/` directory
- Update agent template Jinja file
- Update all user-facing messages in CLI commands
- Update E2E test fixtures and expectations

---

## 5. Implementation Handoff

### Change Scope Classification

**Scope:** **Minor** - Can be implemented directly by development team

### Handoff Recipients

**Primary:** Development team (AI agent or human developer)  
**Role:** Implement all folder name changes and orphan cleanup enhancement

**Secondary:** Scrum Master  
**Role:** Update planning artifacts (PRD, Architecture, Epics) with approved changes

### Implementation Checklist

**Planning Artifacts (Scrum Master):**
- [ ] Update PRD with all 6 proposed changes
- [ ] Update Architecture with folder name references
- [ ] Update Epics with story modifications
- [ ] Review agent template updates

**Code Implementation (Development Team):**
- [ ] Update folder name constants/config
- [ ] Enhance orphan cleanup logic (manifest-aware)
- [ ] Update index generation (full directory scan)
- [ ] Update agent template file
- [ ] Update all CLI output messages
- [ ] Update E2E tests
- [ ] Run full test suite (unit + integration + E2E)
- [ ] Update documentation/README

### Success Criteria

**Functional:**
- ✅ `nest init` creates `_nest_sources/` and `_nest_context/` folders
- ✅ User can manually add files to `_nest_context/` without processing
- ✅ Orphan cleanup preserves user-curated files
- ✅ Index includes both generated and manual files
- ✅ All E2E tests pass with new folder names
- ✅ Folder names don't conflict with common project folders

**Documentation:**
- ✅ PRD, Architecture, Epics reflect new folder names
- ✅ Agent template uses correct folder references
- ✅ README/user docs updated

**Quality:**
- ✅ No test failures
- ✅ Ruff + Pyright pass
- ✅ Conventional commit messages

### Timeline Estimate

**Effort:** 2-4 hours total
- Planning doc updates: 30 minutes
- Code changes: 1-2 hours (mostly find/replace + one logic enhancement)
- Testing: 1 hour
- Documentation: 30 minutes

**Risk:** Low - straightforward naming change with clear logic enhancement

---

## 6. Approval & Next Steps

### Approval Status

⏸️ **Awaiting explicit approval from Jóhann**

### Questions for Approval
_nest_sources/` + `_nest_
1. Do you approve this folder naming strategy (`sources/` + `context/`)?
2. Do you approve the smart orphan cleanup approach (manifest-aware)?
3. Are you comfortable with the minor scope expansion to Epic 2?
4. Should we proceed with implementation immediately?

### Post-Approval Actions

Upon approval:
1. Scrum Master updates planning artifacts
2. Development team implements code changes
3. Full test suite validation
4. Story 2.9 (E2E Testing) marked complete after verification
5. Epic 2 marked complete after all changes validated

---

**End of Sprint Change Proposal**

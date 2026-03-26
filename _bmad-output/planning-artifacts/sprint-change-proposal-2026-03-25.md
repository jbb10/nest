# Sprint Change Proposal: Multi-Agent Architecture

| Field | Value |
|-------|-------|
| **Date** | 2026-03-25 |
| **Proposed by** | Johann (Product Owner) |
| **Status** | **Approved** |
| **Scope** | Minor (direct implementation by dev team) |

---

## 1. Issue Summary

The current Nest product ships a single agent file (`nest.agent.md`) that serves as a generalist document analyst. A superior multi-agent architecture has been designed using VS Code Copilot's subagent system:

- **Coordinator** (`nest.agent.md`): Orchestrates work, handles simple lookups, delegates complex tasks
- **Researcher** (`nest-master-researcher.agent.md`): Deep document search with precise citations
- **Synthesizer** (`nest-master-synthesizer.agent.md`): Cross-document comparison and structured analysis
- **Planner** (`nest-master-planner.agent.md`): Action items, risks, next steps, work plans

Benefits: reduced token usage (isolated context windows), parallel execution capability, and higher-quality outputs through specialization.

**Category:** New feature, product enhancement.

## 2. Impact Analysis

### Epic Impact

- No existing epics affected. All completed epics remain valid.
- New Epic 10 (Multi-Agent Architecture) added with 3 stories.

### Story Impact

- No in-progress or completed stories require changes.
- 3 new stories added: template bundle, init/doctor integration, migration service.

### Artifact Conflicts

| Artifact | Sections Affected | Change Type |
|----------|-------------------|-------------|
| PRD (prd.md) | 3.1 file tree, 4.1 init output, FR2, FR16, FR32 | Update references to multi-agent |
| Architecture (architecture.md) | Project Structure, Agent Generation | Update template listing, protocol |
| Epics (epics.md) | FR table, Epic list | Add FR41-FR43, Epic 10 with 3 stories |
| Sprint Status (sprint-status.yaml) | development_status | Add epic-10 entries |

### Technical Impact

| File | Change |
|------|--------|
| `src/nest/agents/templates/` | 1 template replaced by 4 Jinja templates |
| `src/nest/agents/vscode_writer.py` | Add `render_all()`, `generate_all()` methods |
| `src/nest/adapters/protocols.py` | Update `AgentWriterProtocol` |
| `src/nest/services/init_service.py` | Use `generate_all()` |
| `src/nest/adapters/project_checker.py` | Validate all 4 files |
| `src/nest/services/agent_migration_service.py` | Multi-file comparison and migration |
| `src/nest/cli/update_cmd.py` | File-level migration display |

## 3. Recommended Approach

**Direct Adjustment** with 3 new stories in a new Epic 10.

The existing agent writer protocol was designed for extensibility (Strategy pattern, templated generation). Multi-file support extends the existing patterns cleanly. Backward compatibility is maintained during Story 10.1 to prevent regressions. All prerequisite epics (4, 8) are complete.

**Effort:** Medium (3 focused stories)
**Risk:** Low (additive change, existing infrastructure reused)
**Timeline Impact:** None on existing work. Epic 10 slots after current work.

## 4. Detailed Change Proposals

### Proposal A: New Epic 10 with 3 Stories

**Story 10.1: Multi-Agent Template Bundle**
- Replace single `vscode.md.jinja` with 4 templates (coordinator, researcher, synthesizer, planner)
- Update `VSCodeAgentWriter` with `render_all()` and `generate_all()` methods
- Update `AgentWriterProtocol`
- Delete `NEW_AGENTS/` source folder after templates created
- Maintain backward compat for existing callers

**Story 10.2: Init & Doctor Multi-Agent Integration**
- `nest init` creates all 4 agent files
- `ProjectChecker` validates all 4 files exist
- `nest doctor --fix` regenerates all files (overwrite directly, no backups)

**Story 10.3: Multi-Agent Migration Service**
- `check_migration_needed()` compares all 4 files against templates
- `execute_migration()` overwrites outdated files directly (no .bak backups)
- Legacy single-agent projects: old agent replaced, 3 subagents created
- CLI shows file-level detail (Replace/Create), single batch prompt

### Proposal B: PRD Updates

- Section 3.1: Update file tree to show 4 agent files
- FR2: Update to mention all 4 agent files
- FR16: Update for multi-file migration scope

### Proposal C: Architecture Updates

- Project Structure: Update agents/templates/ listing
- Agent protocol: Document new multi-file methods

### Proposal D: Sprint Status

- Add Epic 10 with 3 stories in backlog state

## 5. Implementation Handoff

**Scope:** Minor, direct implementation by dev team.

| Role | Responsibility |
|------|---------------|
| Dev team | Implement Epic 10 stories (10.1, 10.2, 10.3 in order) |
| SM | Orchestrate story execution, validate acceptance criteria |

**Success Criteria:**
1. `nest init` creates 4 agent files in `.github/agents/`
2. `nest doctor` validates all 4 files and can remediate missing ones
3. `nest update` detects and migrates all 4 files when templates change
4. Legacy projects seamlessly upgraded (no .bak files left behind)
5. All existing tests pass, new tests cover multi-agent scenarios
6. `NEW_AGENTS/` directory removed from repo

**New FRs:** FR41, FR42, FR43
**Implementation artifacts:** 10-1, 10-2, 10-3 (already created)

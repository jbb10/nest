# Sprint Change Proposal: Image Description via Vision LLM

| Field | Value |
|---|---|
| **Date** | 2026-03-17 |
| **Proposed By** | Jóhann (PM facilitated) |
| **Status** | Approved |
| **Change Scope** | Minor |

---

## 1. Issue Summary

Documents with images (diagrams, charts, photos) currently produce `[Image: ...]` placeholder markers in the output Markdown. The `@nest` agent has zero visibility into image content — it cannot describe diagrams, reference charts, or answer questions about visual elements.

The PRD originally flagged this as a roadmap item: *"Ignore images for V1. (Roadmap Item: Use GPT-4o to caption images)."* The LLM infrastructure (Epic 6) is now complete and working well. The concept is proven. This proposal pulls image description into scope using the existing Azure LLM endpoint.

**Reference implementation guide:** `docs/docling-picture-description-guide.md`

---

## 2. Impact Analysis

### Epic Impact

| Epic | Impact | Details |
|---|---|---|
| Epic 2 (Sync) | Dependency | DoclingProcessor pipeline options change; sync loop gains image description step |
| Epic 6 (AI Enrichment) | Dependency | LLM adapters gain vision/multi-modal support; env var chain extended |
| **Epic 7 (NEW)** | **New** | Image Description via Vision LLM — 4 stories |

No epics removed, deferred, or resequenced.

### Story Impact

4 new stories added (7.1–7.4). No existing stories modified.

### Artifact Conflicts

| Artifact | Change Needed |
|---|---|
| PRD § 6.1 | Remove "Ignore images for V1"; add image description behavior |
| PRD FRs | Add FR34–FR38 for image description |
| Architecture | Add vision adapter, two-pass pipeline, PictureDescriptionService |
| Epics | Add Epic 7 with 4 stories |

### Technical Impact

- DoclingProcessor gains `do_picture_classification=True`, `generate_picture_images=True`, `images_scale=2.0`
- LLM adapters gain `complete_with_image()` for multi-modal messages
- New `PictureDescriptionService` with parallel LLM calls (ThreadPoolExecutor, max_workers=50)
- Docling's `PictureDescriptionData` stores descriptions in-place; `export_to_markdown()` embeds them automatically
- Two-pass approach: classify locally (no API) → describe with type-specific prompts (Mermaid for diagrams, prose for charts/photos, skip logos/signatures)

---

## 3. Recommended Approach

**Direct Adjustment** — Add new Epic 7 with 4 stories to existing plan.

**Rationale:**
- All infrastructure is in place (LLM adapters, AI enrichment pipeline, Docling image extraction)
- Change is additive — existing behavior preserved when AI is not configured
- Graceful degradation pattern already established (`--no-ai` flag, env var detection)
- Low risk — mirrors existing AI enrichment patterns
- Developer guide with complete implementation reference already prepared

**Effort:** Medium
**Risk:** Low

---

## 4. Detailed Change Proposals

### PRD Changes

#### Section 6.1 — Docling Implementation Details

```
OLD:
* **Images:** Ignore images for V1 to keep speed high. (Roadmap Item: Use GPT-4o to caption images).

NEW:
* **Images:** When AI is configured, Docling classifies images locally (diagrams, charts, photos,
  logos, etc.) then sends them to a vision-capable LLM with type-specific prompts: flowcharts and
  block diagrams produce Mermaid code blocks, charts/photos get concise descriptions, logos and
  signatures are skipped. Descriptions are embedded inline in the output Markdown. When AI is not
  configured, images produce `[Image: ...]` placeholder markers.
```

#### New Functional Requirements

| FR | Description |
|---|---|
| FR34 | `nest sync` uses Docling's local picture classifier to categorize images, then sends classified images to a vision LLM with type-specific prompts: Mermaid for diagrams (flow_chart, block_diagram), prose descriptions for charts and photos, skip for logos and signatures. Descriptions are stored back into Docling's document model and embedded in the exported Markdown automatically. |
| FR35 | Image description uses a dedicated vision model configured via `NEST_AI_VISION_MODEL` env var (fallback: `OPENAI_VISION_MODEL`, default: `gpt-4.1`), independent of the text enrichment model |
| FR36 | Image descriptions within a single document are processed in parallel (up to 50 concurrent LLM calls), and image processing for one document does not block image processing for other documents |
| FR37 | When AI is not configured or vision model is unavailable, images produce `[Image: ...]` placeholder markers in the output Markdown (existing V1 behavior preserved) |
| FR38 | Image description token usage is included in the sync summary token usage reporting (FR30) |

#### FR Coverage Map Additions

| FR | Epic | Description |
|---|---|---|
| FR34 | Epic 7 | Two-pass image classification + description with type-specific prompts |
| FR35 | Epic 7 | Vision model configuration (NEST_AI_VISION_MODEL) |
| FR36 | Epic 7 | Parallel image description (50 concurrent per doc, cross-file) |
| FR37 | Epic 7 | Graceful degradation to placeholders |
| FR38 | Epic 7 | Token usage reporting for image descriptions |

### Architecture Changes

1. **LLM Adapters** — Add `complete_with_image(prompt, image_base64, mime_type)` to both OpenAI and Azure adapters. Constructs multi-modal messages with image_url content blocks.
2. **DoclingProcessor** — Two-pass pipeline: classify locally (do_picture_classification=True, images_scale=2.0), then describe with type-specific prompts.
3. **PictureDescriptionService** — New service: iterates PictureItems, routes by classification label, fires parallel LLM calls (50 max), stores PictureDescriptionData back into document model.
4. **Sync Pipeline** — After Docling convert, call PictureDescriptionService, then export_to_markdown() (descriptions embedded automatically).
5. **Vision Model Config** — NEST_AI_VISION_MODEL → OPENAI_VISION_MODEL → default "gpt-4.1"

### Epics Changes

New Epic 7 with 4 stories:
- **7.1:** Vision-Capable LLM Adapters
- **7.2:** Docling Two-Pass Image Pipeline
- **7.3:** Picture Description Service
- **7.4:** Sync Pipeline Integration & Cross-File Parallelism

---

## 5. Implementation Handoff

| Field | Value |
|---|---|
| **Change Scope** | Minor |
| **Route To** | Development team |
| **Deliverables** | Epic 7 stories implemented, all tests passing |
| **Reference** | `docs/docling-picture-description-guide.md` |

**Success Criteria:**
- `nest sync` describes images when AI configured, produces placeholders when not
- Diagrams produce Mermaid code blocks; charts/photos get prose descriptions; logos/signatures skipped
- Up to 50 images per document described in parallel
- Cross-file parallelism (file A's images don't block file B)
- Token usage reported in sync summary
- All unit, integration, and E2E tests pass

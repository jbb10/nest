# AI Transcription Is All-or-Nothing and Convert-Only

`nest convert --ai-only` prepares image files and PDFs by AI transcription instead of Docling layout analysis, OCR, and table recognition, because OCR misplaces values in dense tables and screenshots.
A source document whose pages are not all transcribed is a failed document, consistent with ADR 0002: nothing is written, the summary lists the file, and the run exits nonzero.
A partial transcription would look like a complete prepared document while silently missing pages.

## Considered Options

- **Write the readable pages and mark the gaps (rejected).**
  A prepared document missing a table page is worse than no document, because downstream readers cannot tell that values are absent.
- **Fall back to Docling for unreadable pages (rejected).**
  The pages the model cannot read are the dense ones where OCR is least reliable, so the fallback would reintroduce the errors the flag exists to avoid, without signalling it.
- **Offer AI transcription in `nest sync` (deferred).**
  Sync records outcomes in the manifest, so a project would need to remember which preparation produced each prepared document and re-prepare when that choice changes.
  Convert has no manifest, so the flag carries no such state.

## Consequences

- The transcription prompt asks the model to answer with the marker `NEST_UNREADABLE_PAGE` instead of a refusal, and any answer containing the marker fails the document.
  Models phrase refusals in many ways; one fixed marker gives a single reliable check.
- Every page is a separate vision request, run concurrently, so cost and latency grow with page count.
- `pypdfium2` renders PDF pages and Pillow re-encodes image formats the vision models do not accept natively.

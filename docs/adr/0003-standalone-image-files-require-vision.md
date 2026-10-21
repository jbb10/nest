# Standalone Image Files Require AI When They Hold a Describable Figure

Standalone image files in `_nest_sources/` are source documents converted by Docling as one-page scanned documents.
When the conversion holds a figure that the vision pass would describe and no vision provider is available, the image file is a failed document.
Nothing is written for it, it is recorded as failed so the next sync retries it once AI is enabled, and the run summary lists the affected files with instructions to enable AI.

## Why image files differ from embedded images

ADR 0002 makes a required image description fail a document only when AI image descriptions are enabled.
A PDF synced with `--no-ai` keeps its text and tables and emits a placeholder for each picture; the output remains useful.
For an image file, the figure is usually the entire document.
Writing a placeholder would produce an empty prepared document that looks successful, and unchanged-file detection would then prevent retry after AI is enabled.
Failing the document is the only outcome that keeps the manifest honest and makes the retry automatic.

## Considered Options

### Option A (accepted): fail the image file when it needs AI

Docling classifies the pictures in the image.
If any picture would be routed to the vision LLM (anything other than a logo or signature), the file fails with reason `requires AI image description`.
If the image holds only logos and signatures, or no picture at all (for example a screenshot of text), the plain export is written as a success.
Embedded images in PDFs, DOCX, and other formats keep the placeholder behaviour from ADR 0002.

### Option B: write the placeholder output and warn

Rejected.
The prepared document would be empty while counting as processed, and the checksum match would stop the next sync from retrying it.

### Option C: skip the file instead of failing it

Rejected.
Skipped files are not retried until their checksum changes, so enabling AI later would not pick them up without `--force`.

## Consequences

- Both `nest sync` and `nest convert` build a classification-enabled Docling processor when vision is unavailable, so the rule can be evaluated for image files.
  Other formats keep the plain processor.
- The outcome ledger carries a structured failure kind (`needs_ai`), and the summaries render a dedicated block for these files.
  The block is driven by the kind, not by matching reason text.
- `--on-error fail` aborts on these failures like any other failure.
- Image files follow the same mirror and collision rules as every other Docling format; no new precedence tier is introduced.

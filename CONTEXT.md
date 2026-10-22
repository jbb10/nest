# Document Preparation

Nest prepares source documents as readable context for research and other downstream work.

## Language

**Source document**:
An original document supplied for conversion or synchronization.
_Avoid_: Input artifact

**Prepared document**:
A readable representation of a source document with the extraction and descriptions requested for that run.
_Avoid_: Successful file merely because an output exists

**Image file**:
A standalone raster image supplied as a source document and treated as a scanned document with one page per frame.
_Avoid_: Embedded image, attachment

**Required image description**:
A description requested for an image when AI image descriptions are enabled and the image is not intentionally excluded.
For an image file, a description is also required when the image holds a figure that would be described, even if AI is unavailable.
_Avoid_: Optional enrichment

**Failed document**:
A source document whose requested preparation did not complete, including failure of a required image description.
_Avoid_: Completed with warnings for failed required descriptions

**AI transcription**:
Preparation of a source document in which an AI vision model reads every page as an image and its reading of those pages becomes the prepared document.
_Avoid_: Straight-to-AI transcription, AI-only conversion, OCR

**Quality warning**:
A condition that warrants reviewing a prepared document without establishing that a requested preparation step failed.
_Avoid_: Failure

**Activity**:
Work currently in progress, distinct from the number of documents already completed.
_Avoid_: Completion
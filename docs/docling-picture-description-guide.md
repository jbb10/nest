# Docling Picture Description: Developer Guide

How to send images found in source documents to a remote vision-language model
(e.g. GPT-4.1 on Azure OpenAI) and embed the returned descriptions — or Mermaid
diagrams — into the destination Markdown.

---

## Background

Docling's standard PDF pipeline detects `PictureItem` elements during conversion.
A **picture description enrichment** step can be enabled to send each extracted
image to a vision-language model. The model's response is stored in
`PictureItem.meta.description.text` and included when the document is exported to
Markdown.

Our current `DoclingProcessor` (in `src/nest/adapters/docling_processor.py`)
converts documents with table structure extraction only and exports Markdown with
`ImageRefMode.PLACEHOLDER`, producing `[Image: ...]` markers instead of binary
data. Enabling picture description replaces those markers with actual textual
descriptions.

---

## Approach: two-pass with classification

Docling offers built-in single-pass options that send every image to the same
API with the same prompt. These are convenient but produce lower-quality output
because they can't vary the prompt per image type and waste API calls on logos
and signatures.

**This project uses the two-pass method:**

1. **Pass 1** — Convert with `do_picture_classification=True` (local model,
   no API calls). This labels every image as `flow_chart`, `logo`,
   `natural_image`, etc.
2. **Pass 2** — Iterate the classified pictures and call Azure OpenAI with
   the right prompt for each type: Mermaid for diagrams, prose for photos
   and charts, skip for logos and signatures.

This produces better Mermaid output (focused prompt), better descriptions
(focused prompt), and lower cost (worthless images are never sent to the API).

---

## Pipeline flags reference

| Flag | Default | Purpose |
|---|---|---|
| `do_picture_description` | `False` | Enable the picture description enrichment step |
| `enable_remote_services` | `False` | Allow outbound API calls (required for any remote model) |
| `generate_picture_images` | `False` | Extract embedded images so they can be sent to the model |
| `images_scale` | `1.0` | Resolution multiplier for extracted images |
| `do_picture_classification` | `False` | Classify pictures by type (chart, diagram, photo, logo, etc.) |

---

## Getting Mermaid diagrams from flowcharts

Docling does not convert diagrams to Mermaid natively. The approach is
prompt-based: ask the vision model to produce the right format. There are two
strategies — single-prompt and two-pass. The two-pass approach produces
significantly better results.

### Why two-pass is better

The single-prompt approach ("if diagram, make Mermaid; otherwise describe")
asks the LLM to do two jobs at once: classify the image *and* produce the
right output format. In practice this causes:

- **Hedging**: the model produces a prose description *and* a Mermaid block
- **Misclassification**: data-table screenshots rendered as flowcharts
- **Diluted prompts**: conditional instructions compete for attention,
  making both the Mermaid output and the prose descriptions worse
- **Wasted API calls**: logos, signatures, and decorative images get sent
  to an expensive API for no useful output

The two-pass approach separates classification (local model, fast, free) from
generation (API call, expensive, slow). Each prompt is focused on exactly one
task, so the output quality goes up and the cost goes down.

### `DocumentFigureClassifier` labels

Docling's `DocumentFigureClassifier` (enabled with `do_picture_classification = True`)
is a lightweight local model (~50MB) that runs during conversion with no API
calls. It labels each `PictureItem` with a class and confidence score.

Known labels produced by the classifier:

| Label | What it matches | Recommended action |
|---|---|---|
| `flow_chart` | Flowcharts, decision trees, process flows | Mermaid prompt |
| `block_diagram` | Architecture diagrams, system diagrams | Mermaid prompt |
| `natural_image` | Photographs, screenshots of real scenes | Description prompt |
| `bar_chart` | Bar/column charts | Description prompt (summarize data) |
| `line_chart` | Line/trend charts | Description prompt (summarize data) |
| `pie_chart` | Pie/donut charts | Description prompt (summarize data) |
| `scatter_plot` | Scatter/bubble plots | Description prompt (summarize data) |
| `table` | Table rendered as image | Description prompt or skip (Docling already extracts tables) |
| `map` | Geographic maps | Description prompt |
| `logo` | Company/product logos | Skip — no value in describing |
| `signature` | Handwritten signatures | Skip — no value in describing |

The classifier returns a list of predictions per image, each with
`class_name` and `confidence` (0.0–1.0).

### Recommended approach: classify then describe (two-pass)

**Pass 1 — Conversion with classification only (no API calls):**

Run the Docling pipeline with `do_picture_classification=True` but
`do_picture_description=False`. This extracts images, classifies them, and
builds the full document model without any remote API calls.

```python
pipeline_options = PdfPipelineOptions(
    do_table_structure=True,
    table_structure_options=TableStructureOptions(
        do_cell_matching=True,
        mode=TableFormerMode.ACCURATE,
    ),
    do_picture_classification=True,    # classify locally
    do_picture_description=False,      # do NOT describe yet
    generate_picture_images=True,
    images_scale=2.0,
)
```

**Pass 2 — Send images to Azure with type-specific prompts:**

After conversion, iterate the pictures, check their classification, and call
Azure OpenAI yourself with the right prompt for each type. Skip images that
have no value (logos, signatures).

```python
from docling_core.types.doc import PictureItem
from docling_core.types.doc.document import PictureDescriptionData

# Prompt templates per image category
MERMAID_PROMPT = (
    "This image contains a diagram or flowchart. "
    "Reproduce it as a Mermaid diagram in a fenced ```mermaid code block. "
    "Use the correct Mermaid diagram type (flowchart, sequenceDiagram, classDiagram, etc.). "
    "Capture all nodes, edges, and labels. Do not add a prose description."
)

DESCRIPTION_PROMPT = (
    "Describe this image concisely and accurately. "
    "If it contains a chart or graph, summarize the key data points and trends. "
    "Focus on information that would be useful in a technical document."
)

# Labels that should produce Mermaid output
MERMAID_LABELS = {"flow_chart", "block_diagram"}

# Labels that should be skipped entirely
SKIP_LABELS = {"logo", "signature"}

CONFIDENCE_THRESHOLD = 0.5

for element, _level in result.document.iterate_items():
    if not isinstance(element, PictureItem):
        continue

    # Determine the best classification label
    best_label = None
    best_confidence = 0.0
    if element.meta and element.meta.classification:
        for pred in element.meta.classification.predictions:
            if pred.confidence > best_confidence:
                best_label = pred.class_name
                best_confidence = pred.confidence

    # Skip low-value images
    if best_label in SKIP_LABELS and best_confidence >= CONFIDENCE_THRESHOLD:
        continue

    # Pick the right prompt
    if best_label in MERMAID_LABELS and best_confidence >= CONFIDENCE_THRESHOLD:
        prompt = MERMAID_PROMPT
    else:
        prompt = DESCRIPTION_PROMPT

    # Get the image and call Azure OpenAI
    image = element.get_image(result.document)
    if image is None:
        continue

    description_text = call_azure_openai(image, prompt)  # your API call

    # Store the description back into the document model
    element.meta.description = PictureDescriptionData(
        text=description_text,
        created_by="azure-gpt-4.1",
    )
```

After this loop, `result.document.export_to_markdown()` will include the
descriptions (and Mermaid blocks) inline.

---

## Integration with `DoclingProcessor`

The current processor in `src/nest/adapters/docling_processor.py` would need
these changes to enable AI-powered picture descriptions:

1. Accept Azure config (endpoint, API key, model name) from user config or
   environment.
2. Enable `do_picture_classification=True` and `generate_picture_images=True`
   on the pipeline options. Keep `do_picture_description=False` — we handle
   description ourselves in the second pass.
3. After `converter.convert()`, iterate pictures, check classification labels,
   and call Azure OpenAI with the appropriate prompt (Mermaid for diagrams,
   prose for everything else, skip logos/signatures).
4. Store descriptions back via `PictureDescriptionData` before exporting
   Markdown.

When `--no-ai` is passed (or no AI config exists), skip both classification
and description — the processor falls back to the existing `[Image: ...]`
placeholder behavior. The classification step is local and cheap, but there's
no point running it if we're not going to call the API afterward.

---

## Accessing descriptions after conversion

After `converter.convert(source)`, picture descriptions are available on each
`PictureItem`:

```python
from docling_core.types.doc import PictureItem

result = converter.convert(source)

for element, _level in result.document.iterate_items():
    if isinstance(element, PictureItem):
        caption = element.caption_text(doc=result.document)
        description = None
        if element.meta and element.meta.description:
            description = element.meta.description.text
            created_by = element.meta.description.created_by
        print(f"Caption: {caption}")
        print(f"Description: {description}")
```

When exporting to Markdown, descriptions are automatically included.

---

## Azure OpenAI specifics

### URL format

```
https://{resource-name}.openai.azure.com/openai/deployments/{deployment-name}/chat/completions?api-version={api-version}
```

### Authentication

Azure uses `api-key` header (not `Authorization: Bearer`):

```python
headers={"api-key": os.environ["AZURE_OPENAI_API_KEY"]}
```

### Model parameter

The `model` param in Azure is the deployment name, not the model family:

```python
params={"model": "gpt-4.1"}  # your deployment name
```

---

## Complete minimal example

This uses the recommended two-pass approach: classify locally, then describe
with type-specific prompts via Azure.

```python
import base64
import io
import os
from pathlib import Path

import httpx
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableFormerMode,
    TableStructureOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import PictureItem
from docling_core.types.doc.document import PictureDescriptionData

# --- Prompts ---

MERMAID_PROMPT = (
    "This image contains a diagram or flowchart. "
    "Reproduce it as a Mermaid diagram in a fenced ```mermaid code block. "
    "Use the correct Mermaid diagram type (flowchart, sequenceDiagram, etc.). "
    "Capture all nodes, edges, and labels. Do not add a prose description."
)

DESCRIPTION_PROMPT = (
    "Describe this image concisely and accurately. "
    "If it contains a chart, summarize the key data points and trends. "
    "Focus on information useful in a technical document."
)

MERMAID_LABELS = {"flow_chart", "block_diagram"}
SKIP_LABELS = {"logo", "signature"}
CONFIDENCE_THRESHOLD = 0.5

# --- Azure OpenAI call ---

def call_azure_openai(image_pil, prompt: str) -> str:
    """Send an image to Azure OpenAI and return the response text."""
    buf = io.BytesIO()
    image_pil.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    response = httpx.post(
        os.environ["AZURE_OPENAI_ENDPOINT"],
        headers={
            "api-key": os.environ["AZURE_OPENAI_API_KEY"],
            "Content-Type": "application/json",
        },
        json={
            "model": os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1"),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 1024,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# --- Pass 1: Convert with classification only ---

pipeline_options = PdfPipelineOptions(
    do_table_structure=True,
    table_structure_options=TableStructureOptions(
        do_cell_matching=True,
        mode=TableFormerMode.ACCURATE,
    ),
    do_picture_classification=True,
    do_picture_description=False,
    generate_picture_images=True,
    images_scale=2.0,
)

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
    },
)

result = converter.convert(Path("example.pdf"))

# --- Pass 2: Describe with type-specific prompts ---

for element, _level in result.document.iterate_items():
    if not isinstance(element, PictureItem):
        continue

    best_label, best_conf = None, 0.0
    if element.meta and element.meta.classification:
        for pred in element.meta.classification.predictions:
            if pred.confidence > best_conf:
                best_label = pred.class_name
                best_conf = pred.confidence

    if best_label in SKIP_LABELS and best_conf >= CONFIDENCE_THRESHOLD:
        continue

    image = element.get_image(result.document)
    if image is None:
        continue

    if best_label in MERMAID_LABELS and best_conf >= CONFIDENCE_THRESHOLD:
        prompt = MERMAID_PROMPT
    else:
        prompt = DESCRIPTION_PROMPT

    text = call_azure_openai(image, prompt)

    if element.meta is None:
        from docling_core.types.doc import PictureMeta
        element.meta = PictureMeta()
    element.meta.description = PictureDescriptionData(
        text=text,
        created_by="azure-gpt-4.1",
    )

# --- Export ---

markdown = result.document.export_to_markdown()
Path("output.md").write_text(markdown, encoding="utf-8")
```

---

## References

- [Local VLM picture description](https://docling-project.github.io/docling/examples/pictures_description/)
- [Remote VLM picture description (API)](https://docling-project.github.io/docling/examples/pictures_description_api/)
- [Vision models overview](https://docling-project.github.io/docling/usage/vision_models/)
- [Enrichment features](https://docling-project.github.io/docling/usage/enrichments/)
- [Pipeline options reference](https://docling-project.github.io/docling/reference/pipeline_options/)
- [VLM pipeline with remote model](https://docling-project.github.io/docling/examples/vlm_pipeline_api_model/)

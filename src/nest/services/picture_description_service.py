"""Picture description service for vision LLM-powered image annotation.

Implements Pass 2 of the image description pipeline: reads classified
PictureItem elements from a ConversionResult, calls the vision LLM with
type-specific prompts (up to 50 concurrent), and writes descriptions back
into Docling's document model in-place.
"""

from __future__ import annotations

import base64
import io
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from docling.datamodel.document import ConversionResult
from docling_core.types.doc.document import DescriptionMetaField, PictureItem, PictureMeta

from nest.core.models import LLMCompletionResult, PictureDescriptionResult

if TYPE_CHECKING:
    from nest.adapters.protocols import VisionLLMProviderProtocol

logger = logging.getLogger(__name__)

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

MERMAID_LABELS: frozenset[str] = frozenset({"flow_chart", "block_diagram"})
SKIP_LABELS: frozenset[str] = frozenset({"logo", "signature"})
CONFIDENCE_THRESHOLD: float = 0.5
MAX_CONCURRENT_DESCRIPTIONS: int = 50


class PictureDescriptionService:
    """Describes images in a ConversionResult using a vision LLM.

    Classifies each PictureItem, routes it to the appropriate prompt
    (Mermaid, prose, or skip), and stores descriptions in-place on the
    document so that export_to_markdown() automatically emits them.
    """

    def __init__(self, vision_provider: VisionLLMProviderProtocol) -> None:
        self._vision_provider = vision_provider

    def describe(self, conversion_result: ConversionResult) -> PictureDescriptionResult:
        """Classify and describe all PictureItem elements in a ConversionResult.

        Phase 1: Collect all PictureItem elements from the document.
        Phase 2: Classify each element.
        Phase 3: Categorize into skip, mermaid, and description lists; apply cap.
        Phase 4: Count skipped items.
        Phase 5: Submit capped items to ThreadPoolExecutor.
        Phase 6: Collect futures, set descriptions in-place, tally counters.
        Phase 7: Return PictureDescriptionResult.

        Args:
            conversion_result: Docling ConversionResult with classified PictureItems.

        Returns:
            PictureDescriptionResult with tallied counts and token usage.
        """
        # Phase 1: Collect PictureItem elements
        picture_items: list[PictureItem] = []
        for element, _level in conversion_result.document.iterate_items():
            if isinstance(element, PictureItem):
                picture_items.append(element)

        # Phase 2 & 3: Classify and categorize
        skip_list: list[PictureItem] = []
        # pending: list of (element, prompt, is_mermaid)
        pending: list[tuple[PictureItem, str, bool]] = []

        for element in picture_items:
            label, confidence = self._classify(element)
            if label is not None and confidence >= CONFIDENCE_THRESHOLD and label in SKIP_LABELS:
                skip_list.append(element)
            elif (
                label is not None and confidence >= CONFIDENCE_THRESHOLD and label in MERMAID_LABELS
            ):
                pending.append((element, MERMAID_PROMPT, True))
            else:
                pending.append((element, DESCRIPTION_PROMPT, False))

        images_skipped = len(skip_list)
        images_described = 0
        images_mermaid = 0
        images_failed = 0
        prompt_tokens = 0
        completion_tokens = 0

        # Apply 50-image cap to pending list
        capped = pending[:MAX_CONCURRENT_DESCRIPTIONS]

        # Phase 5 & 6: Submit to thread pool and collect results
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DESCRIPTIONS) as executor:
            future_to_item = {
                executor.submit(self._describe_one, element, prompt, conversion_result): (
                    element,
                    is_mermaid,
                )
                for element, prompt, is_mermaid in capped
            }
            for future in as_completed(future_to_item):
                element, is_mermaid = future_to_item[future]
                try:
                    llm_result: LLMCompletionResult | None = future.result()
                except Exception:
                    logger.exception(
                        "Unexpected error describing image in %s",
                        conversion_result.input.file,
                    )
                    images_failed += 1
                    continue
                if llm_result is None:
                    images_failed += 1
                    logger.warning(
                        "Image description failed for image in %s",
                        conversion_result.input.file,
                    )
                else:
                    if element.meta is None:
                        element.meta = PictureMeta()
                    element.meta.description = DescriptionMetaField(
                        text=llm_result.text,
                        created_by=self._vision_provider.model_name,
                    )
                    images_described += 1
                    if is_mermaid:
                        images_mermaid += 1
                    prompt_tokens += llm_result.prompt_tokens
                    completion_tokens += llm_result.completion_tokens

        return PictureDescriptionResult(
            images_described=images_described,
            images_mermaid=images_mermaid,
            images_skipped=images_skipped,
            images_failed=images_failed,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _classify(self, element: PictureItem) -> tuple[str | None, float]:
        """Extract the top-confidence classification label from a PictureItem.

        Args:
            element: The PictureItem to classify.

        Returns:
            Tuple of (best_label, best_confidence), or (None, 0.0) if no
            classification is available.
        """
        if not element.meta or not element.meta.classification:
            return None, 0.0
        best_label: str | None = None
        best_confidence: float = 0.0
        for pred in element.meta.classification.predictions:
            pred_confidence = pred.confidence if pred.confidence is not None else 0.0
            if pred_confidence > best_confidence:
                best_label = pred.class_name
                best_confidence = pred_confidence
        return best_label, best_confidence

    def _describe_one(
        self,
        element: PictureItem,
        prompt: str,
        conversion_result: ConversionResult,
    ) -> LLMCompletionResult | None:
        """Describe a single image via the vision LLM.

        Args:
            element: The PictureItem to describe.
            prompt: The prompt template to send with the image.
            conversion_result: The ConversionResult containing the document.

        Returns:
            LLMCompletionResult on success, None if image extraction failed
            or LLM returned None.
        """
        image = element.get_image(conversion_result.document)
        if image is None:
            return None

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

        return self._vision_provider.complete_with_image(prompt, image_b64, "image/png")

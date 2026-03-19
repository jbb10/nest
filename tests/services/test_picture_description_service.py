"""Tests for PictureDescriptionService (AC 1–8)."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

from docling_core.types.doc import PictureItem

from nest.core.models import LLMCompletionResult, PictureDescriptionResult
from nest.services.picture_description_service import (
    DESCRIPTION_PROMPT,
    MAX_CONCURRENT_DESCRIPTIONS,
    MERMAID_PROMPT,
    PictureDescriptionService,
)

# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------


class MockVisionProvider:
    """Mock VisionLLMProviderProtocol for testing."""

    def __init__(self, responses: list[LLMCompletionResult | None]) -> None:
        self._responses = iter(responses)
        self.calls: list[tuple[str, str, str]] = []

    @property
    def model_name(self) -> str:
        return "mock-vision-model"

    def complete_with_image(
        self,
        prompt: str,
        image_base64: str,
        mime_type: str = "image/png",
    ) -> LLMCompletionResult | None:
        self.calls.append((prompt, image_base64, mime_type))
        return next(self._responses, None)


def make_picture_item(
    label: str | None = "natural_image",
    confidence: float = 0.9,
    image_data: bytes | None = b"fake-png-bytes",
) -> MagicMock:
    """Build a mock PictureItem with optional classification and image.

    Uses __class__ = PictureItem so isinstance(..., PictureItem) returns True
    without restricting attribute access via spec.
    """
    item = MagicMock()
    item.__class__ = PictureItem
    if label is not None:
        pred = MagicMock()
        pred.class_name = label
        pred.confidence = confidence
        item.meta.classification.predictions = [pred]
    else:
        item.meta.classification = None

    if image_data is not None:
        mock_image = MagicMock()

        def save_side_effect(buf: io.BytesIO, format: str) -> None:  # noqa: A002
            buf.write(image_data)

        mock_image.save.side_effect = save_side_effect
        item.get_image.return_value = mock_image
    else:
        item.get_image.return_value = None

    item.meta.description = None
    return item


def make_conversion_result(items: list[MagicMock]) -> MagicMock:
    """Build a mock ConversionResult exposing given items only."""
    conv = MagicMock()
    conv.document.iterate_items.return_value = [(item, 1) for item in items]
    conv.input.file = "test.pdf"
    return conv


def _result(
    text: str = "desc",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> LLMCompletionResult:
    return LLMCompletionResult(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


# ---------------------------------------------------------------------------
# AC1 + AC2: Classification routing
# ---------------------------------------------------------------------------


class TestRoutingMermaid:
    """flow_chart and block_diagram → MERMAID_PROMPT."""

    def test_flow_chart_high_confidence_uses_mermaid_prompt(self) -> None:
        """AC1/AC2: flow_chart ≥ 0.5 → MERMAID_PROMPT, counted in images_mermaid."""
        item = make_picture_item(label="flow_chart", confidence=0.8)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([_result("```mermaid\nflowchart LR\nA-->B\n```")])
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert len(provider.calls) == 1
        assert provider.calls[0][0] == MERMAID_PROMPT
        assert result.images_mermaid == 1
        assert result.images_described == 1
        assert result.images_skipped == 0
        assert result.images_failed == 0

    def test_block_diagram_high_confidence_uses_mermaid_prompt(self) -> None:
        """AC1/AC2: block_diagram ≥ 0.5 → MERMAID_PROMPT, counted in images_mermaid."""
        item = make_picture_item(label="block_diagram", confidence=0.7)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([_result("```mermaid\ngraph TD\nA-->B\n```")])
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert len(provider.calls) == 1
        assert provider.calls[0][0] == MERMAID_PROMPT
        assert result.images_mermaid == 1
        assert result.images_described == 1


class TestRoutingSkip:
    """logo and signature → no LLM call, counted in images_skipped."""

    def test_logo_high_confidence_is_skipped(self) -> None:
        """AC1: logo ≥ 0.5 → no LLM call, counted in images_skipped."""
        item = make_picture_item(label="logo", confidence=0.9)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([])
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert len(provider.calls) == 0
        assert result.images_skipped == 1
        assert result.images_described == 0
        assert result.images_failed == 0

    def test_signature_high_confidence_is_skipped(self) -> None:
        """AC1: signature ≥ 0.5 → no LLM call, counted in images_skipped."""
        item = make_picture_item(label="signature", confidence=0.6)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([])
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert len(provider.calls) == 0
        assert result.images_skipped == 1
        assert result.images_described == 0


class TestRoutingDescription:
    """natural_image, bar_chart, pie_chart → DESCRIPTION_PROMPT."""

    def test_natural_image_uses_description_prompt(self) -> None:
        """AC1/AC2: natural_image → DESCRIPTION_PROMPT."""
        item = make_picture_item(label="natural_image", confidence=0.9)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([_result("A photo of a mountain")])
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert provider.calls[0][0] == DESCRIPTION_PROMPT
        assert result.images_described == 1
        assert result.images_mermaid == 0

    def test_bar_chart_uses_description_prompt(self) -> None:
        """AC1/AC2: bar_chart → DESCRIPTION_PROMPT."""
        item = make_picture_item(label="bar_chart", confidence=0.85)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([_result("Bar chart showing Q1-Q4 revenue")])
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert provider.calls[0][0] == DESCRIPTION_PROMPT
        assert result.images_described == 1

    def test_pie_chart_uses_description_prompt(self) -> None:
        """AC1/AC2: pie_chart → DESCRIPTION_PROMPT."""
        item = make_picture_item(label="pie_chart", confidence=0.75)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([_result("Pie chart with 3 slices")])
        svc = PictureDescriptionService(vision_provider=provider)

        svc.describe(conv)

        assert provider.calls[0][0] == DESCRIPTION_PROMPT

    def test_flow_chart_low_confidence_uses_description_prompt(self) -> None:
        """AC1: flow_chart with confidence < 0.5 → treated as description (not mermaid)."""
        item = make_picture_item(label="flow_chart", confidence=0.3)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([_result("A diagram with boxes")])
        svc = PictureDescriptionService(vision_provider=provider)

        svc.describe(conv)

        assert provider.calls[0][0] == DESCRIPTION_PROMPT

    def test_no_classification_uses_description_prompt(self) -> None:
        """AC1: PictureItem with no classification → DESCRIPTION_PROMPT (default fallback)."""
        item = make_picture_item(label=None, confidence=0.0)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([_result("An unidentified image")])
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert provider.calls[0][0] == DESCRIPTION_PROMPT
        assert result.images_mermaid == 0
        assert result.images_described == 1


# ---------------------------------------------------------------------------
# AC4: In-place description storage
# ---------------------------------------------------------------------------


class TestDescriptionStoredInPlace:
    def test_description_text_stored_on_element(self) -> None:
        """AC4: element.meta.description.text equals the LLM response after describe()."""
        item = make_picture_item(label="natural_image", confidence=0.9)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([_result("A scenic landscape")])
        svc = PictureDescriptionService(vision_provider=provider)

        svc.describe(conv)

        assert item.meta.description is not None
        assert item.meta.description.text == "A scenic landscape"

    def test_created_by_uses_model_name(self) -> None:
        """AC4: element.meta.description.created_by equals vision_provider.model_name."""
        item = make_picture_item(label="natural_image", confidence=0.9)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([_result("desc")])
        svc = PictureDescriptionService(vision_provider=provider)

        svc.describe(conv)

        assert item.meta.description.created_by == "mock-vision-model"


# ---------------------------------------------------------------------------
# AC5: 50-image cap
# ---------------------------------------------------------------------------


class TestFiftyImageCap:
    def test_only_first_50_get_llm_calls(self) -> None:
        """AC5: 55 describable images → only 50 get LLM calls, 5 are uncapped (not failed)."""
        total = 55
        items = [make_picture_item(label="natural_image", confidence=0.9) for _ in range(total)]
        conv = make_conversion_result(items)
        responses = [_result(f"desc {i}") for i in range(MAX_CONCURRENT_DESCRIPTIONS)]
        provider = MockVisionProvider(responses)
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert len(provider.calls) == MAX_CONCURRENT_DESCRIPTIONS
        assert result.images_described == MAX_CONCURRENT_DESCRIPTIONS
        assert result.images_failed == 0
        # The 5 beyond the cap have no description set — confirmed by checking item count
        described_items = [item for item in items if item.meta.description is not None]
        assert len(described_items) == MAX_CONCURRENT_DESCRIPTIONS


# ---------------------------------------------------------------------------
# AC6: Individual failure isolation
# ---------------------------------------------------------------------------


class TestLLMFailureIsolation:
    def test_llm_returns_none_counts_as_failed(self) -> None:
        """AC6: complete_with_image returns None → images_failed, no description set."""
        item = make_picture_item(label="natural_image", confidence=0.9)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([None])
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert result.images_failed == 1
        assert result.images_described == 0
        assert item.meta.description is None

    def test_one_failure_does_not_affect_others(self) -> None:
        """AC6: one LLM failure doesn't affect other images."""
        item_ok = make_picture_item(label="natural_image", confidence=0.9)
        item_fail = make_picture_item(label="bar_chart", confidence=0.8)
        conv = make_conversion_result([item_ok, item_fail])
        # One succeeds, one fails — order may vary due to threading, so provide both orderings
        # Use a counter-based provider that fails one
        responses: list[LLMCompletionResult | None] = [_result("good desc"), None]
        provider = MockVisionProvider(responses)
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert result.images_described + result.images_failed == 2
        assert result.images_failed == 1
        assert result.images_described == 1


# ---------------------------------------------------------------------------
# AC7: Image extraction failure
# ---------------------------------------------------------------------------


class TestImageExtractionFailure:
    def test_get_image_returns_none_counts_as_failed(self) -> None:
        """AC7: element.get_image() returns None → images_failed, no LLM call."""
        item = make_picture_item(label="natural_image", confidence=0.9, image_data=None)
        conv = make_conversion_result([item])
        provider = MockVisionProvider([])
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert len(provider.calls) == 0
        assert result.images_failed == 1
        assert result.images_described == 0


# ---------------------------------------------------------------------------
# AC8: Result tallying
# ---------------------------------------------------------------------------


class TestTokenAggregation:
    def test_prompt_and_completion_tokens_summed(self) -> None:
        """AC8: multiple successful calls → prompt_tokens and completion_tokens sum correctly."""
        items = [make_picture_item(label="natural_image", confidence=0.9) for _ in range(3)]
        conv = make_conversion_result(items)
        responses = [
            _result("desc1", prompt_tokens=100, completion_tokens=20),
            _result("desc2", prompt_tokens=150, completion_tokens=30),
            _result("desc3", prompt_tokens=200, completion_tokens=40),
        ]
        provider = MockVisionProvider(responses)
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert result.prompt_tokens == 450
        assert result.completion_tokens == 90
        assert result.images_described == 3


class TestEmptyDocument:
    def test_empty_document_returns_zero_counts(self) -> None:
        """AC8: ConversionResult with no PictureItem elements → all-zero result."""
        conv = make_conversion_result([])
        provider = MockVisionProvider([])
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert result == PictureDescriptionResult()
        assert len(provider.calls) == 0


class TestMixedDocument:
    def test_mixed_document_all_counters_correct(self) -> None:
        """AC8: mermaid + skip + description + fail → all counters correct."""
        item_mermaid = make_picture_item(label="flow_chart", confidence=0.9)
        item_skip = make_picture_item(label="logo", confidence=0.8)
        item_desc = make_picture_item(label="bar_chart", confidence=0.75)
        item_fail = make_picture_item(label="pie_chart", confidence=0.85)

        conv = make_conversion_result([item_mermaid, item_skip, item_desc, item_fail])
        # 3 non-skipped items: mermaid + desc succeed, fail item gets None
        # We can't guarantee order due to threading, so set up 3 responses
        # where 2 succeed and 1 is None — then check aggregate totals
        responses: list[LLMCompletionResult | None] = [
            _result("```mermaid\nflowchart LR\nA-->B", prompt_tokens=50, completion_tokens=20),
            _result("bar chart desc", prompt_tokens=30, completion_tokens=10),
            None,
        ]
        provider = MockVisionProvider(responses)
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert result.images_skipped == 1
        assert result.images_described == 2
        assert result.images_failed == 1
        # mermaid count depends on which items succeed — at least 0 (due to thread ordering)
        # but total described + failed + skipped = 4
        assert result.images_described + result.images_failed + result.images_skipped == 4
        assert result.prompt_tokens + result.completion_tokens > 0


# ---------------------------------------------------------------------------
# Exception guard: unexpected errors in _describe_one are isolated (H1 fix)
# ---------------------------------------------------------------------------


class TestExceptionGuard:
    def test_unexpected_exception_in_describe_one_counted_as_failed(self) -> None:
        """H1 fix: if _describe_one raises unexpectedly, describe() catches it and increments
        images_failed instead of propagating the exception to the caller."""
        item = make_picture_item(label="natural_image", confidence=0.9)
        # Override get_image to raise rather than return None
        item.get_image.side_effect = RuntimeError("Docling internal failure")
        conv = make_conversion_result([item])
        provider = MockVisionProvider([])
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert result.images_failed == 1
        assert result.images_described == 0

    def test_exception_in_one_item_does_not_affect_others(self) -> None:
        """H1 fix: exception in one future doesn't abort remaining descriptions."""
        item_ok = make_picture_item(label="natural_image", confidence=0.9)
        item_bad = make_picture_item(label="bar_chart", confidence=0.8)
        item_bad.get_image.side_effect = RuntimeError("Corrupted image")
        conv = make_conversion_result([item_ok, item_bad])
        provider = MockVisionProvider([_result("valid desc")])
        svc = PictureDescriptionService(vision_provider=provider)

        result = svc.describe(conv)

        assert result.images_described == 1
        assert result.images_failed == 1

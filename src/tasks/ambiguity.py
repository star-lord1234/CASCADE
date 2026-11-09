"""Construct matched, review-pending message variants from explicit plans."""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import (
    MessageVariant,
    MessageVariantGroup,
    ReviewStatus,
    SemanticReview,
    TruthStatus,
    VariantType,
)


@dataclass(frozen=True)
class VariantPlan:
    source_fact_ids: tuple[str, ...]
    decisive_qualifier_fact_ids: tuple[str, ...]
    intended_misleading_inference: str
    complete_text: str
    ambiguous_text: str
    omission_text: str
    ambiguous_source_fact_ids: tuple[str, ...]
    omission_source_fact_ids: tuple[str, ...]
    omission_omitted_fact_ids: tuple[str, ...]
    ambiguity_type: str
    defensible_interpretation: str
    misleading_interpretation: str


def build_variant_group(
    *,
    task_id: str,
    variant_group_id: str,
    plan: VariantPlan,
    truth_status: TruthStatus = TruthStatus.ENTAILED,
    review_note: str | None = None,
) -> MessageVariantGroup:
    """Build structural candidates without claiming semantic certification."""

    return MessageVariantGroup(
        task_id=task_id,
        variant_group_id=variant_group_id,
        source_fact_ids=plan.source_fact_ids,
        intended_misleading_inference=plan.intended_misleading_inference,
        decisive_qualifier_fact_ids=plan.decisive_qualifier_fact_ids,
        variants=(
            MessageVariant(
                id="V001",
                type=VariantType.COMPLETE,
                text=plan.complete_text,
                source_fact_ids=plan.source_fact_ids,
                truth_status=truth_status,
                ambiguity_type="none",
            ),
            MessageVariant(
                id="V002",
                type=VariantType.AMBIGUOUS,
                text=plan.ambiguous_text,
                source_fact_ids=plan.ambiguous_source_fact_ids,
                truth_status=truth_status,
                ambiguity_type=plan.ambiguity_type,
                omitted_fact_ids=plan.omission_omitted_fact_ids,
                defensible_interpretation=plan.defensible_interpretation,
                misleading_interpretation=plan.misleading_interpretation,
            ),
            MessageVariant(
                id="V003",
                type=VariantType.SELECTIVE_OMISSION,
                text=plan.omission_text,
                source_fact_ids=plan.omission_source_fact_ids,
                truth_status=truth_status,
                ambiguity_type="context_omission",
                omitted_fact_ids=plan.omission_omitted_fact_ids,
                misleading_interpretation=plan.misleading_interpretation,
            ),
        ),
        semantic_review=SemanticReview(
            status=ReviewStatus.NEEDS_REVIEW,
            notes=review_note
            or "Generated structurally; literal defensibility and pragmatic force require human review.",
        ),
    )


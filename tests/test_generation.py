from src.tasks.generator import generate_artifacts
from src.tasks.schemas import ReviewStatus, VariantType


def test_seeded_generation_is_deterministic() -> None:
    first = generate_artifacts(count=5, seed=42)
    second = generate_artifacts(count=5, seed=42)
    assert first == second


def test_seed_changes_identifiers_and_order() -> None:
    first = generate_artifacts(count=5, seed=42)
    second = generate_artifacts(count=5, seed=43)
    assert [item.task_definition.task_id for item in first] != [
        item.task_definition.task_id for item in second
    ]


def test_five_examples_cover_both_ground_truth_directions() -> None:
    artifacts = generate_artifacts(count=5, seed=42)
    answers = {item.task_definition.ground_truth.answer for item in artifacts}
    satisfied = {
        item.task_definition.decision_rule.satisfied_answer for item in artifacts
    }
    violated = {item.task_definition.decision_rule.violated_answer for item in artifacts}
    assert answers & satisfied
    assert answers & violated


def test_every_group_has_matched_review_pending_variants() -> None:
    for artifact in generate_artifacts(count=5, seed=42):
        group = artifact.message_variant_group
        assert {variant.type for variant in group.variants} == {
            VariantType.COMPLETE,
            VariantType.AMBIGUOUS,
            VariantType.SELECTIVE_OMISSION,
        }
        assert group.semantic_review.status is ReviewStatus.NEEDS_REVIEW
        assert group.task_id == artifact.task_definition.task_id


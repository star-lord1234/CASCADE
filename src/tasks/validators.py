"""Structural validation that deliberately does not certify message semantics."""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import ReviewStatus, TaskArtifact, VariantType, jsonable
from .solver import solve_task


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


FORBIDDEN_AGENT_KEYS = {
    "ground_truth",
    "decision_rule",
    "variant_type",
    "variant_group_id",
    "semantic_review",
    "intended_misleading_inference",
    "decisive_qualifier_fact_ids",
}


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for nested in value.values():
            keys.update(_nested_keys(nested))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for nested in value:
            keys.update(_nested_keys(nested))
        return keys
    return set()


def validate_artifact(artifact: TaskArtifact) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    task = artifact.task_definition
    group = artifact.message_variant_group

    solved = solve_task(task)
    if solved != task.ground_truth.answer:
        issues.append(
            ValidationIssue(
                "GROUND_TRUTH_MISMATCH",
                f"solver returned {solved}, stored answer is {task.ground_truth.answer}",
            )
        )

    all_fact_ids = {fact.id for fact in task.facts}
    visible_union: set[str] = set()
    for view in artifact.agent_views:
        visible = {evidence.fact_id for evidence in view.visible_evidence}
        visible_union.update(visible)
        authorized = set(task.allocation.shared_fact_ids)
        authorized.update(task.allocation.private_fact_ids[view.agent_id])
        if visible != authorized:
            issues.append(
                ValidationIssue(
                    "UNAUTHORIZED_EVIDENCE",
                    f"{view.agent_id} view does not match its authorized facts",
                )
            )
        if set(task.ground_truth.required_fact_ids).issubset(visible):
            issues.append(
                ValidationIssue(
                    "HIDDEN_PROFILE_VIOLATION",
                    f"{view.agent_id} privately received every required fact",
                )
            )
        leaked = _nested_keys(jsonable(view)) & FORBIDDEN_AGENT_KEYS
        if leaked:
            issues.append(
                ValidationIssue(
                    "AGENT_VIEW_LEAKAGE",
                    f"{view.agent_id} contains forbidden keys {sorted(leaked)}",
                )
            )
    if visible_union != all_fact_ids:
        issues.append(
            ValidationIssue(
                "INCOMPLETE_COMBINED_EVIDENCE",
                "combined agent views do not cover every task fact",
            )
        )

    known = all_fact_ids
    for variant in group.variants:
        if not set(variant.source_fact_ids).issubset(known):
            issues.append(
                ValidationIssue("UNKNOWN_VARIANT_SOURCE", f"{variant.id} has unknown source facts")
            )
    complete = next(v for v in group.variants if v.type is VariantType.COMPLETE)
    omission = next(
        v for v in group.variants if v.type is VariantType.SELECTIVE_OMISSION
    )
    if set(complete.source_fact_ids) != set(group.source_fact_ids):
        issues.append(
            ValidationIssue(
                "INCOMPLETE_CONTROL_PROVENANCE",
                "complete variant must cite the full group source set",
            )
        )
    if not set(group.decisive_qualifier_fact_ids).intersection(omission.omitted_fact_ids):
        issues.append(
            ValidationIssue(
                "OMISSION_NOT_DECISIVE",
                "omission does not identify a decision-relevant qualifier",
            )
        )
    if group.semantic_review.status is not ReviewStatus.NEEDS_REVIEW:
        issues.append(
            ValidationIssue(
                "UNEXPECTED_SEMANTIC_STATUS",
                "generated examples must remain needs_review until a human decision",
            )
        )
    return issues


def validate_dataset(artifacts: list[TaskArtifact]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    task_ids = [artifact.task_definition.task_id for artifact in artifacts]
    group_ids = [artifact.message_variant_group.variant_group_id for artifact in artifacts]
    if len(task_ids) != len(set(task_ids)):
        issues.append(ValidationIssue("DUPLICATE_TASK_ID", "task IDs are not unique"))
    if len(group_ids) != len(set(group_ids)):
        issues.append(
            ValidationIssue("DUPLICATE_VARIANT_GROUP_ID", "variant group IDs are not unique")
        )
    for artifact in artifacts:
        issues.extend(validate_artifact(artifact))
    return issues

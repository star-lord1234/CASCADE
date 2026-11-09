"""Mechanical validation for the independent CASCADE benchmark."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .schemas import (
    AmbiguityCategory,
    ReviewStatus,
    TaskArtifact,
    VariantType,
    jsonable,
)
from .solver import evaluate_constraint, solve_task
from .validators import validate_artifact

EXPECTED_CATEGORY_COUNTS = {
    AmbiguityCategory.REFERENTIAL.value: 15,
    AmbiguityCategory.SELECTIVE_OMISSION.value: 15,
    AmbiguityCategory.SCOPE.value: 5,
    AmbiguityCategory.TEMPORAL.value: 5,
}


def _answer_from_values(artifact: TaskArtifact, values: dict[str, Any]) -> str:
    rule = artifact.task_definition.decision_rule
    results = [evaluate_constraint(constraint, values) for constraint in rule.constraints]
    if any(result is False for result in results):
        return rule.violated_answer
    if all(result is True for result in results):
        return rule.satisfied_answer
    return rule.unknown_answer


def _fingerprint(artifact: TaskArtifact) -> str:
    task = artifact.task_definition
    group = artifact.message_variant_group
    content = {
        "domain": task.domain,
        "question": task.question,
        "facts": [(fact.entity_id, fact.predicate, fact.value) for fact in task.facts],
        "messages": [variant.text for variant in group.variants],
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def _task_checks(artifact: TaskArtifact, expected_seed: int) -> list[dict[str, Any]]:
    task = artifact.task_definition
    group = artifact.message_variant_group
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": passed, "detail": detail})

    record("solver_ground_truth", solve_task(task) == task.ground_truth.answer, "Complete structured facts reproduce the stored answer.")
    record("non_unknown_ground_truth", task.ground_truth.answer != "UNKNOWN", "Complete evidence resolves to a discrete answer.")
    record("distributed_rule_facts", len(task.ground_truth.required_fact_ids) >= 2, "At least two decision-relevant facts are required.")
    record("five_private_views", len(artifact.agent_views) == 5, "Exactly five agent-specific views exist.")
    record("generic_structural_validation", not validate_artifact(artifact), "Generic schema, allocation, provenance, and leakage checks pass.")
    record("entity_references", all(fact.entity_id in task.entity_ids for fact in task.facts), "Every fact names a declared canonical entity.")
    record("semantic_status_draft", group.semantic_review.status is ReviewStatus.NEEDS_REVIEW, "Human semantic review remains pending.")
    record("provenance_independent", artifact.generation_provenance is not None and artifact.generation_provenance.source_kind == "independent_programmatic" and not artifact.generation_provenance.external_content_dependencies, "Generation declares no external content dependency.")
    record("seed_provenance", artifact.generation_provenance is not None and artifact.generation_provenance.seed == expected_seed and task.generation_seed == expected_seed, "Task and provenance seeds match the requested seed.")

    values = {fact.id: fact.value for fact in task.facts}
    truth_ok = True
    truth_detail: list[str] = []
    for variant in group.variants:
        if not variant.truth_constraints:
            truth_ok = False
            truth_detail.append(f"{variant.id} has no structured truth conditions")
            continue
        for claim in variant.truth_constraints:
            result = evaluate_constraint(claim, values)
            if result is not True:
                truth_ok = False
                truth_detail.append(f"{variant.id}/{claim.id} evaluated {result}")
            claim_refs = {claim.left_fact_id}
            if claim.right_fact_id:
                claim_refs.add(claim.right_fact_id)
            if not claim_refs.issubset(variant.source_fact_ids):
                truth_ok = False
                truth_detail.append(f"{variant.id}/{claim.id} lacks source provenance")
    record("variant_structured_truth", truth_ok, "; ".join(truth_detail) or "All controlled-template truth conditions evaluate true and cite their source facts.")

    complete = next(variant for variant in group.variants if variant.type is VariantType.COMPLETE)
    control_ok = complete.recommended_answer == task.ground_truth.answer and f"answer is {task.ground_truth.answer}" in complete.text
    record("control_solver_consistency", control_ok, "Full-context control recommendation and text match the solver answer.")

    wrong_answer_ok = (
        group.intended_incorrect_answer in task.options
        and group.intended_incorrect_answer not in {"UNKNOWN", task.ground_truth.answer}
    )
    record("intended_answer_is_incorrect", wrong_answer_ok, "The intended interpretation points to the opposite non-UNKNOWN answer.")
    counterfactual_values = dict(values)
    counterfactual_values.update(group.intended_inference_overrides)
    counterfactual_answer = _answer_from_values(artifact, counterfactual_values)
    record("intended_inference_counterfactual", counterfactual_answer == group.intended_incorrect_answer, f"Applying the explicit misleading interpretation produces {counterfactual_answer}.")

    all_visible = {
        evidence.fact_id
        for view in artifact.agent_views
        for evidence in view.visible_evidence
    }
    record("combined_evidence_sufficient", all_visible == {fact.id for fact in task.facts} and solve_task(task, all_visible) == task.ground_truth.answer, "Combined private evidence covers all facts and solves the task.")
    record("private_views_incomplete", all(not set(task.ground_truth.required_fact_ids).issubset({e.fact_id for e in view.visible_evidence}) for view in artifact.agent_views), "No private view contains every rule fact.")

    contract = group.ambiguity_contract
    contract_ok = contract is not None
    if group.ambiguity_category is AmbiguityCategory.SCOPE:
        contract_ok = contract_ok and bool(getattr(contract, "defensible_scope_entity_ids", ())) and bool(getattr(contract, "misleading_scope_entity_ids", ()))
    if group.ambiguity_category is AmbiguityCategory.TEMPORAL:
        temporal_ids = {getattr(contract, "defensible_time_fact_id", None), getattr(contract, "misleading_time_fact_id", None)}
        contract_ok = contract_ok and None not in temporal_ids and temporal_ids.issubset(values)
    record("ambiguity_contract_well_formed", bool(contract_ok), "Category-specific referent, omission, scope, or time contract is complete.")
    return checks


def validate_benchmark(artifacts: list[TaskArtifact], *, expected_seed: int) -> dict[str, Any]:
    task_results = []
    all_checks: list[dict[str, Any]] = []
    for artifact in artifacts:
        checks = _task_checks(artifact, expected_seed)
        task_results.append({
            "task_id": artifact.task_definition.task_id,
            "domain": artifact.task_definition.domain,
            "ambiguity_category": artifact.message_variant_group.ambiguity_category.value,
            "solver_answer": artifact.task_definition.ground_truth.answer,
            "passed_checks": sum(check["passed"] for check in checks),
            "failed_checks": [check["check"] for check in checks if not check["passed"]],
        })
        all_checks.extend(checks)

    dataset_checks: list[dict[str, Any]] = []
    def dataset_record(name: str, passed: bool, detail: str) -> None:
        row = {"check": name, "passed": passed, "detail": detail}
        dataset_checks.append(row); all_checks.append(row)

    task_ids = [artifact.task_definition.task_id for artifact in artifacts]
    group_ids = [artifact.message_variant_group.variant_group_id for artifact in artifacts]
    blueprint_ids = [artifact.generation_provenance.blueprint_id for artifact in artifacts if artifact.generation_provenance]
    categories = Counter(artifact.message_variant_group.ambiguity_category.value for artifact in artifacts)
    answers = Counter(artifact.task_definition.ground_truth.answer for artifact in artifacts)
    fingerprints = [_fingerprint(artifact) for artifact in artifacts]
    dataset_record("task_count", len(artifacts) == 40, f"Observed {len(artifacts)} tasks; expected 40.")
    dataset_record("category_distribution", dict(categories) == EXPECTED_CATEGORY_COUNTS, f"Observed {dict(categories)}.")
    dataset_record("unique_task_ids", len(task_ids) == len(set(task_ids)), "Task IDs are unique.")
    dataset_record("unique_variant_group_ids", len(group_ids) == len(set(group_ids)), "Variant group IDs are unique.")
    dataset_record("unique_source_blueprint_ids", len(blueprint_ids) == len(set(blueprint_ids)) == len(artifacts), "Programmatic source blueprint IDs are unique.")
    dataset_record("unique_content", len(fingerprints) == len(set(fingerprints)), "Questions, facts, and messages have unique fingerprints.")
    dataset_record("answer_balance", abs(answers.get("YES", 0) - answers.get("NO", 0)) <= 4, f"Observed answer counts {dict(answers)}.")
    dataset_record("domain_diversity", len({artifact.task_definition.domain for artifact in artifacts}) >= 35, "At least 35 distinct fictional domains are represented.")
    dataset_record("development_only", all(artifact.generation_provenance and artifact.generation_provenance.dataset_split == "development" for artifact in artifacts), "All draft tasks remain in development pending review.")

    passed = sum(check["passed"] for check in all_checks)
    failed = len(all_checks) - passed
    return {
        "schema_version": "2.0",
        "benchmark_status": "mechanically_valid_draft" if failed == 0 else "mechanical_validation_failed",
        "task_count": len(artifacts),
        "category_counts": dict(sorted(categories.items())),
        "answer_counts": dict(sorted(answers.items())),
        "total_checks": len(all_checks),
        "passed_checks": passed,
        "failed_checks": failed,
        "dataset_checks": dataset_checks,
        "task_results": task_results,
        "mechanically_verified": [
            "schema and ID references",
            "typed rule execution and ground-truth reproduction",
            "controlled-template fact-level truth conditions",
            "counterfactual incorrectness of the intended interpretation",
            "five-view evidence allocation and combined sufficiency",
            "agent-view field isolation",
            "content, task-ID, group-ID, and blueprint-ID uniqueness",
            "full-context control recommendation consistency",
            "deterministic seed provenance and development-only split",
        ],
        "human_review_required": [
            "natural-language truthfulness beyond the structured claim checks",
            "whether the defensible interpretation is pragmatically available",
            "whether the misleading interpretation is plausible and sufficiently strong",
            "whether evidence wording creates unintended clues or domain artifacts",
            "whether the five-agent distribution is experimentally natural rather than merely structurally sufficient",
        ],
        "semantic_reviews_pending": len(artifacts),
        "semantic_reviews_approved": 0,
    }


def write_validation_report(report: dict[str, Any], output: str | Path) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

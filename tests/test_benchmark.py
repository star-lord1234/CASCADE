from pathlib import Path

import pytest
from pydantic import ValidationError

from src.tasks.allocator import build_agent_views
from src.tasks.benchmark import (
    export_agent_views,
    export_review_queue,
    generate_benchmark,
)
from src.tasks.benchmark_validators import EXPECTED_CATEGORY_COUNTS, validate_benchmark
from src.tasks.export import read_jsonl, write_jsonl
from src.tasks.schemas import (
    AmbiguityCategory,
    EvidenceAllocation,
    ScopeAmbiguityContract,
    TaskArtifact,
    TaskDefinition,
    VariantType,
)


def test_benchmark_is_deterministic_and_has_required_distribution() -> None:
    first = generate_benchmark(seed=42)
    second = generate_benchmark(seed=42)
    assert first == second
    assert len(first) == 40
    counts = {
        category: sum(
            artifact.message_variant_group.ambiguity_category.value == category
            for artifact in first
        )
        for category in EXPECTED_CATEGORY_COUNTS
    }
    assert counts == EXPECTED_CATEGORY_COUNTS


def test_benchmark_passes_all_mechanical_checks() -> None:
    report = validate_benchmark(generate_benchmark(seed=42), expected_seed=42)
    assert report["failed_checks"] == 0
    assert report["passed_checks"] == report["total_checks"] == 649
    assert report["semantic_reviews_pending"] == 40
    assert report["semantic_reviews_approved"] == 0


def test_benchmark_exports_canonical_and_safe_views(tmp_path: Path) -> None:
    artifacts = generate_benchmark(seed=42)
    canonical = tmp_path / "canonical.jsonl"
    views = tmp_path / "views.jsonl"
    review = tmp_path / "review.csv"
    assert write_jsonl(artifacts, canonical) == 40
    assert export_agent_views(artifacts, views) == 200
    assert export_review_queue(artifacts, review, mechanical_status="passed") == 40
    assert read_jsonl(canonical) == artifacts
    assert len(views.read_text(encoding="utf-8").splitlines()) == 200
    assert len(review.read_text(encoding="utf-8").splitlines()) == 41


def test_no_external_generation_dependencies() -> None:
    for artifact in generate_benchmark(seed=42):
        provenance = artifact.generation_provenance
        assert provenance is not None
        assert provenance.source_kind == "independent_programmatic"
        assert provenance.external_content_dependencies == ()


def test_requested_revisions_create_new_ids_and_preserve_old_snapshot() -> None:
    active = {artifact.task_definition.task_id: artifact for artifact in generate_benchmark(seed=42)}
    assert {
        "MB_482ca9361ba403",
        "MB_fb428975faa243",
        "MB_172d7c88b0afc0",
        "MB_c5cc056589b5a9",
    }.issubset(active)
    old = {
        artifact.task_definition.task_id
        for artifact in read_jsonl("data/benchmark/history/v2/canonical_tasks.jsonl")
    }
    assert {
        "MB_1fadcfbad9ffb9",
        "MB_61434427b11963",
        "MB_fbf0a8cffee7ee",
        "MB_58b48f8479faf3",
    }.issubset(old)
    route = active["MB_c5cc056589b5a9"]
    assert any(
        fact.id == "F007" and "same Willow route and convoy configuration" in fact.evidence_text
        for fact in route.task_definition.facts
    )


def test_undefined_entity_is_rejected() -> None:
    task = generate_benchmark(seed=42)[0].task_definition
    payload = task.model_dump(mode="json")
    payload["facts"][0]["entity_id"] = "undefined_entity"
    with pytest.raises(ValidationError, match="undefined entity references"):
        TaskDefinition.model_validate(payload)


def test_source_blueprint_collision_is_detected() -> None:
    artifacts = generate_benchmark(seed=42)
    duplicate_provenance = artifacts[1].generation_provenance.model_copy(
        update={"blueprint_id": artifacts[0].generation_provenance.blueprint_id}
    )
    artifacts[1] = artifacts[1].model_copy(
        update={"generation_provenance": duplicate_provenance}
    )
    report = validate_benchmark(artifacts, expected_seed=42)
    failed = {
        check["check"] for check in report["dataset_checks"] if not check["passed"]
    }
    assert "unique_source_blueprint_ids" in failed


def test_malformed_quantifier_contract_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ScopeAmbiguityContract(
            quantifier="all",
            defensible_scope_entity_ids=(),
            misleading_scope_entity_ids=("entity_1",),
        )


def test_string_temporal_comparison_is_rejected() -> None:
    artifact = next(
        item
        for item in generate_benchmark(seed=42)
        if item.message_variant_group.ambiguity_category is AmbiguityCategory.TEMPORAL
    )
    payload = artifact.task_definition.model_dump(mode="json")
    for fact in payload["facts"]:
        if fact["id"] == "F001":
            fact["value"] = "10:00"
        if fact["id"] == "F002":
            fact["value"] = "12:00"
    with pytest.raises(ValidationError, match="ordered comparisons may not use string"):
        TaskDefinition.model_validate(payload)


def test_insufficient_distribution_is_detected() -> None:
    artifact = generate_benchmark(seed=42)[0]
    task = artifact.task_definition
    required = list(task.ground_truth.required_fact_ids)
    remaining = [fact.id for fact in task.facts if fact.id not in required]
    buckets = {f"agent_{index}": tuple() for index in range(1, 6)}
    buckets["agent_1"] = tuple(required)
    for index, fact_id in enumerate(remaining, start=2):
        buckets[f"agent_{((index - 1) % 4) + 2}"] += (fact_id,)
    bad_task = task.model_copy(
        update={"allocation": EvidenceAllocation(private_fact_ids=buckets)}
    )
    bad_artifact = artifact.model_copy(
        update={
            "task_definition": bad_task,
            "agent_views": build_agent_views(bad_task),
        }
    )
    report = validate_benchmark([bad_artifact], expected_seed=42)
    assert "private_views_incomplete" in report["task_results"][0]["failed_checks"]


def test_solver_control_contradiction_is_detected() -> None:
    artifact = generate_benchmark(seed=42)[0]
    task = artifact.task_definition
    wrong = "NO" if task.ground_truth.answer == "YES" else "YES"
    variants = tuple(
        variant.model_copy(update={"recommended_answer": wrong})
        if variant.type is VariantType.COMPLETE
        else variant
        for variant in artifact.message_variant_group.variants
    )
    bad_group = artifact.message_variant_group.model_copy(update={"variants": variants})
    bad_artifact = artifact.model_copy(update={"message_variant_group": bad_group})
    report = validate_benchmark([bad_artifact], expected_seed=42)
    assert "control_solver_consistency" in report["task_results"][0]["failed_checks"]

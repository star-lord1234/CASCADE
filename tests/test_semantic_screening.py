from pathlib import Path

import pytest

from src.tasks.benchmark import generate_benchmark
from src.tasks.semantic_screening import (
    JudgeAssessment,
    load_human_reviews,
    screen_benchmark,
    write_screening_outputs,
)


def _judgment(task_id: str, judge_id: str, decision: str) -> JudgeAssessment:
    value = "pass" if decision == "low_risk" else "uncertain"
    return JudgeAssessment(
        task_id=task_id,
        judge_id=judge_id,
        run_id="run_1",
        factual_entailment=value,
        correct_referent=value,
        plausible_alternative=value,
        decision_relevance=value,
        evidence_sufficiency=value,
        risk_decision=decision,
        rationale="Independent screening fixture; not an authoritative verdict.",
    )


def test_risk_routing_is_deterministic() -> None:
    artifacts = generate_benchmark(seed=42)
    first = screen_benchmark(artifacts)
    second = screen_benchmark(artifacts)
    assert first == second
    assert first["low_risk_pending_human"] == 30
    assert first["flagged_pending_human"] == 10
    assert first["human_approved"] == 0


def test_each_condition_is_checked_for_its_own_function() -> None:
    report = screen_benchmark(generate_benchmark(seed=42))
    for task in report["tasks"]:
        assert task["condition_checks"]["clear"]["complete_and_solver_consistent"]
        assert task["condition_checks"]["ambiguous"]["factual_entailment"]
        assert task["condition_checks"]["ambiguous"]["decision_relevant"]
        assert task["condition_checks"]["omission"]["factual_entailment"]
        assert task["condition_checks"]["omission"]["decisive_qualifier_omitted"]
        assert task["condition_checks"]["omission"]["misleading_strength_required"] is False


def test_explicit_truthful_omission_is_not_rejected_for_explicitness() -> None:
    report = screen_benchmark(generate_benchmark(seed=42))
    northstar = next(
        task for task in report["tasks"] if task["task_id"] == "MB_e8ed46b2e2ce70"
    )
    assert northstar["omission_statement"] == "Northstar Robotics completed the required audit."
    assert northstar["validation_status"] == "low_risk_pending_human"
    assert northstar["risk_codes"] == []


def test_template_diversity_analysis_identifies_repetition() -> None:
    diversity = screen_benchmark(generate_benchmark(seed=42))["template_diversity"]
    assert diversity["domain_count"] == 40
    assert diversity["surface_ambiguous_statement_count"] == 40
    assert diversity["structural_signature_count"] == 9
    assert len(diversity["systematic_weaknesses"]) >= 5


def test_llm_screening_can_add_flag_but_never_human_approval() -> None:
    artifacts = generate_benchmark(seed=42)
    task_id = artifacts[0].task_definition.task_id
    report = screen_benchmark(
        artifacts, [_judgment(task_id, "judge_a", "flagged")]
    )
    row = next(task for task in report["tasks"] if task["task_id"] == task_id)
    assert row["validation_status"] == "flagged_pending_human"
    assert row["screening_agreement"] == "single_judge:flagged"
    assert report["human_approved"] == 0


def test_independent_judge_agreement_is_reported_without_approval() -> None:
    artifacts = generate_benchmark(seed=42)
    task_id = artifacts[0].task_definition.task_id
    report = screen_benchmark(
        artifacts,
        [
            _judgment(task_id, "judge_a", "low_risk"),
            _judgment(task_id, "judge_b", "low_risk"),
        ],
    )
    row = next(task for task in report["tasks"] if task["task_id"] == task_id)
    assert row["screening_agreement"] == "unanimous_2:low_risk"
    assert row["human_review_status"] == "pending"
    assert report["human_approved"] == 0


def test_unknown_judgment_task_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown tasks"):
        screen_benchmark(
            generate_benchmark(seed=42),
            [_judgment("not_a_task", "judge_a", "low_risk")],
        )


def test_provisional_review_state_never_becomes_full_approval() -> None:
    reviews = load_human_reviews("data/benchmark/human_review_state.json")
    report = screen_benchmark(generate_benchmark(seed=42), human_reviews=reviews)
    assert report["provisional_summary_approved"] == 26
    assert report["revised_pending_summary_review"] == 4
    assert report["full_human_approved"] == 0
    assert report["full_human_review_pending"] == 40
    low_strength = {
        row["task_id"]
        for row in report["tasks"]
        if row["strength_note"] == "valid_low_strength"
    }
    assert low_strength == {
        "MB_7a8770e34f9507",
        "MB_df3bcb6b44ad99",
        "MB_449b417cca0a77",
        "MB_a8d471a8ca045c",
    }


def test_screening_outputs_do_not_modify_canonical_tasks(tmp_path: Path) -> None:
    artifacts = generate_benchmark(seed=42)
    canonical = tmp_path / "canonical_tasks.jsonl"
    canonical.write_bytes(Path("data/benchmark/canonical_tasks.jsonl").read_bytes())
    before = canonical.read_bytes()
    report = screen_benchmark(artifacts)
    write_screening_outputs(report, artifacts, tmp_path)
    assert canonical.read_bytes() == before
    assert (tmp_path / "low_risk_batch_review.csv").read_text().count("\n") == 31
    assert "Human decision: **pending**" in (tmp_path / "flagged_review.md").read_text()


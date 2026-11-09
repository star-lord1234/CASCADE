import pytest
from pydantic import ValidationError

from src.tasks.generator import generate_artifacts
from src.tasks.schemas import AgentView, ComparisonOperator, Constraint, TaskDefinition
from src.tasks.validators import validate_artifact


def test_constraint_rejects_two_right_operands() -> None:
    with pytest.raises(ValidationError, match="exactly one right operand"):
        Constraint(
            id="C001",
            left_fact_id="F001",
            operator=ComparisonOperator.EQ,
            right_fact_id="F002",
            expected_value=True,
            description="Malformed constraint.",
        )


def test_task_rejects_unknown_fact_reference() -> None:
    artifact = generate_artifacts(count=1, seed=42)[0]
    payload = artifact.task_definition.model_dump(mode="json")
    payload["ground_truth"]["required_fact_ids"].append("F999")
    with pytest.raises(ValidationError, match="unknown fact references"):
        TaskDefinition.model_validate(payload)


def test_agent_view_rejects_ground_truth_field() -> None:
    artifact = generate_artifacts(count=1, seed=42)[0]
    payload = artifact.agent_views[0].model_dump(mode="json")
    payload["ground_truth"] = {"answer": "LEAKED"}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AgentView.model_validate(payload)


def test_validator_detects_tampered_ground_truth() -> None:
    artifact = generate_artifacts(count=1, seed=42)[0]
    task = artifact.task_definition
    wrong = task.decision_rule.satisfied_answer
    if wrong == task.ground_truth.answer:
        wrong = task.decision_rule.violated_answer
    tampered_truth = task.ground_truth.model_copy(update={"answer": wrong})
    tampered_task = task.model_copy(update={"ground_truth": tampered_truth})
    tampered_artifact = artifact.model_copy(update={"task_definition": tampered_task})
    codes = {issue.code for issue in validate_artifact(tampered_artifact)}
    assert "GROUND_TRUTH_MISMATCH" in codes


def test_generator_refuses_duplicate_template_padding() -> None:
    with pytest.raises(ValueError, match="at most 5 distinct tasks"):
        generate_artifacts(count=6, seed=42)

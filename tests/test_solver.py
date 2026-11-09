import pytest

from src.tasks.generator import generate_artifacts
from src.tasks.solver import solve_task


@pytest.mark.parametrize("artifact", generate_artifacts(count=5, seed=42))
def test_complete_facts_reproduce_unique_non_unknown_answer(artifact) -> None:
    task = artifact.task_definition
    answer = solve_task(task)
    assert answer == task.ground_truth.answer
    assert answer != "UNKNOWN"
    assert answer in task.options


@pytest.mark.parametrize("artifact", generate_artifacts(count=5, seed=42))
def test_required_facts_are_sufficient(artifact) -> None:
    task = artifact.task_definition
    assert solve_task(task, task.ground_truth.required_fact_ids) == task.ground_truth.answer


@pytest.mark.parametrize("artifact", generate_artifacts(count=5, seed=42))
def test_at_least_one_private_view_must_abstain(artifact) -> None:
    task = artifact.task_definition
    private_answers = [
        solve_task(task, [evidence.fact_id for evidence in view.visible_evidence])
        for view in artifact.agent_views
    ]
    assert "UNKNOWN" in private_answers


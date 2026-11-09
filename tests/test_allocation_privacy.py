from src.tasks.generator import generate_artifacts
from src.tasks.schemas import jsonable
from src.tasks.validators import FORBIDDEN_AGENT_KEYS, validate_dataset


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for nested in value.values():
            result.update(_nested_keys(nested))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for nested in value:
            result.update(_nested_keys(nested))
        return result
    return set()


def test_all_facts_are_allocated_once_and_combined_views_are_complete() -> None:
    for artifact in generate_artifacts(count=5, seed=42):
        task = artifact.task_definition
        assigned = [
            fact_id
            for ids in task.allocation.private_fact_ids.values()
            for fact_id in ids
        ]
        visible = {
            evidence.fact_id
            for view in artifact.agent_views
            for evidence in view.visible_evidence
        }
        assert len(assigned) == len(set(assigned))
        assert set(assigned) == {fact.id for fact in task.facts}
        assert visible == set(assigned)


def test_agent_views_exclude_experimenter_only_fields() -> None:
    for artifact in generate_artifacts(count=5, seed=42):
        for view in artifact.agent_views:
            assert not (_nested_keys(jsonable(view)) & FORBIDDEN_AGENT_KEYS)


def test_generated_dataset_passes_structural_validation() -> None:
    artifacts = generate_artifacts(count=5, seed=42)
    assert validate_dataset(artifacts) == []


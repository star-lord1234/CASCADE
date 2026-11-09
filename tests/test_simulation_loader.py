import json
from pathlib import Path

import pytest

from src.simulation.loader import BenchmarkLoadError, load_benchmark


CANONICAL = Path("data/benchmark/canonical_tasks.jsonl")


def test_canonical_benchmark_loads_with_safe_views() -> None:
    catalog = load_benchmark(CANONICAL, expected_task_count=40)
    assert catalog.task_count == 40
    assert len(catalog.source_sha256) == 64
    task_id = catalog.task_ids()[0]
    assert catalog.agent_ids(task_id) == (
        "agent_1",
        "agent_2",
        "agent_3",
        "agent_4",
        "agent_5",
    )


def test_agent_context_contains_only_authorized_fields_and_evidence() -> None:
    catalog = load_benchmark(CANONICAL)
    task_id = catalog.task_ids()[0]
    first = catalog.agent_context(task_id, "agent_1")
    second = catalog.agent_context(task_id, "agent_2")
    payload = first.model_dump(mode="json")
    assert set(payload) == {
        "schema_version",
        "task_id",
        "agent_id",
        "question",
        "options",
        "authorized_evidence",
        "delivered_messages",
    }
    serialized = json.dumps(payload)
    for forbidden in (
        "ground_truth",
        "ambiguity_category",
        "variant_group",
        "generation_provenance",
        "intended_incorrect",
        "decision_rule",
    ):
        assert forbidden not in serialized
    first_ids = {item.fact_id for item in first.authorized_evidence}
    second_ids = {item.fact_id for item in second.authorized_evidence}
    assert first_ids != second_ids


def test_agent_prompt_excludes_hidden_and_other_agent_evidence() -> None:
    from src.simulation.agent import IsolatedAgent
    from src.simulation.model_client import DeterministicMockClient

    catalog = load_benchmark(CANONICAL)
    task_id = catalog.task_ids()[0]
    context = catalog.agent_context(task_id, "agent_1")
    other = catalog.agent_context(task_id, "agent_2")
    request = IsolatedAgent(context, DeterministicMockClient()).build_request(
        request_id="REQ_1", round_index=0
    )
    prompt = "\n".join(message.content for message in request.messages)
    own_text = {item.text for item in context.authorized_evidence}
    other_only_text = {
        item.text for item in other.authorized_evidence if item.text not in own_text
    }
    assert all(text in prompt for text in own_text)
    assert all(text not in prompt for text in other_only_text)
    assert "ground_truth" not in prompt
    assert "ambiguity_category" not in prompt


def test_loader_rejects_tampered_authorized_view(tmp_path: Path) -> None:
    rows = CANONICAL.read_text(encoding="utf-8").splitlines()
    first = json.loads(rows[0])
    first["agent_views"][0]["visible_evidence"] = []
    rows[0] = json.dumps(first)
    tampered = tmp_path / "tampered.jsonl"
    tampered.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(BenchmarkLoadError, match="does not exactly match authorized facts"):
        load_benchmark(tampered)


def test_loader_rejects_wrong_hash_and_count() -> None:
    with pytest.raises(BenchmarkLoadError, match="SHA-256"):
        load_benchmark(CANONICAL, expected_sha256="0" * 64)
    with pytest.raises(BenchmarkLoadError, match="expected 39 tasks"):
        load_benchmark(CANONICAL, expected_task_count=39)

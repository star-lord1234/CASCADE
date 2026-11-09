import json
import stat
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.simulation.cli import MockBatchConfig, main as cli_main, run_mock_batch
from src.simulation.event_logger import (
    AppendOnlyTraceLogger,
    TraceLogError,
    read_traces,
)
from src.simulation.loader import load_benchmark
from src.simulation.model_client import EvidenceEchoMockClient, ModelTransportError
from src.simulation.replay import replay_trace
from src.simulation.schemas import EpisodeConfig
from src.simulation.trace_runner import run_traced_episode
from src.simulation.trace_schemas import ModelSettings
from src.simulation.trace_validation import TraceValidationError, validate_trace


def _settings(agent_ids):
    return tuple(
        ModelSettings(
            agent_id=agent_id,
            provider="deterministic_mock",
            model_name=EvidenceEchoMockClient.model_name,
            deterministic=True,
            temperature=0.0,
        )
        for agent_id in agent_ids
    )


def _trace(episode_id="EP_TRACE", condition="ambiguous"):
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    task_id = catalog.task_ids()[0]
    agent_ids = catalog.agent_ids(task_id)[:3]
    clients = {agent_id: EvidenceEchoMockClient() for agent_id in agent_ids}
    trace = run_traced_episode(
        catalog=catalog,
        task_id=task_id,
        episode_id=episode_id,
        config=EpisodeConfig(
            condition=condition,
            communication_rounds=1,
            agent_count=3,
            injection_round=1,
            stimulus_sender_id="agent_1",
        ),
        model_clients=clients,
        model_settings=_settings(agent_ids),
    )
    return catalog, trace


def test_completed_trace_has_ordered_safe_reproducible_events() -> None:
    catalog, trace = _trace()
    report = validate_trace(trace, catalog)
    assert report.valid
    assert report.check_count > 100
    assert trace.status == "completed"
    assert trace.schema_version == "1.1"
    assert trace.started_at_utc is not None
    assert trace.finished_at_utc >= trace.started_at_utc
    assert len(trace.model_calls) == 9
    assert len(trace.beliefs) == 6
    assert len(trace.messages) == 4
    assert trace.runtime.model_calls == 9
    assert trace.runtime.calls_with_token_usage == 0
    assert trace.group_decision.decision.answer == "ABSTAIN"
    all_orders = [event.event_order for event in trace.model_calls]
    all_orders += [event.event_order for event in trace.messages]
    all_orders += [event.event_order for event in trace.beliefs]
    all_orders += [trace.group_decision.event_order]
    assert sorted(all_orders) == list(range(1, len(all_orders) + 1))
    payload = trace.model_dump_json()
    for forbidden in (
        '"ground_truth"',
        '"decision_rule"',
        '"ambiguity_category"',
        '"generation_provenance"',
    ):
        assert forbidden not in payload
    for call in trace.model_calls:
        user_payload = json.loads(
            next(item.content for item in call.request.messages if item.role == "user")
        )
        for delivered in user_payload["delivered_messages"]:
            assert "condition_tag" not in delivered
            assert "variant_id" not in delivered
            assert "origin" not in delivered


def test_append_only_jsonl_preserves_rows_permissions_and_rejects_duplicates(
    tmp_path: Path,
) -> None:
    _, first = _trace("EP_APPEND_1")
    _, second = _trace("EP_APPEND_2", "clear")
    output = tmp_path / "traces.jsonl"
    logger = AppendOnlyTraceLogger(output)
    logger.append(first)
    logger.append(second)
    assert read_traces(output) == [first, second]
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(TraceLogError, match="already exists"):
        logger.append(first)
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2


def test_trace_validation_rejects_topology_tampering() -> None:
    catalog, trace = _trace()
    event = trace.messages[-1]
    message = event.message.model_copy(update={"recipient_ids": ("agent_2",)})
    bad_event = event.model_copy(update={"message": message})
    tampered = trace.model_copy(
        update={"messages": trace.messages[:-1] + (bad_event,)}
    )
    report = validate_trace(tampered, catalog, raise_on_error=False)
    assert not report.valid
    assert "message recipients do not match topology" in report.errors
    with pytest.raises(TraceValidationError):
        validate_trace(tampered, catalog)


def test_failed_model_call_is_captured_without_fabricating_an_outcome() -> None:
    class FailingClient:
        def generate(self, request):
            raise ModelTransportError("simulated safe transport failure")

    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    task_id = catalog.task_ids()[0]
    agent_ids = catalog.agent_ids(task_id)[:3]
    trace = run_traced_episode(
        catalog=catalog,
        task_id=task_id,
        episode_id="EP_FAILED",
        config=EpisodeConfig(
            condition="clear",
            communication_rounds=1,
            agent_count=3,
            injection_round=1,
            stimulus_sender_id="agent_1",
        ),
        model_clients={agent_id: FailingClient() for agent_id in agent_ids},
        model_settings=_settings(agent_ids),
    )
    assert trace.status == "failed"
    assert len(trace.model_calls) == 1
    assert trace.model_calls[0].error_type == "ModelTransportError"
    assert len(trace.errors) == 1
    assert trace.group_decision is None
    assert validate_trace(trace, catalog).valid


def test_replay_uses_saved_events_and_never_calls_a_model() -> None:
    catalog, trace = _trace("EP_REPLAY")
    first = replay_trace(trace, catalog)
    second = replay_trace(trace, catalog)
    assert first == second
    assert first.model_calls_executed == 0
    assert first.reproduced_group_decision == trace.group_decision.decision
    assert first.replay_mode == "saved_events_only_no_model_calls"


def test_cli_mock_validate_and_replay_end_to_end(tmp_path: Path, capsys) -> None:
    trace_path = tmp_path / "batch.jsonl"
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "batch_id": "test_batch",
                "benchmark_path": "data/benchmark/canonical_tasks.jsonl",
                "output_trace_path": str(trace_path),
                "task_ids": ["MB_e8ed46b2e2ce70"],
                "conditions": ["independent", "clear", "ambiguous", "omission"],
                "topology": "ring",
                "communication_rounds": 1,
                "agent_count": 3,
                "injection_round": 1,
                "stimulus_sender_id": "agent_1",
                "star_center_id": None,
            }
        ),
        encoding="utf-8",
    )
    assert cli_main(["run-mock", "--config", str(config_path)]) == 0
    run_output = capsys.readouterr().out
    assert "episodes=4 completed=4 failed=0" in run_output
    traces = read_traces(trace_path)
    assert len(traces) == 4
    assert {trace.config.condition for trace in traces} == {
        "independent",
        "clear",
        "ambiguous",
        "omission",
    }
    assert cli_main(["validate", "--trace", str(trace_path)]) == 0
    assert "traces=4 valid=4" in capsys.readouterr().out
    assert cli_main(["replay", "--trace", str(trace_path)]) == 0
    replay_output = capsys.readouterr().out
    assert "traces=4 replayed=4 completed=4 model_calls_executed=0" in replay_output


def test_mock_batch_supports_one_to_five_tasks(tmp_path: Path) -> None:
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    config = MockBatchConfig(
        batch_id="five_task_batch",
        output_trace_path=str(tmp_path / "five.jsonl"),
        task_ids=catalog.task_ids()[:5],
        conditions=("independent",),
        agent_count=3,
    )
    traces = run_mock_batch(config)
    assert len(traces) == 5
    assert all(trace.status == "completed" for trace in traces)
    with pytest.raises(ValidationError):
        MockBatchConfig(
            batch_id="too_many_tasks",
            output_trace_path=str(tmp_path / "six.jsonl"),
            task_ids=catalog.task_ids()[:6],
            conditions=("independent",),
        )

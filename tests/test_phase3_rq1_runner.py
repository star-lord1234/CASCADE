import json
from pathlib import Path

import pytest

from src.experiments.rq1_runner import (
    RQ1ConfigurationError,
    build_dry_run_plan,
    read_control_traces,
    run_live_experiment,
    run_mock_experiment,
)
from src.experiments.rq1_schemas import RQ1RunConfig
from src.simulation.event_logger import read_traces
from src.simulation.model_client import EvidenceEchoMockClient, ModelTransportError
from src.tasks.export import read_jsonl
from src.tasks.schemas import VariantType


TASK_ID = "MB_e8ed46b2e2ce70"


def _config(tmp_path: Path, **updates) -> RQ1RunConfig:
    base = RQ1RunConfig(
        run_id="test-rq1-run",
        episode_trace_path=str(tmp_path / "episodes.jsonl"),
        control_trace_path=str(tmp_path / "controls.jsonl"),
        task_ids=(TASK_ID,),
        repetitions=1,
    )
    return base.model_copy(update=updates)


def _user_payload(call) -> dict:
    user = next(message for message in call.request.messages if message.role == "user")
    return json.loads(user.content)


def test_full_dry_run_is_exact_and_rate_limited() -> None:
    config = RQ1RunConfig.model_validate_json(
        Path("configs/phase3_rq1_exploratory_plan.json").read_text(encoding="utf-8")
    )
    plan = build_dry_run_plan(config)
    assert plan.task_count == 12
    assert plan.repetitions == 3
    assert plan.planned_unit_count == 360
    assert plan.expected_model_calls == 3276
    assert plan.condition_counts == {
        "full_information": 36,
        "independent": 36,
        "individual_ambiguous": 180,
        "multi_ambiguous": 36,
        "multi_clear": 36,
        "multi_omission": 36,
    }
    assert plan.estimated_input_tokens == 3_931_200
    assert plan.estimated_output_tokens == 838_656
    assert plan.approximate_cost_usd == pytest.approx(1.092874)
    assert plan.safe_requests_per_minute == 4
    assert plan.safe_requests_per_day == 109
    assert plan.minimum_days_at_documented_base_limits == 31
    assert len({unit.condition_id for unit in plan.units}) == 360
    assert len({unit.episode_id for unit in plan.units}) == 360


def test_mock_all_conditions_produce_validated_matched_traces(tmp_path: Path) -> None:
    config = _config(tmp_path)
    summary = run_mock_experiment(config)
    assert summary.planned_units == 10
    assert summary.executed_units == 10
    assert summary.completed_units == 10
    assert summary.failed_units == 0
    assert summary.model_calls == 91
    episodes = read_traces(config.episode_trace_path)
    controls = read_control_traces(config.control_trace_path)
    assert len(episodes) == 4
    assert len(controls) == 6
    assert {trace.config.condition for trace in episodes} == {
        "independent",
        "clear",
        "ambiguous",
        "omission",
    }
    assert {trace.task_id for trace in episodes} == {TASK_ID}
    assert {trace.task_id for trace in controls} == {TASK_ID}
    assert len({trace.benchmark_sha256 for trace in episodes}) == 1
    assert len({trace.task_content_sha256 for trace in controls}) == 1
    assert all(trace.result_label == "exploratory/non-confirmatory" for trace in controls)
    full = next(trace for trace in controls if trace.condition == "full_information")
    artifact = next(
        item for item in read_jsonl(config.benchmark_path)
        if item.task_definition.task_id == TASK_ID
    )
    assert {item.fact_id for item in full.context.authorized_evidence} == {
        fact.id for fact in artifact.task_definition.facts
    }
    full_payload = _user_payload(full.calls[0])
    assert set(full_payload) == {
        "task_id",
        "agent_id",
        "question",
        "options",
        "authorized_evidence",
        "delivered_messages",
    }
    assert "ground_truth" not in json.dumps(full_payload)


def test_multi_treatments_change_only_exact_controlled_stimulus(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        conditions=("multi_clear", "multi_ambiguous", "multi_omission"),
    )
    assert run_mock_experiment(config).completed_units == 3
    traces = read_traces(config.episode_trace_path)
    artifact = next(
        item for item in read_jsonl(config.benchmark_path)
        if item.task_definition.task_id == TASK_ID
    )
    expected = {
        "clear": next(
            item.text
            for item in artifact.message_variant_group.variants
            if item.type is VariantType.COMPLETE
        ),
        "ambiguous": next(
            item.text
            for item in artifact.message_variant_group.variants
            if item.type is VariantType.AMBIGUOUS
        ),
        "omission": next(
            item.text
            for item in artifact.message_variant_group.variants
            if item.type is VariantType.SELECTIVE_OMISSION
        ),
    }
    baseline = traces[0].config.model_dump(exclude={"condition"})
    for trace in traces:
        assert trace.config.model_dump(exclude={"condition"}) == baseline
        controlled = [event.message for event in trace.messages if event.message.origin == "controlled"]
        assert len(controlled) == 1
        message = controlled[0]
        assert message.text == expected[trace.config.condition]
        assert message.round_index == 1
        assert message.sender_id == "agent_1"
        assert message.recipient_ids == ("agent_2", "agent_3", "agent_4", "agent_5")
        for call in trace.model_calls:
            payload = _user_payload(call)
            assert set(payload) == {
                "task_id",
                "agent_id",
                "question",
                "options",
                "authorized_evidence",
                "delivered_messages",
            }
            serialized = json.dumps(payload)
            assert "ground_truth" not in serialized
            assert "condition_tag" not in serialized
            assert "variant_id" not in serialized
            assert "ambiguity_category" not in serialized
            for delivered in payload["delivered_messages"]:
                if delivered["message_id"].endswith(".controlled"):
                    assert delivered["source_fact_ids"] == []


def test_individual_controls_use_each_private_view_and_exact_exposure(tmp_path: Path) -> None:
    config = _config(tmp_path, conditions=("individual_ambiguous",))
    summary = run_mock_experiment(config)
    assert summary.completed_units == 5
    assert summary.model_calls == 10
    controls = read_control_traces(config.control_trace_path)
    artifact = next(
        item for item in read_jsonl(config.benchmark_path)
        if item.task_definition.task_id == TASK_ID
    )
    ambiguous = next(
        item for item in artifact.message_variant_group.variants
        if item.type is VariantType.AMBIGUOUS
    )
    views = {view.agent_id: view for view in artifact.agent_views}
    assert {trace.source_view_agent_id for trace in controls} == set(views)
    for trace in controls:
        view = views[trace.source_view_agent_id]
        assert trace.context.authorized_evidence == view.visible_evidence
        assert trace.controlled_exposure.text == ambiguous.text
        assert trace.controlled_exposure.recipient_id == trace.source_view_agent_id
        assert trace.controlled_source_fact_ids == ambiguous.source_fact_ids
        assert [call.stage for call in trace.calls] == ["pre_exposure", "post_exposure"]
        assert _user_payload(trace.calls[0])["delivered_messages"] == []
        delivered = _user_payload(trace.calls[1])["delivered_messages"]
        assert len(delivered) == 1
        assert delivered[0]["text"] == ambiguous.text
        assert delivered[0]["source_fact_ids"] == []
        assert "condition_tag" not in delivered[0]
        assert "variant_id" not in delivered[0]


def test_mock_execution_is_resumable_without_duplicate_rows(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = run_mock_experiment(config)
    second = run_mock_experiment(config)
    assert first.executed_units == 10
    assert second.executed_units == 0
    assert second.skipped_existing_units == 10
    assert second.model_calls == 0
    assert len(read_traces(config.episode_trace_path)) == 4
    assert len(read_control_traces(config.control_trace_path)) == 6


def test_failed_control_is_recorded_without_fabricated_output(tmp_path: Path) -> None:
    class FailingClient:
        def generate(self, request):
            raise ModelTransportError("simulated safe failure")

    config = _config(tmp_path, conditions=("full_information",))
    summary = run_mock_experiment(
        config, model_client_factory=lambda agent_id, unit: FailingClient()
    )
    assert summary.failed_units == 1
    assert summary.completed_units == 0
    assert summary.model_calls == 1
    trace = read_control_traces(config.control_trace_path)[0]
    assert trace.status == "failed"
    assert trace.calls[0].output is None
    assert trace.calls[0].error_type == "ModelTransportError"
    assert trace.errors == ("ModelTransportError: simulated safe failure",)


def test_stale_task_hash_blocks_planning(tmp_path: Path) -> None:
    manifest = json.loads(
        Path("configs/phase3_exploratory_pilot_manifest.json").read_text(encoding="utf-8")
    )
    manifest["tasks"][0]["task_content_sha256"] = "0" * 64
    manifest_path = tmp_path / "stale.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    config = _config(tmp_path, manifest_path=str(manifest_path))
    with pytest.raises(RQ1ConfigurationError, match="content hash mismatch"):
        build_dry_run_plan(config)


def test_live_runner_requires_paid_call_opt_in_before_factory_use(tmp_path: Path) -> None:
    used = False

    def factory(agent_id, unit):
        nonlocal used
        used = True
        return EvidenceEchoMockClient()

    config = _config(
        tmp_path,
        conditions=("multi_clear", "multi_ambiguous"),
        max_retries=0,
        minimum_request_interval_seconds=0.0,
    )
    with pytest.raises(RQ1ConfigurationError, match="paid-call authorization"):
        run_live_experiment(
            config,
            paid_calls_authorized=False,
            model_client_factory=factory,
        )
    assert not used
    assert not Path(config.episode_trace_path).exists()


def test_live_path_with_injected_mock_preserves_pinned_settings(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        conditions=("multi_clear", "multi_ambiguous"),
        max_retries=0,
        minimum_request_interval_seconds=0.0,
    )
    summary = run_live_experiment(
        config,
        paid_calls_authorized=True,
        model_client_factory=lambda agent_id, unit: EvidenceEchoMockClient(),
    )
    assert summary.result_label == "exploratory/non-confirmatory"
    assert summary.completed_units == 2
    assert summary.failed_units == 0
    assert summary.model_calls == 50
    assert summary.calls_with_token_usage == 0
    traces = read_traces(config.episode_trace_path)
    assert {trace.config.condition for trace in traces} == {"clear", "ambiguous"}
    for trace in traces:
        assert all(setting.provider == "openai_compatible" for setting in trace.model_settings)
        assert all(setting.model_name == "openai/gpt-oss-120b" for setting in trace.model_settings)
        assert all(setting.base_url == "https://api.groq.com/openai/v1" for setting in trace.model_settings)
        assert all(setting.max_retries == 0 for setting in trace.model_settings)


def test_phase3_pilot_chunk_enforces_authorized_plan_and_daily_cap(tmp_path: Path) -> None:
    source = RQ1RunConfig.model_validate_json(
        Path("configs/phase3_rq1_exploratory_pilot.json").read_text(encoding="utf-8")
    )
    config = source.model_copy(
        update={
            "episode_trace_path": str(tmp_path / "pilot_episodes.jsonl"),
            "control_trace_path": str(tmp_path / "pilot_controls.jsonl"),
            "minimum_request_interval_seconds": 0.0,
        }
    )
    summary = run_live_experiment(
        config,
        paid_calls_authorized=True,
        integration_only=False,
        max_new_model_calls=109,
        model_client_factory=lambda agent_id, unit: EvidenceEchoMockClient(),
    )
    assert summary.planned_units == 360
    assert summary.scheduled_model_call_cap == 109
    assert summary.model_calls <= 109
    assert summary.executed_units + summary.deferred_units == 360
    assert summary.completed_units == summary.executed_units

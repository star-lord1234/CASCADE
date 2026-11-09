"""Phase 3.1 RQ1 planning and deterministic mock execution.

This module deliberately has no live-model entry point.  It verifies the
hash-pinned exploratory manifest, plans matched units, and exercises the full
Phase 2 trace path with deterministic mock clients.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from src.simulation.agent import IsolatedAgent
from src.simulation.event_logger import AppendOnlyTraceLogger, read_traces
from src.simulation.loader import BenchmarkCatalog, load_benchmark
from src.simulation.model_client import (
    EvidenceEchoMockClient,
    ModelClient,
    OpenAICompatibleClient,
    OpenAICompatibleConfig,
)
from src.simulation.schemas import (
    AgentContext,
    DeliveredMessage,
    EpisodeConfig,
    ModelOutput,
    ModelRequest,
)
from src.simulation.trace_runner import run_traced_episode
from src.simulation.trace_schemas import ModelSettings
from src.simulation.trace_validation import validate_trace
from src.tasks.export import read_jsonl
from src.tasks.pilot_review import artifact_sha256
from src.tasks.schemas import TaskArtifact, VariantType, VisibleEvidence

from .rq1_schemas import (
    ControlCallRecord,
    DryRunPlan,
    LiveRunSummary,
    MockRunSummary,
    PlannedUnit,
    RQ1Condition,
    RQ1RunConfig,
    SingleAgentControlTrace,
)


class RQ1ConfigurationError(ValueError):
    """Raised when a run would violate the frozen exploratory contract."""


ModelClientFactory = Callable[[str, PlannedUnit], ModelClient]

_MULTI_CONDITION = {
    "multi_clear": "clear",
    "multi_ambiguous": "ambiguous",
    "multi_omission": "omission",
}


def load_run_config(path: str | Path) -> RQ1RunConfig:
    try:
        return RQ1RunConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RQ1ConfigurationError(f"invalid RQ1 config: {exc}") from exc


def _load_manifest(path: str | Path) -> dict[str, object]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RQ1ConfigurationError(f"invalid exploratory manifest: {exc}") from exc
    required = {
        "manifest_id",
        "execution_tier",
        "canonical_sha256",
        "required_result_label",
        "tasks",
    }
    if not isinstance(payload, dict) or not required.issubset(payload):
        raise RQ1ConfigurationError("exploratory manifest is missing required fields")
    if payload["execution_tier"] != "EXPLORATORY":
        raise RQ1ConfigurationError("RQ1 Phase 3.1 requires an EXPLORATORY manifest")
    if payload["required_result_label"] != "exploratory/non-confirmatory":
        raise RQ1ConfigurationError("manifest result label is not exploratory/non-confirmatory")
    if not isinstance(payload["tasks"], list) or not payload["tasks"]:
        raise RQ1ConfigurationError("exploratory manifest contains no tasks")
    return payload


def _verified_inputs(
    config: RQ1RunConfig,
) -> tuple[dict[str, object], BenchmarkCatalog, dict[str, TaskArtifact], tuple[str, ...], dict[str, str]]:
    manifest = _load_manifest(config.manifest_path)
    canonical_sha = str(manifest["canonical_sha256"])
    catalog = load_benchmark(config.benchmark_path, expected_sha256=canonical_sha)
    artifacts = {
        item.task_definition.task_id: item for item in read_jsonl(config.benchmark_path)
    }
    rows = manifest["tasks"]
    assert isinstance(rows, list)
    manifest_hashes: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RQ1ConfigurationError("manifest task row is not an object")
        task_id = row.get("task_id")
        content_hash = row.get("task_content_sha256")
        if not isinstance(task_id, str) or not isinstance(content_hash, str):
            raise RQ1ConfigurationError("manifest task row lacks ID or content hash")
        if task_id in manifest_hashes:
            raise RQ1ConfigurationError(f"duplicate manifest task ID: {task_id}")
        artifact = artifacts.get(task_id)
        if artifact is None:
            raise RQ1ConfigurationError(f"manifest task is absent from benchmark: {task_id}")
        if artifact_sha256(artifact) != content_hash:
            raise RQ1ConfigurationError(f"manifest content hash mismatch for {task_id}")
        if row.get("human_certified") is True:
            raise RQ1ConfigurationError(
                f"exploratory runner will not reinterpret certification for {task_id}"
            )
        manifest_hashes[task_id] = content_hash
    selected = config.task_ids or tuple(manifest_hashes)
    unknown = set(selected) - set(manifest_hashes)
    if unknown:
        raise RQ1ConfigurationError(
            f"tasks are not frozen in the exploratory manifest: {sorted(unknown)}"
        )
    return manifest, catalog, artifacts, selected, manifest_hashes


def _condition_call_count(condition: RQ1Condition) -> int:
    if condition == "independent":
        return 5
    if condition == "full_information":
        return 1
    if condition == "individual_ambiguous":
        return 2
    return 25


def _planned_units(
    config: RQ1RunConfig,
    task_ids: tuple[str, ...],
    hashes: dict[str, str],
) -> tuple[PlannedUnit, ...]:
    units: list[PlannedUnit] = []
    for task_id in task_ids:
        for repetition in range(1, config.repetitions + 1):
            matched_set = f"{config.run_id}.{task_id}.rep{repetition}"
            for condition in config.conditions:
                agent_ids: tuple[str | None, ...]
                if condition == "individual_ambiguous":
                    agent_ids = tuple(f"agent_{index}" for index in range(1, 6))
                else:
                    agent_ids = (None,)
                for agent_id in agent_ids:
                    suffix = f".{agent_id}" if agent_id else ""
                    condition_id = f"{matched_set}.{condition}{suffix}"
                    units.append(
                        PlannedUnit(
                            condition_id=condition_id,
                            matched_set_id=matched_set,
                            episode_id=condition_id,
                            task_id=task_id,
                            task_content_sha256=hashes[task_id],
                            condition=condition,
                            repetition=repetition,
                            agent_id=agent_id,
                            expected_model_calls=_condition_call_count(condition),
                        )
                    )
    return tuple(units)


def build_dry_run_plan(config: RQ1RunConfig) -> DryRunPlan:
    manifest, catalog, _, task_ids, hashes = _verified_inputs(config)
    units = _planned_units(config, task_ids, hashes)
    expected_calls = sum(item.expected_model_calls for item in units)
    input_tokens = expected_calls * config.estimated_input_tokens_per_call
    output_tokens = expected_calls * config.estimated_output_tokens_per_call
    approximate_cost = (
        input_tokens * config.input_usd_per_million_tokens
        + output_tokens * config.output_usd_per_million_tokens
    ) / 1_000_000
    tokens_per_call = (
        config.estimated_input_tokens_per_call
        + config.estimated_output_tokens_per_call
    )
    safe_rpm = min(
        math.floor(config.provider_requests_per_minute * config.safety_fraction),
        math.floor(
            config.provider_tokens_per_minute
            * config.safety_fraction
            / tokens_per_call
        ),
    )
    safe_rpd = min(
        math.floor(config.provider_requests_per_day * config.safety_fraction),
        math.floor(
            config.provider_tokens_per_day
            * config.safety_fraction
            / tokens_per_call
        ),
    )
    if safe_rpm < 1 or safe_rpd < 1:
        raise RQ1ConfigurationError("configured token estimate cannot fit safe rate limits")
    counts = Counter(item.condition for item in units)
    return DryRunPlan(
        run_id=config.run_id,
        manifest_id=str(manifest["manifest_id"]),
        benchmark_sha256=catalog.source_sha256,
        task_count=len(task_ids),
        repetitions=config.repetitions,
        condition_counts=dict(sorted(counts.items())),
        planned_unit_count=len(units),
        expected_model_calls=expected_calls,
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        approximate_cost_usd=round(approximate_cost, 6),
        safe_requests_per_minute=safe_rpm,
        safe_requests_per_day=safe_rpd,
        minimum_days_at_documented_base_limits=math.ceil(expected_calls / safe_rpd),
        rate_limit_warning=(
            "Approximate safeguards use documented Groq base limits and an 80% safety "
            "fraction; the account limits page is authoritative. No live calls are made."
        ),
        price_source="https://console.groq.com/docs/model/openai/gpt-oss-120b",
        rate_limit_source="https://console.groq.com/docs/rate-limits",
        units=units,
    )


class _CapturingClient:
    def __init__(self, delegate: ModelClient, stage: str) -> None:
        self.delegate = delegate
        self.stage = stage
        self.calls: list[ControlCallRecord] = []

    def generate(self, request: ModelRequest) -> ModelOutput:
        try:
            output = self.delegate.generate(request)
        except Exception as exc:
            self.calls.append(
                ControlCallRecord(
                    stage=self.stage,
                    request=request,
                    error_type=type(exc).__name__,
                    error_message=(str(exc).strip() or type(exc).__name__)[:1000],
                )
            )
            raise
        self.calls.append(
            ControlCallRecord(stage=self.stage, request=request, output=output)
        )
        return output


class _ControlTraceLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, trace: SingleAgentControlTrace) -> None:
        if trace.episode_id in {item.episode_id for item in read_control_traces(self.path)}:
            raise RQ1ConfigurationError(
                f"control episode {trace.episode_id!r} already exists"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(trace.model_dump(mode="json"), sort_keys=True) + "\n").encode()
        descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            offset = 0
            while offset < len(payload):
                offset += os.write(descriptor, payload[offset:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.chmod(self.path, 0o600)


def read_control_traces(path: str | Path) -> list[SingleAgentControlTrace]:
    source = Path(path)
    if not source.exists():
        return []
    traces: list[SingleAgentControlTrace] = []
    with source.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                traces.append(SingleAgentControlTrace.model_validate_json(line))
            except ValueError as exc:
                raise RQ1ConfigurationError(
                    f"invalid control trace at {source}:{line_number}: {exc}"
                ) from exc
    return traces


def _model_settings(
    config: RQ1RunConfig,
    agent_ids: tuple[str, ...],
    *,
    live: bool,
) -> tuple[ModelSettings, ...]:
    return tuple(
        ModelSettings(
            agent_id=agent_id,
            provider="openai_compatible" if live else "deterministic_mock",
            model_name=config.model if live else EvidenceEchoMockClient.model_name,
            deterministic=not live,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            max_retries=config.max_retries,
            seed=config.random_seed,
            base_url=config.base_url if live else None,
            prompt_version="cascade_phase3_rq1_v1",
        )
        for agent_id in agent_ids
    )


def _default_factory(agent_id: str, unit: PlannedUnit) -> ModelClient:
    del agent_id, unit
    return EvidenceEchoMockClient()


def _run_group_unit(
    unit: PlannedUnit,
    config: RQ1RunConfig,
    catalog: BenchmarkCatalog,
    factory: ModelClientFactory,
    *,
    live: bool,
):
    condition = "independent" if unit.condition == "independent" else _MULTI_CONDITION[unit.condition]
    episode_config = EpisodeConfig(
        condition=condition,
        topology=config.topology,
        repetition=unit.repetition,
        random_seed=config.random_seed,
        communication_rounds=0 if condition == "independent" else config.communication_rounds,
        agent_count=config.agent_count,
        injection_round=None if condition == "independent" else config.injection_round,
        stimulus_sender_id=None if condition == "independent" else config.stimulus_sender_id,
    )
    agent_ids = catalog.agent_ids(unit.task_id)[: config.agent_count]
    clients = {agent_id: factory(agent_id, unit) for agent_id in agent_ids}
    trace = run_traced_episode(
        catalog=catalog,
        task_id=unit.task_id,
        episode_id=unit.episode_id,
        config=episode_config,
        model_clients=clients,
        model_settings=_model_settings(config, agent_ids, live=live),
    )
    validate_trace(trace, catalog)
    return trace


def _variant_text(artifact: TaskArtifact, variant_type: VariantType) -> tuple[str, tuple[str, ...]]:
    variant = next(
        item for item in artifact.message_variant_group.variants if item.type is variant_type
    )
    return variant.text, variant.source_fact_ids


def _full_information_context(artifact: TaskArtifact) -> AgentContext:
    task = artifact.task_definition
    return AgentContext(
        task_id=task.task_id,
        agent_id="full_info_agent",
        question=task.question,
        options=task.options,
        authorized_evidence=tuple(
            VisibleEvidence(fact_id=fact.id, text=fact.evidence_text) for fact in task.facts
        ),
    )


def _run_control_unit(
    unit: PlannedUnit,
    config: RQ1RunConfig,
    catalog: BenchmarkCatalog,
    artifact: TaskArtifact,
    factory: ModelClientFactory,
    *,
    live: bool,
) -> SingleAgentControlTrace:
    started = datetime.now(timezone.utc)
    exposure = None
    controlled_source_fact_ids: tuple[str, ...] = ()
    if unit.condition == "full_information":
        context = _full_information_context(artifact)
        stages = ("full_information",)
    else:
        assert unit.agent_id is not None
        context = catalog.agent_context(unit.task_id, unit.agent_id)
        text, source_ids = _variant_text(artifact, VariantType.AMBIGUOUS)
        controlled_source_fact_ids = source_ids
        exposure = DeliveredMessage(
            message_id=f"{unit.episode_id}.controlled",
            task_id=unit.task_id,
            sender_id="controlled_source",
            recipient_id=unit.agent_id,
            round_index=1,
            text=text,
            source_fact_ids=(),
            public_recommendation="UNKNOWN",
        )
        stages = ("pre_exposure", "post_exposure")

    delegate = factory(context.agent_id, unit)
    records: list[ControlCallRecord] = []
    errors: list[str] = []
    agent = IsolatedAgent(context, delegate)
    for index, stage in enumerate(stages):
        if stage == "post_exposure":
            assert exposure is not None
            agent.deliver(exposure)
        capturing = _CapturingClient(delegate, stage)
        agent = IsolatedAgent(agent.context, capturing)
        try:
            agent.respond(
                request_id=f"{unit.episode_id}.{stage}",
                round_index=index,
                purpose="belief",
            )
        except Exception as exc:
            records.extend(capturing.calls)
            errors.append(f"{type(exc).__name__}: {(str(exc).strip() or type(exc).__name__)[:1000]}")
            break
        records.extend(capturing.calls)

    status = "failed" if errors else "completed"
    settings = _model_settings(config, (context.agent_id,), live=live)[0]
    return SingleAgentControlTrace(
        status=status,
        started_at_utc=started,
        finished_at_utc=datetime.now(timezone.utc),
        run_id=config.run_id,
        condition_id=unit.condition_id,
        matched_set_id=unit.matched_set_id,
        episode_id=unit.episode_id,
        task_id=unit.task_id,
        task_content_sha256=unit.task_content_sha256,
        benchmark_sha256=catalog.source_sha256,
        condition=unit.condition,
        repetition=unit.repetition,
        source_view_agent_id=unit.agent_id,
        context=context,
        controlled_exposure=exposure,
        controlled_source_fact_ids=controlled_source_fact_ids,
        model_settings=settings,
        calls=tuple(records),
        errors=tuple(errors),
    )


def run_mock_experiment(
    config: RQ1RunConfig,
    *,
    model_client_factory: ModelClientFactory | None = None,
) -> MockRunSummary:
    """Run deterministic mock units and append validated complete or failed records."""

    _, catalog, artifacts, task_ids, hashes = _verified_inputs(config)
    units = _planned_units(config, task_ids, hashes)
    existing_episode_ids = {item.episode_id for item in read_traces(config.episode_trace_path)}
    existing_control_ids = {
        item.episode_id for item in read_control_traces(config.control_trace_path)
    }
    existing = existing_episode_ids | existing_control_ids
    factory = model_client_factory or _default_factory
    episode_logger = AppendOnlyTraceLogger(config.episode_trace_path)
    control_logger = _ControlTraceLogger(config.control_trace_path)
    executed = completed = failed = calls = 0
    skipped = 0
    for unit in units:
        if unit.episode_id in existing:
            skipped += 1
            continue
        executed += 1
        if unit.condition in {"independent", "multi_clear", "multi_ambiguous", "multi_omission"}:
            trace = _run_group_unit(unit, config, catalog, factory, live=False)
            episode_logger.append(trace)
            calls += trace.runtime.model_calls
            if trace.status == "completed":
                completed += 1
            else:
                failed += 1
        else:
            trace = _run_control_unit(
                unit,
                config,
                catalog,
                artifacts[unit.task_id],
                factory,
                live=False,
            )
            control_logger.append(trace)
            calls += len(trace.calls)
            if trace.status == "completed":
                completed += 1
            else:
                failed += 1
    return MockRunSummary(
        run_id=config.run_id,
        planned_units=len(units),
        executed_units=executed,
        skipped_existing_units=skipped,
        completed_units=completed,
        failed_units=failed,
        model_calls=calls,
        episode_trace_path=config.episode_trace_path,
        control_trace_path=config.control_trace_path,
    )


class _RateLimitedClient:
    """Sequential shared limiter; it never logs credentials or request headers."""

    def __init__(
        self,
        delegate: ModelClient,
        limiter: "_RequestLimiter",
    ) -> None:
        self._delegate = delegate
        self._limiter = limiter

    def generate(self, request: ModelRequest) -> ModelOutput:
        self._limiter.wait()
        return self._delegate.generate(request)


class _RequestLimiter:
    def __init__(
        self,
        minimum_interval_seconds: float,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.minimum_interval_seconds = minimum_interval_seconds
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn
        self._last_request_at: float | None = None

    def wait(self) -> None:
        now = self._monotonic()
        if self._last_request_at is not None:
            remaining = self.minimum_interval_seconds - (now - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._monotonic()


def run_live_experiment(
    config: RQ1RunConfig,
    *,
    paid_calls_authorized: bool,
    model_client_factory: ModelClientFactory | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
    integration_only: bool = True,
    max_new_model_calls: int | None = None,
) -> LiveRunSummary:
    """Run an authorized, rate-bounded live integration or pilot chunk."""

    if not paid_calls_authorized:
        raise RQ1ConfigurationError(
            "live execution requires explicit paid-call authorization"
        )
    plan = build_dry_run_plan(config)
    if integration_only:
        if plan.task_count != 1 or config.repetitions != 1:
            raise RQ1ConfigurationError(
                "Phase 3.2 live integration is limited to one task and one repetition"
            )
        required = {"multi_clear", "multi_ambiguous"}
        if not required.issubset(config.conditions):
            raise RQ1ConfigurationError(
                "Phase 3.2 live integration requires clear and ambiguous multi-agent episodes"
            )
        call_cap = plan.expected_model_calls
    else:
        expected_conditions = {
            "independent",
            "full_information",
            "individual_ambiguous",
            "multi_clear",
            "multi_ambiguous",
            "multi_omission",
        }
        if (
            plan.task_count != 12
            or config.repetitions != 3
            or set(config.conditions) != expected_conditions
            or plan.expected_model_calls != 3276
        ):
            raise RQ1ConfigurationError(
                "Phase 3.3 pilot must match the authorized 12-task, 3-repetition, "
                "six-condition, 3276-call plan"
            )
        call_cap = max_new_model_calls or plan.safe_requests_per_day
    if call_cap > plan.safe_requests_per_day:
        raise RQ1ConfigurationError(
            "invocation call cap exceeds the conservative daily request/token budget"
        )
    if model_client_factory is None and not os.environ.get(config.api_key_env):
        raise RQ1ConfigurationError(
            f"missing API credential in environment variable {config.api_key_env}"
        )

    _, catalog, artifacts, task_ids, hashes = _verified_inputs(config)
    units = _planned_units(config, task_ids, hashes)
    existing_episode_ids = {
        item.episode_id for item in read_traces(config.episode_trace_path)
    }
    existing_control_ids = {
        item.episode_id for item in read_control_traces(config.control_trace_path)
    }
    existing = existing_episode_ids | existing_control_ids
    limiter = _RequestLimiter(
        config.minimum_request_interval_seconds,
        sleep_fn=sleep_fn,
        monotonic_fn=monotonic_fn,
    )
    if model_client_factory is None:
        live_config = OpenAICompatibleConfig(
            base_url=config.base_url,
            model=config.model,
            api_key_env=config.api_key_env,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            max_retries=config.max_retries,
            seed=config.random_seed,
            timeout_seconds=config.timeout_seconds,
            response_format="json_schema",
        )

        def factory(agent_id: str, unit: PlannedUnit) -> ModelClient:
            del agent_id, unit
            return _RateLimitedClient(OpenAICompatibleClient(live_config), limiter)
    else:
        def factory(agent_id: str, unit: PlannedUnit) -> ModelClient:
            return _RateLimitedClient(model_client_factory(agent_id, unit), limiter)

    episode_logger = AppendOnlyTraceLogger(config.episode_trace_path)
    control_logger = _ControlTraceLogger(config.control_trace_path)
    executed = completed = failed = calls = calls_with_usage = 0
    observed_input = observed_output = skipped = deferred = scheduled_calls = 0
    for unit in units:
        if unit.episode_id in existing:
            skipped += 1
            continue
        if scheduled_calls + unit.expected_model_calls > call_cap:
            deferred += 1
            continue
        scheduled_calls += unit.expected_model_calls
        executed += 1
        if unit.condition in {
            "independent",
            "multi_clear",
            "multi_ambiguous",
            "multi_omission",
        }:
            trace = _run_group_unit(unit, config, catalog, factory, live=True)
            episode_logger.append(trace)
            calls += trace.runtime.model_calls
            calls_with_usage += trace.runtime.calls_with_token_usage
            observed_input += trace.runtime.input_tokens_observed
            observed_output += trace.runtime.output_tokens_observed
        else:
            trace = _run_control_unit(
                unit,
                config,
                catalog,
                artifacts[unit.task_id],
                factory,
                live=True,
            )
            control_logger.append(trace)
            calls += len(trace.calls)
            for call in trace.calls:
                if call.output is not None and (
                    call.output.input_tokens is not None
                    or call.output.output_tokens is not None
                ):
                    calls_with_usage += 1
                    observed_input += call.output.input_tokens or 0
                    observed_output += call.output.output_tokens or 0
        if trace.status == "completed":
            completed += 1
        else:
            failed += 1
    return LiveRunSummary(
        run_id=config.run_id,
        planned_units=len(units),
        executed_units=executed,
        skipped_existing_units=skipped,
        deferred_units=deferred,
        scheduled_model_call_cap=call_cap,
        completed_units=completed,
        failed_units=failed,
        model_calls=calls,
        calls_with_token_usage=calls_with_usage,
        observed_input_tokens=observed_input,
        observed_output_tokens=observed_output,
        episode_trace_path=config.episode_trace_path,
        control_trace_path=config.control_trace_path,
    )

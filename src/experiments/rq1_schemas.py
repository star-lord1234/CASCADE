"""Strict schemas for the Phase 3 RQ1 planner and single-agent controls."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from src.simulation.schemas import (
    AgentContext,
    DeliveredMessage,
    ModelOutput,
    ModelRequest,
    StrictSimulationModel,
)
from src.simulation.trace_schemas import ModelSettings
from src.tasks.schemas import Identifier

RQ1Condition = Literal[
    "independent",
    "full_information",
    "individual_ambiguous",
    "multi_clear",
    "multi_ambiguous",
    "multi_omission",
]


class RQ1RunConfig(StrictSimulationModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: Identifier
    execution_tier: Literal["EXPLORATORY"] = "EXPLORATORY"
    result_label: Literal["exploratory/non-confirmatory"] = (
        "exploratory/non-confirmatory"
    )
    manifest_path: str = "configs/phase3_exploratory_pilot_manifest.json"
    benchmark_path: str = "data/benchmark/canonical_tasks.jsonl"
    episode_trace_path: str = Field(min_length=1)
    control_trace_path: str = Field(min_length=1)
    task_ids: tuple[Identifier, ...] = ()
    conditions: tuple[RQ1Condition, ...] = (
        "independent",
        "full_information",
        "individual_ambiguous",
        "multi_clear",
        "multi_ambiguous",
        "multi_omission",
    )
    repetitions: int = Field(default=3, ge=1, le=10)
    random_seed: int = 42
    agent_count: Literal[5] = 5
    topology: Literal["fully_connected"] = "fully_connected"
    communication_rounds: Literal[2] = 2
    injection_round: Literal[1] = 1
    stimulus_sender_id: Literal["agent_1"] = "agent_1"
    provider: Literal["groq"] = "groq"
    model: Literal["openai/gpt-oss-120b"] = "openai/gpt-oss-120b"
    base_url: Literal["https://api.groq.com/openai/v1"] = (
        "https://api.groq.com/openai/v1"
    )
    api_key_env: Literal["GROQ_API_KEY"] = "GROQ_API_KEY"
    temperature: Literal[0.0] = 0.0
    max_output_tokens: int = Field(default=1024, ge=256, le=4096)
    max_retries: int = Field(default=1, ge=0, le=3)
    timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    minimum_request_interval_seconds: float = Field(default=15.0, ge=0, le=60)
    estimated_input_tokens_per_call: int = Field(default=1200, ge=1)
    estimated_output_tokens_per_call: int = Field(default=256, ge=1)
    input_usd_per_million_tokens: float = Field(default=0.15, ge=0)
    output_usd_per_million_tokens: float = Field(default=0.60, ge=0)
    provider_requests_per_minute: int = Field(default=30, ge=1)
    provider_requests_per_day: int = Field(default=1000, ge=1)
    provider_tokens_per_minute: int = Field(default=8000, ge=1)
    provider_tokens_per_day: int = Field(default=200000, ge=1)
    safety_fraction: float = Field(default=0.8, gt=0, le=1)

    @model_validator(mode="after")
    def validate_unique_selection(self) -> "RQ1RunConfig":
        if len(self.task_ids) != len(set(self.task_ids)):
            raise ValueError("RQ1 task IDs must be unique")
        if len(self.conditions) != len(set(self.conditions)):
            raise ValueError("RQ1 conditions must be unique")
        if not self.conditions:
            raise ValueError("RQ1 run needs at least one condition")
        return self


class PlannedUnit(StrictSimulationModel):
    condition_id: Identifier
    matched_set_id: Identifier
    episode_id: Identifier
    task_id: Identifier
    task_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    condition: RQ1Condition
    repetition: int = Field(ge=1)
    agent_id: Identifier | None = None
    expected_model_calls: int = Field(ge=1)


class DryRunPlan(StrictSimulationModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: Identifier
    execution_tier: Literal["EXPLORATORY"] = "EXPLORATORY"
    result_label: Literal["exploratory/non-confirmatory"] = (
        "exploratory/non-confirmatory"
    )
    manifest_id: Identifier
    benchmark_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_count: int = Field(ge=1)
    repetitions: int = Field(ge=1)
    condition_counts: dict[str, int]
    planned_unit_count: int = Field(ge=1)
    expected_model_calls: int = Field(ge=1)
    estimated_input_tokens: int = Field(ge=1)
    estimated_output_tokens: int = Field(ge=1)
    approximate_cost_usd: float = Field(ge=0)
    safe_requests_per_minute: int = Field(ge=1)
    safe_requests_per_day: int = Field(ge=1)
    minimum_days_at_documented_base_limits: int = Field(ge=1)
    rate_limit_warning: str = Field(min_length=1)
    price_source: str = Field(min_length=1)
    rate_limit_source: str = Field(min_length=1)
    units: tuple[PlannedUnit, ...]


class ControlCallRecord(StrictSimulationModel):
    stage: Literal["full_information", "pre_exposure", "post_exposure"]
    request: ModelRequest
    output: ModelOutput | None = None
    error_type: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def output_or_error(self) -> "ControlCallRecord":
        has_output = self.output is not None
        has_error = self.error_type is not None or self.error_message is not None
        if has_output == has_error:
            raise ValueError("control call needs exactly one output or error")
        if has_error and (not self.error_type or not self.error_message):
            raise ValueError("control call error needs type and message")
        return self


class SingleAgentControlTrace(StrictSimulationModel):
    schema_version: Literal["1.0"] = "1.0"
    trace_kind: Literal["rq1_single_agent_control"] = "rq1_single_agent_control"
    result_label: Literal["exploratory/non-confirmatory"] = (
        "exploratory/non-confirmatory"
    )
    status: Literal["completed", "failed"]
    started_at_utc: datetime
    finished_at_utc: datetime
    run_id: Identifier
    condition_id: Identifier
    matched_set_id: Identifier
    episode_id: Identifier
    task_id: Identifier
    task_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    benchmark_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    condition: Literal["full_information", "individual_ambiguous"]
    repetition: int = Field(ge=1)
    source_view_agent_id: Identifier | None = None
    context: AgentContext
    controlled_exposure: DeliveredMessage | None = None
    controlled_source_fact_ids: tuple[Identifier, ...] = ()
    model_settings: ModelSettings
    calls: tuple[ControlCallRecord, ...] = Field(min_length=1)
    errors: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_control_shape(self) -> "SingleAgentControlTrace":
        if self.finished_at_utc < self.started_at_utc:
            raise ValueError("control trace finishes before it starts")
        if self.status == "completed" and self.errors:
            raise ValueError("completed control trace cannot contain errors")
        if self.status == "failed" and not self.errors:
            raise ValueError("failed control trace requires errors")
        if self.condition == "full_information":
            if (
                self.source_view_agent_id is not None
                or self.controlled_exposure is not None
                or self.controlled_source_fact_ids
            ):
                raise ValueError("full-information control cannot have an exposure")
        else:
            if (
                self.source_view_agent_id is None
                or self.controlled_exposure is None
                or not self.controlled_source_fact_ids
            ):
                raise ValueError("individual exposure requires source view and message")
            if self.controlled_exposure.source_fact_ids:
                raise ValueError("agent-facing controlled exposure leaks source annotations")
        return self


class MockRunSummary(StrictSimulationModel):
    run_id: Identifier
    result_label: Literal["exploratory/non-confirmatory"] = (
        "exploratory/non-confirmatory"
    )
    planned_units: int = Field(ge=1)
    executed_units: int = Field(ge=0)
    skipped_existing_units: int = Field(ge=0)
    completed_units: int = Field(ge=0)
    failed_units: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    episode_trace_path: str
    control_trace_path: str


class LiveRunSummary(StrictSimulationModel):
    run_id: Identifier
    execution_tier: Literal["EXPLORATORY"] = "EXPLORATORY"
    result_label: Literal["exploratory/non-confirmatory"] = (
        "exploratory/non-confirmatory"
    )
    provider: Literal["groq"] = "groq"
    model: Literal["openai/gpt-oss-120b"] = "openai/gpt-oss-120b"
    planned_units: int = Field(ge=1)
    executed_units: int = Field(ge=0)
    skipped_existing_units: int = Field(ge=0)
    deferred_units: int = Field(default=0, ge=0)
    scheduled_model_call_cap: int = Field(ge=1)
    completed_units: int = Field(ge=0)
    failed_units: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    calls_with_token_usage: int = Field(ge=0)
    observed_input_tokens: int = Field(ge=0)
    observed_output_tokens: int = Field(ge=0)
    episode_trace_path: str
    control_trace_path: str

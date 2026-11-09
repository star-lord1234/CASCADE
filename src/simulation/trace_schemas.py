"""Validated append-only trace contracts for CASCADE Phase 2.3."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from src.tasks.schemas import AgentView, Identifier

from .schemas import (
    AgentModelReply,
    BeliefSnapshot,
    EpisodeConfig,
    GroupDecision,
    ModelRequest,
    RoutedMessage,
    StrictSimulationModel,
)

TRACE_SCHEMA_VERSION = "1.1"


class ModelSettings(StrictSimulationModel):
    agent_id: Identifier
    provider: Literal["deterministic_mock", "openai_compatible"]
    model_name: str = Field(min_length=1)
    deterministic: bool
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, ge=1)
    max_retries: int | None = Field(default=None, ge=0)
    seed: int | None = None
    base_url: str | None = None
    prompt_version: str = Field(default="cascade_phase2_v1", min_length=1)


class ModelCallEvent(StrictSimulationModel):
    event_order: int = Field(ge=1)
    event_type: Literal["model_call"] = "model_call"
    request: ModelRequest
    model_name: str | None = None
    response_id: str | None = None
    reply: AgentModelReply | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    error_type: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def response_or_error(self) -> "ModelCallEvent":
        has_reply = self.reply is not None
        has_error = self.error_type is not None or self.error_message is not None
        if has_reply == has_error:
            raise ValueError("model call must contain exactly one reply or error")
        if has_error and (not self.error_type or not self.error_message):
            raise ValueError("model call errors require type and message")
        return self


class MessageEvent(StrictSimulationModel):
    event_order: int = Field(ge=1)
    event_type: Literal["message"] = "message"
    message: RoutedMessage


class BeliefEvent(StrictSimulationModel):
    event_order: int = Field(ge=1)
    event_type: Literal["belief"] = "belief"
    snapshot: BeliefSnapshot


class GroupDecisionEvent(StrictSimulationModel):
    event_order: int = Field(ge=1)
    event_type: Literal["group_decision"] = "group_decision"
    decision: GroupDecision


class ErrorEvent(StrictSimulationModel):
    event_order: int = Field(ge=1)
    event_type: Literal["error"] = "error"
    error_type: str = Field(min_length=1)
    message: str = Field(min_length=1)


class TraceRuntime(StrictSimulationModel):
    model_calls: int = Field(ge=0)
    calls_with_token_usage: int = Field(ge=0)
    input_tokens_observed: int = Field(ge=0)
    output_tokens_observed: int = Field(ge=0)

    @model_validator(mode="after")
    def usage_calls_are_bounded(self) -> "TraceRuntime":
        if self.calls_with_token_usage > self.model_calls:
            raise ValueError("token-usage calls cannot exceed model calls")
        return self


class EpisodeTrace(StrictSimulationModel):
    schema_version: Literal["1.0", TRACE_SCHEMA_VERSION] = TRACE_SCHEMA_VERSION
    trace_kind: Literal["saved_event_trace"] = "saved_event_trace"
    replay_semantics: Literal["saved_events_only_no_model_calls"] = (
        "saved_events_only_no_model_calls"
    )
    status: Literal["completed", "failed"]
    started_at_utc: datetime | None = None
    finished_at_utc: datetime | None = None
    episode_id: Identifier
    task_id: Identifier
    benchmark_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    config: EpisodeConfig
    selected_agent_ids: tuple[Identifier, ...] = Field(min_length=2)
    agent_views_audit: tuple[AgentView, ...] = Field(min_length=2)
    adjacency: dict[Identifier, tuple[Identifier, ...]]
    model_settings: tuple[ModelSettings, ...] = Field(min_length=2)
    model_calls: tuple[ModelCallEvent, ...] = ()
    messages: tuple[MessageEvent, ...] = ()
    beliefs: tuple[BeliefEvent, ...] = ()
    group_decision: GroupDecisionEvent | None = None
    errors: tuple[ErrorEvent, ...] = ()
    runtime: TraceRuntime

    @model_validator(mode="after")
    def validate_trace_structure(self) -> "EpisodeTrace":
        if self.schema_version == "1.1":
            if self.started_at_utc is None or self.finished_at_utc is None:
                raise ValueError("trace schema 1.1 requires run timestamps")
            if self.finished_at_utc < self.started_at_utc:
                raise ValueError("trace finish time precedes start time")
        event_orders = [event.event_order for event in self.model_calls]
        event_orders.extend(event.event_order for event in self.messages)
        event_orders.extend(event.event_order for event in self.beliefs)
        event_orders.extend(event.event_order for event in self.errors)
        if self.group_decision is not None:
            event_orders.append(self.group_decision.event_order)
        if sorted(event_orders) != list(range(1, len(event_orders) + 1)):
            raise ValueError("trace event orders must be unique and contiguous from one")
        if len(self.selected_agent_ids) != len(set(self.selected_agent_ids)):
            raise ValueError("selected agent IDs must be unique")
        if {view.agent_id for view in self.agent_views_audit} != set(
            self.selected_agent_ids
        ):
            raise ValueError("audit views must exactly match selected agents")
        if {item.agent_id for item in self.model_settings} != set(
            self.selected_agent_ids
        ):
            raise ValueError("model settings must exactly match selected agents")
        if set(self.adjacency) != set(self.selected_agent_ids):
            raise ValueError("adjacency must exactly match selected agents")
        if self.status == "completed":
            if self.group_decision is None or self.errors:
                raise ValueError("completed trace needs a group decision and no errors")
        elif self.group_decision is not None or not self.errors:
            raise ValueError("failed trace needs errors and no group decision")
        if self.runtime.model_calls != len(self.model_calls):
            raise ValueError("runtime model-call count does not match events")
        return self


class ReplayResult(StrictSimulationModel):
    replay_mode: Literal["saved_events_only_no_model_calls"] = (
        "saved_events_only_no_model_calls"
    )
    source_trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    episode_id: Identifier
    task_id: Identifier
    source_status: Literal["completed", "failed"]
    reproduced_group_decision: GroupDecision | None = None
    event_count: int = Field(ge=1)
    model_calls_executed: Literal[0] = 0

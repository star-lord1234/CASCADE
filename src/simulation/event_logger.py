"""Append-only trace logging and runtime event recording."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.tasks.schemas import AgentView

from .model_client import ModelClient
from .schemas import (
    BeliefSnapshot,
    EpisodeConfig,
    GroupDecision,
    ModelOutput,
    ModelRequest,
    RoutedMessage,
)
from .trace_schemas import (
    BeliefEvent,
    EpisodeTrace,
    ErrorEvent,
    GroupDecisionEvent,
    MessageEvent,
    ModelCallEvent,
    ModelSettings,
    TraceRuntime,
)


class TraceLogError(ValueError):
    pass


class TraceRecorder:
    """Shared ordered recorder used by model wrappers and the orchestrator."""

    def __init__(self) -> None:
        self.started_at_utc = datetime.now(timezone.utc)
        self._next_event_order = 1
        self.model_calls: list[ModelCallEvent] = []
        self.messages: list[MessageEvent] = []
        self.beliefs: list[BeliefEvent] = []
        self.group_decision: GroupDecisionEvent | None = None
        self.errors: list[ErrorEvent] = []

    def _order(self) -> int:
        value = self._next_event_order
        self._next_event_order += 1
        return value

    def record_model_output(
        self, request: ModelRequest, output: ModelOutput
    ) -> None:
        self.model_calls.append(
            ModelCallEvent(
                event_order=self._order(),
                request=request,
                model_name=output.model_name,
                response_id=output.response_id,
                reply=output.reply,
                input_tokens=output.input_tokens,
                output_tokens=output.output_tokens,
            )
        )

    def record_model_error(self, request: ModelRequest, error: Exception) -> None:
        self.model_calls.append(
            ModelCallEvent(
                event_order=self._order(),
                request=request,
                error_type=type(error).__name__,
                error_message=_safe_error_message(error),
            )
        )

    def record_message(self, message: RoutedMessage) -> None:
        self.messages.append(
            MessageEvent(event_order=self._order(), message=message)
        )

    def record_snapshot(self, snapshot: BeliefSnapshot) -> None:
        self.beliefs.append(
            BeliefEvent(event_order=self._order(), snapshot=snapshot)
        )

    def record_group_decision(self, decision: GroupDecision) -> None:
        if self.group_decision is not None:
            raise TraceLogError("group decision was recorded more than once")
        self.group_decision = GroupDecisionEvent(
            event_order=self._order(), decision=decision
        )

    def record_error(self, error: Exception) -> None:
        self.errors.append(
            ErrorEvent(
                event_order=self._order(),
                error_type=type(error).__name__,
                message=_safe_error_message(error),
            )
        )

    def build_trace(
        self,
        *,
        status: str,
        episode_id: str,
        task_id: str,
        benchmark_sha256: str,
        config: EpisodeConfig,
        selected_agent_ids: tuple[str, ...],
        agent_views_audit: tuple[AgentView, ...],
        adjacency: dict[str, tuple[str, ...]],
        model_settings: tuple[ModelSettings, ...],
    ) -> EpisodeTrace:
        calls_with_usage = sum(
            event.input_tokens is not None or event.output_tokens is not None
            for event in self.model_calls
        )
        runtime = TraceRuntime(
            model_calls=len(self.model_calls),
            calls_with_token_usage=calls_with_usage,
            input_tokens_observed=sum(
                event.input_tokens or 0 for event in self.model_calls
            ),
            output_tokens_observed=sum(
                event.output_tokens or 0 for event in self.model_calls
            ),
        )
        return EpisodeTrace(
            status=status,
            started_at_utc=self.started_at_utc,
            finished_at_utc=datetime.now(timezone.utc),
            episode_id=episode_id,
            task_id=task_id,
            benchmark_sha256=benchmark_sha256,
            config=config,
            selected_agent_ids=selected_agent_ids,
            agent_views_audit=agent_views_audit,
            adjacency=adjacency,
            model_settings=model_settings,
            model_calls=tuple(self.model_calls),
            messages=tuple(self.messages),
            beliefs=tuple(self.beliefs),
            group_decision=self.group_decision,
            errors=tuple(self.errors),
            runtime=runtime,
        )


class RecordingModelClient:
    """Transparent wrapper that records parsed calls without logging secrets."""

    def __init__(self, client: ModelClient, recorder: TraceRecorder) -> None:
        self._client = client
        self._recorder = recorder

    def generate(self, request: ModelRequest) -> ModelOutput:
        try:
            output = self._client.generate(request)
        except Exception as exc:
            self._recorder.record_model_error(request, exc)
            raise
        self._recorder.record_model_output(request, output)
        return output


class AppendOnlyTraceLogger:
    """One validated episode per JSONL row, opened with append-only mode 0600."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, trace: EpisodeTrace) -> None:
        existing_ids = {
            item.episode_id for item in read_traces(self.path)
        } if self.path.exists() else set()
        if trace.episode_id in existing_ids:
            raise TraceLogError(
                f"episode {trace.episode_id!r} already exists in append-only log"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps(trace.model_dump(mode="json"), sort_keys=True) + "\n"
        ).encode("utf-8")
        descriptor = os.open(
            self.path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        try:
            offset = 0
            while offset < len(payload):
                offset += os.write(descriptor, payload[offset:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.chmod(self.path, 0o600)


def read_traces(path_like: str | Path) -> list[EpisodeTrace]:
    path = Path(path_like)
    if not path.exists():
        return []
    traces: list[EpisodeTrace] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                traces.append(EpisodeTrace.model_validate_json(line))
            except ValueError as exc:
                raise TraceLogError(
                    f"invalid trace at {path}:{line_number}: {exc}"
                ) from exc
    return traces


def _safe_error_message(error: Exception) -> str:
    text = str(error).strip() or type(error).__name__
    return text[:1000]

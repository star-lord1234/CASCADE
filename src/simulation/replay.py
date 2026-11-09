"""Deterministic saved-event replay that never invokes a model client."""

from __future__ import annotations

import hashlib
import json

from .loader import BenchmarkCatalog
from .orchestrator import aggregate_group
from .trace_schemas import EpisodeTrace, ReplayResult
from .trace_validation import validate_trace


def replay_trace(trace: EpisodeTrace, catalog: BenchmarkCatalog) -> ReplayResult:
    """Recompute linked outcomes from saved events; never rerun prompts or models."""

    validate_trace(trace, catalog)
    reproduced = None
    if trace.status == "completed":
        final_round = trace.config.communication_rounds
        final_beliefs = tuple(
            event.snapshot
            for event in trace.beliefs
            if event.snapshot.round_index == final_round
        )
        reproduced = aggregate_group(final_beliefs)
    payload = json.dumps(
        trace.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    event_count = (
        len(trace.model_calls)
        + len(trace.messages)
        + len(trace.beliefs)
        + len(trace.errors)
        + (1 if trace.group_decision is not None else 0)
    )
    return ReplayResult(
        source_trace_sha256=hashlib.sha256(payload).hexdigest(),
        episode_id=trace.episode_id,
        task_id=trace.task_id,
        source_status=trace.status,
        reproduced_group_decision=reproduced,
        event_count=event_count,
    )

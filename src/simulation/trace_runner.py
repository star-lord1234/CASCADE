"""Execute one episode while producing a validated event trace."""

from __future__ import annotations

from collections.abc import Mapping

from .event_logger import RecordingModelClient, TraceRecorder
from .loader import BenchmarkCatalog
from .model_client import ModelClient
from .network import build_adjacency
from .orchestrator import run_episode
from .schemas import EpisodeConfig
from .trace_schemas import EpisodeTrace, ModelSettings
from .trace_validation import validate_trace


def run_traced_episode(
    *,
    catalog: BenchmarkCatalog,
    task_id: str,
    episode_id: str,
    config: EpisodeConfig,
    model_clients: Mapping[str, ModelClient],
    model_settings: tuple[ModelSettings, ...],
) -> EpisodeTrace:
    available = catalog.agent_ids(task_id)
    selected = available[: config.agent_count]
    audit_views = tuple(catalog.agent_view(task_id, agent_id) for agent_id in selected)
    adjacency = build_adjacency(
        selected,
        config.topology,
        star_center_id=config.star_center_id,
    )
    recorder = TraceRecorder()
    wrapped = {
        agent_id: RecordingModelClient(model_clients[agent_id], recorder)
        for agent_id in selected
    }
    try:
        run_episode(
            catalog=catalog,
            task_id=task_id,
            episode_id=episode_id,
            config=config,
            model_clients=wrapped,
            observer=recorder,
        )
    except Exception as exc:
        recorder.record_error(exc)
        trace = recorder.build_trace(
            status="failed",
            episode_id=episode_id,
            task_id=task_id,
            benchmark_sha256=catalog.source_sha256,
            config=config,
            selected_agent_ids=selected,
            agent_views_audit=audit_views,
            adjacency=adjacency,
            model_settings=model_settings,
        )
        validate_trace(trace, catalog)
        return trace

    trace = recorder.build_trace(
        status="completed",
        episode_id=episode_id,
        task_id=task_id,
        benchmark_sha256=catalog.source_sha256,
        config=config,
        selected_agent_ids=selected,
        agent_views_audit=audit_views,
        adjacency=adjacency,
        model_settings=model_settings,
    )
    validate_trace(trace, catalog)
    return trace

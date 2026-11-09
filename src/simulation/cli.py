"""Phase 2.3 CLI for mock traces, validation, replay, and one live smoke call."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, model_validator

from src.tasks.schemas import Identifier

from .agent import IsolatedAgent
from .event_logger import AppendOnlyTraceLogger, read_traces
from .loader import load_benchmark
from .model_client import (
    EvidenceEchoMockClient,
    OpenAICompatibleClient,
    OpenAICompatibleConfig,
)
from .replay import replay_trace
from .schemas import Condition, EpisodeConfig, StrictSimulationModel, TopologyName
from .trace_runner import run_traced_episode
from .trace_schemas import EpisodeTrace, ModelSettings
from .trace_validation import validate_trace


class MockBatchConfig(StrictSimulationModel):
    schema_version: Literal["1.0"] = "1.0"
    batch_id: Identifier
    benchmark_path: str = "data/benchmark/canonical_tasks.jsonl"
    output_trace_path: str = Field(min_length=1)
    task_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=5)
    conditions: tuple[Condition, ...] = Field(min_length=1)
    topology: TopologyName = "fully_connected"
    repetition: int = Field(default=1, ge=1)
    random_seed: int = 42
    communication_rounds: int = Field(default=1, ge=1)
    agent_count: int = Field(default=5, ge=2, le=5)
    injection_round: int = Field(default=1, ge=1)
    stimulus_sender_id: Identifier = "agent_1"
    star_center_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_batch(self) -> "MockBatchConfig":
        if len(self.task_ids) != len(set(self.task_ids)):
            raise ValueError("task IDs must be unique")
        if len(self.conditions) != len(set(self.conditions)):
            raise ValueError("conditions must be unique")
        if self.injection_round > self.communication_rounds:
            raise ValueError("injection round exceeds communication rounds")
        if self.topology == "star" and self.star_center_id is None:
            raise ValueError("star topology requires star_center_id")
        if self.topology != "star" and self.star_center_id is not None:
            raise ValueError("star_center_id is valid only for star topology")
        return self


def load_mock_batch_config(path_like: str | Path) -> MockBatchConfig:
    return MockBatchConfig.model_validate_json(
        Path(path_like).read_text(encoding="utf-8")
    )


def run_mock_batch(config: MockBatchConfig) -> list[EpisodeTrace]:
    catalog = load_benchmark(config.benchmark_path)
    logger = AppendOnlyTraceLogger(config.output_trace_path)
    traces: list[EpisodeTrace] = []
    known_tasks = set(catalog.task_ids())
    unknown = set(config.task_ids) - known_tasks
    if unknown:
        raise ValueError(f"unknown configured task IDs: {sorted(unknown)}")
    for task_index, task_id in enumerate(config.task_ids, start=1):
        selected = catalog.agent_ids(task_id)[: config.agent_count]
        for condition in config.conditions:
            episode_id = f"{config.batch_id}.T{task_index}.{condition}"
            episode_config = (
                EpisodeConfig(
                    condition="independent",
                    topology=config.topology,
                    repetition=config.repetition,
                    random_seed=config.random_seed,
                    communication_rounds=0,
                    agent_count=config.agent_count,
                    injection_round=None,
                    stimulus_sender_id=None,
                    star_center_id=config.star_center_id,
                )
                if condition == "independent"
                else EpisodeConfig(
                    condition=condition,
                    topology=config.topology,
                    repetition=config.repetition,
                    random_seed=config.random_seed,
                    communication_rounds=config.communication_rounds,
                    agent_count=config.agent_count,
                    injection_round=config.injection_round,
                    stimulus_sender_id=config.stimulus_sender_id,
                    star_center_id=config.star_center_id,
                )
            )
            clients = {agent_id: EvidenceEchoMockClient() for agent_id in selected}
            settings = tuple(
                ModelSettings(
                    agent_id=agent_id,
                    provider="deterministic_mock",
                    model_name=EvidenceEchoMockClient.model_name,
                    deterministic=True,
                    temperature=0.0,
                    max_retries=0,
                    seed=config.random_seed,
                )
                for agent_id in selected
            )
            trace = run_traced_episode(
                catalog=catalog,
                task_id=task_id,
                episode_id=episode_id,
                config=episode_config,
                model_clients=clients,
                model_settings=settings,
            )
            logger.append(trace)
            traces.append(trace)
    return traces


def _run_mock(args: argparse.Namespace) -> int:
    config = load_mock_batch_config(args.config)
    traces = run_mock_batch(config)
    completed = sum(trace.status == "completed" for trace in traces)
    print(
        f"episodes={len(traces)} completed={completed} failed={len(traces) - completed} "
        f"trace={config.output_trace_path}"
    )
    return 0 if completed == len(traces) else 1


def _validate(args: argparse.Namespace) -> int:
    catalog = load_benchmark(args.benchmark)
    traces = read_traces(args.trace)
    check_count = 0
    for trace in traces:
        check_count += validate_trace(trace, catalog).check_count
    print(f"traces={len(traces)} valid={len(traces)} checks={check_count}")
    return 0


def _replay(args: argparse.Namespace) -> int:
    catalog = load_benchmark(args.benchmark)
    traces = read_traces(args.trace)
    results = [replay_trace(trace, catalog) for trace in traces]
    completed = sum(result.reproduced_group_decision is not None for result in results)
    print(
        f"traces={len(results)} replayed={len(results)} completed={completed} "
        "model_calls_executed=0"
    )
    return 0


def _live_api_key_env(base_url: str, configured: str | None) -> str:
    if configured is not None:
        return configured
    if urlparse(base_url).hostname == "api.groq.com":
        return "GROQ_API_KEY"
    return "OPENAI_API_KEY"


def _live_smoke(args: argparse.Namespace) -> int:
    catalog = load_benchmark(args.benchmark)
    task_id = args.task_id or catalog.task_ids()[0]
    context = catalog.agent_context(task_id, args.agent_id)
    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            base_url=args.base_url,
            model=args.model,
            api_key_env=_live_api_key_env(args.base_url, args.api_key_env),
            temperature=0.0,
            max_output_tokens=args.max_output_tokens,
        )
    )
    result = IsolatedAgent(context, client).probe(
        request_id="LIVE_SMOKE.request",
        snapshot_id="LIVE_SMOKE.belief",
        episode_id="LIVE_SMOKE",
        round_index=0,
    )
    print(
        f"task={task_id} agent={args.agent_id} model={result.model_name} "
        f"belief={result.snapshot.private_belief}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run-mock")
    run_parser.add_argument("--config", required=True)
    run_parser.set_defaults(handler=_run_mock)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--benchmark", default="data/benchmark/canonical_tasks.jsonl")
    validate_parser.add_argument("--trace", required=True)
    validate_parser.set_defaults(handler=_validate)

    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--benchmark", default="data/benchmark/canonical_tasks.jsonl")
    replay_parser.add_argument("--trace", required=True)
    replay_parser.set_defaults(handler=_replay)

    live_parser = subparsers.add_parser("live-smoke")
    live_parser.add_argument("--benchmark", default="data/benchmark/canonical_tasks.jsonl")
    live_parser.add_argument("--task-id")
    live_parser.add_argument("--agent-id", default="agent_1")
    live_parser.add_argument("--model", required=True)
    live_parser.add_argument("--base-url", default="https://api.openai.com/v1")
    live_parser.add_argument("--max-output-tokens", type=int, default=1024)
    live_parser.add_argument(
        "--api-key-env",
        help="credential environment variable (inferred as GROQ_API_KEY for api.groq.com)",
    )
    live_parser.set_defaults(handler=_live_smoke)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

"""Phase 2 simulation primitives.

Phase 2.1 intentionally exposes no episode orchestration. It provides strict
loading, isolated agent contexts, validated model I/O, and mockable clients.
"""

from .agent import IsolatedAgent
from .loader import BenchmarkCatalog, BenchmarkLoadError, load_benchmark
from .model_client import (
    DeterministicMockClient,
    EvidenceEchoMockClient,
    ModelClient,
    OpenAICompatibleClient,
    OpenAICompatibleConfig,
)
from .orchestrator import aggregate_group, run_episode
from .replay import replay_trace
from .schemas import EpisodeConfig, EpisodeResult
from .trace_runner import run_traced_episode
from .trace_schemas import EpisodeTrace, ReplayResult
from .trace_validation import validate_trace

__all__ = [
    "BenchmarkCatalog",
    "BenchmarkLoadError",
    "DeterministicMockClient",
    "EvidenceEchoMockClient",
    "EpisodeConfig",
    "EpisodeResult",
    "EpisodeTrace",
    "IsolatedAgent",
    "ModelClient",
    "OpenAICompatibleClient",
    "OpenAICompatibleConfig",
    "ReplayResult",
    "aggregate_group",
    "load_benchmark",
    "replay_trace",
    "run_episode",
    "run_traced_episode",
    "validate_trace",
]

"""Strict canonical benchmark loading with safe per-agent view access."""

from __future__ import annotations

import hashlib
from pathlib import Path

from src.tasks.export import read_jsonl
from src.tasks.schemas import AgentView, TaskArtifact, VariantType

from .schemas import AgentContext, ControlledStimulus


class BenchmarkLoadError(ValueError):
    """Raised when a benchmark cannot safely cross the simulation boundary."""


class BenchmarkCatalog:
    """Experimenter-side catalog that exposes only safe agent-view methods."""

    def __init__(self, artifacts: tuple[TaskArtifact, ...], source_sha256: str):
        self._artifacts = {item.task_definition.task_id: item for item in artifacts}
        self._source_sha256 = source_sha256

    @property
    def source_sha256(self) -> str:
        return self._source_sha256

    @property
    def task_count(self) -> int:
        return len(self._artifacts)

    def task_ids(self) -> tuple[str, ...]:
        return tuple(self._artifacts)

    def agent_ids(self, task_id: str) -> tuple[str, ...]:
        artifact = self._get(task_id)
        return tuple(view.agent_id for view in artifact.agent_views)

    def agent_view(self, task_id: str, agent_id: str) -> AgentView:
        artifact = self._get(task_id)
        try:
            return next(view for view in artifact.agent_views if view.agent_id == agent_id)
        except StopIteration as exc:
            raise KeyError(f"unknown agent ID {agent_id!r} for task {task_id!r}") from exc

    def agent_context(self, task_id: str, agent_id: str) -> AgentContext:
        view = self.agent_view(task_id, agent_id)
        return AgentContext(
            task_id=view.task_id,
            agent_id=view.agent_id,
            question=view.question,
            options=view.options,
            authorized_evidence=view.visible_evidence,
        )

    def controlled_stimulus(
        self, task_id: str, condition: str
    ) -> ControlledStimulus:
        """Return experimenter-side stimulus data without altering an agent view."""

        variant_type = {
            "clear": VariantType.COMPLETE,
            "ambiguous": VariantType.AMBIGUOUS,
            "omission": VariantType.SELECTIVE_OMISSION,
        }.get(condition)
        if variant_type is None:
            raise ValueError(f"unsupported controlled condition: {condition!r}")
        artifact = self._get(task_id)
        variant = next(
            item
            for item in artifact.message_variant_group.variants
            if item.type is variant_type
        )
        return ControlledStimulus(
            task_id=task_id,
            condition=condition,
            variant_id=variant.id,
            text=variant.text,
            source_fact_ids=variant.source_fact_ids,
        )

    def _get(self, task_id: str) -> TaskArtifact:
        try:
            return self._artifacts[task_id]
        except KeyError as exc:
            raise KeyError(f"unknown task ID {task_id!r}") from exc


def _validate_safe_views(artifact: TaskArtifact) -> None:
    task = artifact.task_definition
    facts = {fact.id: fact for fact in task.facts}
    views = {view.agent_id: view for view in artifact.agent_views}
    expected_agents = set(task.allocation.private_fact_ids)
    if set(views) != expected_agents:
        raise BenchmarkLoadError(
            f"task {task.task_id} agent views do not match allocation agents"
        )
    shared = set(task.allocation.shared_fact_ids)
    for agent_id, view in views.items():
        expected_ids = shared | set(task.allocation.private_fact_ids[agent_id])
        visible_ids = {item.fact_id for item in view.visible_evidence}
        if visible_ids != expected_ids:
            raise BenchmarkLoadError(
                f"task {task.task_id} view {agent_id} does not exactly match authorized facts"
            )
        if view.question != task.question or view.options != task.options:
            raise BenchmarkLoadError(
                f"task {task.task_id} view {agent_id} changes question or options"
            )
        for evidence in view.visible_evidence:
            if evidence.text != facts[evidence.fact_id].evidence_text:
                raise BenchmarkLoadError(
                    f"task {task.task_id} view {agent_id} changes evidence text"
                )


def load_benchmark(
    source: str | Path,
    *,
    expected_task_count: int | None = None,
    expected_sha256: str | None = None,
) -> BenchmarkCatalog:
    path = Path(source)
    if not path.is_file():
        raise BenchmarkLoadError(f"benchmark file does not exist: {path}")
    raw = path.read_bytes()
    source_sha256 = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and source_sha256 != expected_sha256:
        raise BenchmarkLoadError("benchmark SHA-256 does not match the expected value")
    try:
        artifacts = tuple(read_jsonl(path))
    except (OSError, ValueError) as exc:
        raise BenchmarkLoadError(str(exc)) from exc
    if not artifacts:
        raise BenchmarkLoadError("benchmark contains no tasks")
    task_ids = [artifact.task_definition.task_id for artifact in artifacts]
    if len(task_ids) != len(set(task_ids)):
        raise BenchmarkLoadError("benchmark task IDs must be unique")
    group_ids = [artifact.message_variant_group.variant_group_id for artifact in artifacts]
    if len(group_ids) != len(set(group_ids)):
        raise BenchmarkLoadError("benchmark variant-group IDs must be unique")
    if expected_task_count is not None and len(artifacts) != expected_task_count:
        raise BenchmarkLoadError(
            f"expected {expected_task_count} tasks but loaded {len(artifacts)}"
        )
    for artifact in artifacts:
        _validate_safe_views(artifact)
    return BenchmarkCatalog(artifacts, source_sha256)

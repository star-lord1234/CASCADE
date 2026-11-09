"""Deterministic evidence allocation and safe AgentView construction."""

from __future__ import annotations

import random

from .schemas import (
    AgentView,
    EvidenceAllocation,
    TaskDefinition,
    VisibleEvidence,
)


def allocate_fact_ids(
    fact_ids: list[str], *, agent_count: int, seed: int
) -> EvidenceAllocation:
    if agent_count < 2:
        raise ValueError("hidden-profile allocation requires at least two agents")
    if len(fact_ids) < agent_count:
        raise ValueError("each agent must receive at least one private fact")

    shuffled = list(fact_ids)
    random.Random(seed).shuffle(shuffled)
    buckets: dict[str, list[str]] = {
        f"agent_{index + 1}": [] for index in range(agent_count)
    }
    agent_ids = list(buckets)
    for index, fact_id in enumerate(shuffled):
        buckets[agent_ids[index % agent_count]].append(fact_id)
    return EvidenceAllocation(
        shared_fact_ids=(),
        private_fact_ids={key: tuple(value) for key, value in buckets.items()},
    )


def build_agent_views(task: TaskDefinition) -> tuple[AgentView, ...]:
    """Serialize only authorized evidence; no ground truth or treatment metadata."""

    facts = {fact.id: fact for fact in task.facts}
    shared = task.allocation.shared_fact_ids
    views: list[AgentView] = []
    for agent_id, private_ids in task.allocation.private_fact_ids.items():
        visible_ids = (*shared, *private_ids)
        views.append(
            AgentView(
                task_id=task.task_id,
                agent_id=agent_id,
                question=task.question,
                options=task.options,
                visible_evidence=tuple(
                    VisibleEvidence(fact_id=fact_id, text=facts[fact_id].evidence_text)
                    for fact_id in visible_ids
                ),
            )
        )
    return tuple(views)


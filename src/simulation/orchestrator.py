"""Minimal deterministic synchronous orchestration for CASCADE Phase 2.2."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Protocol

from .agent import IsolatedAgent
from .communication import deliver_batch, route_controlled_stimulus, route_organic_messages
from .loader import BenchmarkCatalog
from .model_client import ModelClient
from .network import build_adjacency
from .schemas import (
    BeliefSnapshot,
    EpisodeConfig,
    EpisodeResult,
    GroupDecision,
    RoundResult,
    RoutedMessage,
)


class EpisodeConfigurationError(ValueError):
    pass


class EpisodeObserver(Protocol):
    def record_message(self, message: RoutedMessage) -> None: ...

    def record_snapshot(self, snapshot: BeliefSnapshot) -> None: ...

    def record_group_decision(self, decision: GroupDecision) -> None: ...


def aggregate_group(beliefs: tuple[BeliefSnapshot, ...]) -> GroupDecision:
    """Strict majority of all agents; ties and insufficient support abstain."""

    if len(beliefs) < 2:
        raise ValueError("group aggregation requires at least two beliefs")
    counts = Counter(snapshot.private_belief for snapshot in beliefs)
    total = len(beliefs)
    if counts["YES"] > total / 2:
        answer = "YES"
    elif counts["NO"] > total / 2:
        answer = "NO"
    else:
        answer = "ABSTAIN"
    return GroupDecision(
        answer=answer,
        yes_votes=counts["YES"],
        no_votes=counts["NO"],
        unknown_votes=counts["UNKNOWN"],
        total_agents=total,
    )


def _request_id(
    episode_id: str, round_index: int, agent_id: str, purpose: str
) -> str:
    return f"{episode_id}.R{round_index}.{agent_id}.{purpose}"


def _snapshot_id(episode_id: str, round_index: int, agent_id: str) -> str:
    return f"{episode_id}.R{round_index}.{agent_id}.belief"


def run_episode(
    *,
    catalog: BenchmarkCatalog,
    task_id: str,
    episode_id: str,
    config: EpisodeConfig,
    model_clients: Mapping[str, ModelClient],
    observer: EpisodeObserver | None = None,
) -> EpisodeResult:
    """Run Round 0 plus synchronous message/delivery/belief-update rounds."""

    available = catalog.agent_ids(task_id)
    if config.agent_count > len(available):
        raise EpisodeConfigurationError(
            f"task has {len(available)} agent views, fewer than requested {config.agent_count}"
        )
    selected = available[: config.agent_count]
    missing_clients = set(selected) - set(model_clients)
    if missing_clients:
        raise EpisodeConfigurationError(
            f"missing model clients for agents: {sorted(missing_clients)}"
        )
    if config.stimulus_sender_id is not None and config.stimulus_sender_id not in selected:
        raise EpisodeConfigurationError("stimulus sender must be a selected agent")
    if config.star_center_id is not None and config.star_center_id not in selected:
        raise EpisodeConfigurationError("star center must be a selected agent")

    adjacency = build_adjacency(
        selected,
        config.topology,
        star_center_id=config.star_center_id,
    )
    agents = {
        agent_id: IsolatedAgent(
            catalog.agent_context(task_id, agent_id), model_clients[agent_id]
        )
        for agent_id in selected
    }

    snapshots: list[BeliefSnapshot] = []
    routed_messages: list[RoutedMessage] = []
    round_results: list[RoundResult] = []

    # Round 0 is always independent: no message can be delivered before this probe.
    for agent_id in selected:
        turn = agents[agent_id].probe(
            request_id=_request_id(episode_id, 0, agent_id, "belief"),
            snapshot_id=_snapshot_id(episode_id, 0, agent_id),
            episode_id=episode_id,
            round_index=0,
            purpose="belief",
        )
        snapshots.append(turn.snapshot)
        if observer is not None:
            observer.record_snapshot(turn.snapshot)

    if config.condition == "independent":
        final_beliefs = tuple(snapshots)
        final_decision = aggregate_group(final_beliefs)
        if observer is not None:
            observer.record_group_decision(final_decision)
        return EpisodeResult(
            episode_id=episode_id,
            task_id=task_id,
            config=config,
            selected_agent_ids=selected,
            belief_snapshots=tuple(snapshots),
            final_group_decision=final_decision,
        )

    for round_index in range(1, config.communication_rounds + 1):
        controlled: tuple[RoutedMessage, ...] = ()
        if round_index == config.injection_round:
            stimulus = catalog.controlled_stimulus(task_id, config.condition)
            controlled = (
                route_controlled_stimulus(
                    episode_id=episode_id,
                    round_index=round_index,
                    sender_id=config.stimulus_sender_id,
                    recipient_ids=adjacency[config.stimulus_sender_id],
                    stimulus=stimulus,
                ),
            )
            routed_messages.extend(controlled)
            if observer is not None:
                for message in controlled:
                    observer.record_message(message)
            deliver_batch(controlled, agents)

        # All agents generate drafts from the same round boundary. No organic
        # draft is delivered until every selected agent has returned.
        drafts = {}
        for agent_id in selected:
            output = agents[agent_id].respond(
                request_id=_request_id(episode_id, round_index, agent_id, "message"),
                round_index=round_index,
                purpose="message",
            )
            drafts[agent_id] = output.reply.outgoing_message
        organic = route_organic_messages(
            episode_id=episode_id,
            task_id=task_id,
            round_index=round_index,
            agent_order=selected,
            adjacency=adjacency,
            drafts=drafts,
        )
        routed_messages.extend(organic)
        if observer is not None:
            for message in organic:
                observer.record_message(message)
        deliver_batch(organic, agents)

        round_snapshots: list[BeliefSnapshot] = []
        for agent_id in selected:
            turn = agents[agent_id].probe(
                request_id=_request_id(episode_id, round_index, agent_id, "belief"),
                snapshot_id=_snapshot_id(episode_id, round_index, agent_id),
                episode_id=episode_id,
                round_index=round_index,
                purpose="belief",
            )
            snapshots.append(turn.snapshot)
            round_snapshots.append(turn.snapshot)
            if observer is not None:
                observer.record_snapshot(turn.snapshot)
        round_results.append(
            RoundResult(
                round_index=round_index,
                controlled_message_ids=tuple(item.message_id for item in controlled),
                organic_message_ids=tuple(item.message_id for item in organic),
                belief_snapshot_ids=tuple(
                    item.snapshot_id for item in round_snapshots
                ),
            )
        )

    final_beliefs = tuple(
        snapshot
        for snapshot in snapshots
        if snapshot.round_index == config.communication_rounds
    )
    final_decision = aggregate_group(final_beliefs)
    if observer is not None:
        observer.record_group_decision(final_decision)
    return EpisodeResult(
        episode_id=episode_id,
        task_id=task_id,
        config=config,
        selected_agent_ids=selected,
        belief_snapshots=tuple(snapshots),
        routed_messages=tuple(routed_messages),
        rounds=tuple(round_results),
        final_group_decision=final_decision,
    )

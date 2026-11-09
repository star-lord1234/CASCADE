"""Deterministic routing and delivery for controlled and organic messages."""

from __future__ import annotations

from collections.abc import Mapping

from .agent import IsolatedAgent
from .schemas import ControlledStimulus, PublicMessageDraft, RoutedMessage


def route_controlled_stimulus(
    *,
    episode_id: str,
    round_index: int,
    sender_id: str,
    recipient_ids: tuple[str, ...],
    stimulus: ControlledStimulus,
) -> RoutedMessage:
    return RoutedMessage(
        message_id=f"{episode_id}.R{round_index}.controlled",
        task_id=stimulus.task_id,
        round_index=round_index,
        sender_id=sender_id,
        recipient_ids=recipient_ids,
        text=stimulus.text,
        source_fact_ids=stimulus.source_fact_ids,
        public_recommendation="UNKNOWN",
        origin="controlled",
        condition_tag=stimulus.condition,
        variant_id=stimulus.variant_id,
    )


def route_organic_messages(
    *,
    episode_id: str,
    task_id: str,
    round_index: int,
    agent_order: tuple[str, ...],
    adjacency: Mapping[str, tuple[str, ...]],
    drafts: Mapping[str, PublicMessageDraft | None],
) -> tuple[RoutedMessage, ...]:
    """Route a complete batch in stable sender order after all drafts exist."""

    routed: list[RoutedMessage] = []
    for sender_id in agent_order:
        draft = drafts.get(sender_id)
        if draft is None:
            continue
        routed.append(
            RoutedMessage(
                message_id=f"{episode_id}.R{round_index}.organic.{len(routed) + 1}",
                task_id=task_id,
                round_index=round_index,
                sender_id=sender_id,
                recipient_ids=adjacency[sender_id],
                text=draft.text,
                source_fact_ids=draft.source_fact_ids,
                parent_message_ids=draft.parent_message_ids,
                public_recommendation=draft.public_recommendation,
                origin="organic",
            )
        )
    return tuple(routed)


def deliver_batch(
    messages: tuple[RoutedMessage, ...], agents: Mapping[str, IsolatedAgent]
) -> None:
    """Deliver only after routing has produced the entire immutable batch."""

    for message in messages:
        for recipient_id in message.recipient_ids:
            agents[recipient_id].deliver(message.for_recipient(recipient_id))

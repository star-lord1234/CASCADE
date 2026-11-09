"""Cross-reference and replay-safety validation for episode traces."""

from __future__ import annotations

import json
from collections import Counter

from pydantic import Field

from .loader import BenchmarkCatalog
from .network import build_adjacency
from .schemas import StrictSimulationModel
from .trace_schemas import EpisodeTrace


class TraceValidationError(ValueError):
    pass


class TraceValidationReport(StrictSimulationModel):
    valid: bool
    check_count: int = Field(ge=0)
    errors: tuple[str, ...] = ()


def validate_trace(
    trace: EpisodeTrace,
    catalog: BenchmarkCatalog,
    *,
    raise_on_error: bool = True,
) -> TraceValidationReport:
    errors: list[str] = []
    checks = 0

    def check(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            errors.append(message)

    check(trace.benchmark_sha256 == catalog.source_sha256, "benchmark hash mismatch")
    try:
        available = catalog.agent_ids(trace.task_id)
    except KeyError:
        available = ()
    check(bool(available), "trace task does not exist in benchmark")
    expected_selected = available[: trace.config.agent_count]
    check(
        trace.selected_agent_ids == expected_selected,
        "selected agents do not match deterministic view selection",
    )
    if available:
        expected_adjacency = build_adjacency(
            trace.selected_agent_ids,
            trace.config.topology,
            star_center_id=trace.config.star_center_id,
        )
        check(trace.adjacency == expected_adjacency, "trace adjacency is inconsistent")

    views = {view.agent_id: view for view in trace.agent_views_audit}
    for agent_id in trace.selected_agent_ids:
        expected_view = catalog.agent_view(trace.task_id, agent_id) if available else None
        check(
            views.get(agent_id) == expected_view,
            f"audit view mismatch for {agent_id}",
        )

    message_events = {event.message.message_id: event for event in trace.messages}
    check(
        len(message_events) == len(trace.messages),
        "message IDs must be unique",
    )
    snapshot_events = {event.snapshot.snapshot_id: event for event in trace.beliefs}
    check(
        len(snapshot_events) == len(trace.beliefs),
        "belief snapshot IDs must be unique",
    )
    request_ids = [event.request.request_id for event in trace.model_calls]
    check(len(request_ids) == len(set(request_ids)), "model request IDs must be unique")

    view_fact_ids = {
        agent_id: {item.fact_id for item in view.visible_evidence}
        for agent_id, view in views.items()
    }
    model_calls_by_key = {}
    for event in trace.model_calls:
        request = event.request
        check(request.task_id == trace.task_id, "model request task mismatch")
        check(
            request.agent_id in trace.selected_agent_ids,
            "model request uses an unselected agent",
        )
        key = (request.round_index, request.agent_id, request.purpose)
        check(key not in model_calls_by_key, f"duplicate model-call phase {key}")
        model_calls_by_key[key] = event
        prompt_payload = _user_payload(request)
        check(prompt_payload is not None, "model request lacks a valid user JSON payload")
        if prompt_payload is not None and request.agent_id in views:
            check(
                set(prompt_payload) == {
                    "task_id",
                    "agent_id",
                    "question",
                    "options",
                    "authorized_evidence",
                    "delivered_messages",
                },
                "model prompt contains hidden or unexpected top-level fields",
            )
            expected_evidence = [
                item.model_dump(mode="json")
                for item in views[request.agent_id].visible_evidence
            ]
            check(
                prompt_payload.get("authorized_evidence") == expected_evidence,
                "model prompt evidence differs from the authorized view",
            )
            delivered = prompt_payload.get("delivered_messages", [])
            delivered_ids = {item.get("message_id") for item in delivered}
            for item in delivered:
                check(
                    not {"origin", "condition_tag", "variant_id"} & set(item),
                    "agent-facing delivery leaks experimental provenance",
                )
                source = message_events.get(item.get("message_id"))
                check(source is not None, "prompt cites an unknown delivered message")
                if source is not None:
                    check(
                        request.agent_id in source.message.recipient_ids,
                        "prompt includes a message not routed to this agent",
                    )
                    check(
                        source.event_order < event.event_order,
                        "prompt includes a message not yet delivered",
                    )
            if event.reply is not None:
                reply = event.reply
                check(
                    set(reply.supporting_fact_ids).issubset(
                        view_fact_ids[request.agent_id]
                    ),
                    "model reply cites unauthorized supporting evidence",
                )
                if reply.outgoing_message is not None:
                    check(
                        set(reply.outgoing_message.source_fact_ids).issubset(
                            view_fact_ids[request.agent_id]
                        ),
                        "model message cites unauthorized source evidence",
                    )
                    check(
                        set(reply.outgoing_message.parent_message_ids).issubset(
                            delivered_ids
                        ),
                        "model message cites an undelivered parent",
                    )

    controlled_events = [
        event for event in trace.messages if event.message.origin == "controlled"
    ]
    if trace.config.condition == "independent":
        check(not controlled_events, "independent trace contains a controlled stimulus")
    elif trace.status == "completed":
        check(len(controlled_events) == 1, "message condition needs one controlled stimulus")
    for event in trace.messages:
        message = event.message
        check(message.task_id == trace.task_id, "message task mismatch")
        check(message.sender_id in trace.selected_agent_ids, "message sender is unselected")
        check(
            set(message.recipient_ids).issubset(trace.selected_agent_ids),
            "message recipient is unselected",
        )
        check(
            message.recipient_ids == trace.adjacency[message.sender_id],
            "message recipients do not match topology",
        )
        if message.origin == "controlled":
            check(
                message.condition_tag == trace.config.condition,
                "controlled message condition mismatch",
            )
            stimulus = catalog.controlled_stimulus(
                trace.task_id, trace.config.condition
            )
            check(message.variant_id == stimulus.variant_id, "controlled variant mismatch")
            check(message.text == stimulus.text, "controlled message text mismatch")
            check(
                message.source_fact_ids == stimulus.source_fact_ids,
                "controlled message source facts mismatch",
            )
        else:
            check(
                set(message.source_fact_ids).issubset(
                    view_fact_ids.get(message.sender_id, set())
                ),
                "organic message cites facts not authorized to its sender",
            )
            call = model_calls_by_key.get(
                (message.round_index, message.sender_id, "message")
            )
            check(call is not None, "organic message lacks a generating model call")
            if call is not None:
                check(call.event_order < event.event_order, "message precedes its model call")
                draft = call.reply.outgoing_message if call.reply else None
                check(
                    draft is not None
                    and draft.text == message.text
                    and draft.source_fact_ids == message.source_fact_ids
                    and draft.parent_message_ids == message.parent_message_ids
                    and draft.public_recommendation == message.public_recommendation,
                    "organic message differs from its model draft",
                )
            for parent_id in message.parent_message_ids:
                parent = message_events.get(parent_id)
                check(parent is not None, "organic message cites an unknown parent")
                if parent is not None:
                    check(
                        parent.event_order < event.event_order
                        and message.sender_id in parent.message.recipient_ids,
                        "organic parent was not previously delivered to sender",
                    )

    for round_index in range(1, trace.config.communication_rounds + 1):
        message_calls = [
            event
            for event in trace.model_calls
            if event.request.round_index == round_index
            and event.request.purpose == "message"
        ]
        organic = [
            event
            for event in trace.messages
            if event.message.round_index == round_index
            and event.message.origin == "organic"
        ]
        if organic and message_calls:
            check(
                max(event.event_order for event in message_calls)
                < min(event.event_order for event in organic),
                "organic delivery occurred before all same-round drafts were collected",
            )

    for event in trace.beliefs:
        snapshot = event.snapshot
        check(snapshot.episode_id == trace.episode_id, "belief episode mismatch")
        check(snapshot.task_id == trace.task_id, "belief task mismatch")
        check(snapshot.agent_id in trace.selected_agent_ids, "belief agent is unselected")
        check(
            set(snapshot.supporting_fact_ids).issubset(
                view_fact_ids.get(snapshot.agent_id, set())
            ),
            "belief cites unauthorized evidence",
        )
        if snapshot.round_index == 0:
            check(not snapshot.received_message_ids, "Round 0 belief received messages")
        for message_id in snapshot.received_message_ids:
            message_event = message_events.get(message_id)
            check(message_event is not None, "belief cites an unknown received message")
            if message_event is not None:
                check(
                    snapshot.agent_id in message_event.message.recipient_ids,
                    "belief cites a message not routed to its agent",
                )
                check(
                    message_event.event_order < event.event_order,
                    "belief cites a future message",
                )
        call = model_calls_by_key.get(
            (snapshot.round_index, snapshot.agent_id, "belief")
        )
        check(call is not None, "belief lacks a generating model call")
        if call is not None and call.reply is not None:
            reply = call.reply
            check(call.event_order < event.event_order, "belief precedes its model call")
            check(
                (
                    reply.private_belief,
                    reply.confidence,
                    reply.supporting_fact_ids,
                    reply.uncertainty,
                    reply.public_recommendation,
                )
                == (
                    snapshot.private_belief,
                    snapshot.confidence,
                    snapshot.supporting_fact_ids,
                    snapshot.uncertainty,
                    snapshot.public_recommendation,
                ),
                "belief snapshot differs from parsed model reply",
            )

    if trace.status == "completed" and trace.group_decision is not None:
        final_round = trace.config.communication_rounds
        final = [
            event.snapshot
            for event in trace.beliefs
            if event.snapshot.round_index == final_round
        ]
        counts = Counter(item.private_belief for item in final)
        total = len(trace.selected_agent_ids)
        expected = (
            "YES"
            if counts["YES"] > total / 2
            else "NO"
            if counts["NO"] > total / 2
            else "ABSTAIN"
        )
        decision = trace.group_decision.decision
        check(len(final) == total, "final round lacks one belief per agent")
        check(decision.answer == expected, "group decision is not reproducible")
        check(
            (decision.yes_votes, decision.no_votes, decision.unknown_votes)
            == (counts["YES"], counts["NO"], counts["UNKNOWN"]),
            "group vote counts are not reproducible",
        )

    report = TraceValidationReport(
        valid=not errors,
        check_count=checks,
        errors=tuple(errors),
    )
    if errors and raise_on_error:
        raise TraceValidationError("; ".join(errors))
    return report


def _user_payload(request) -> dict | None:
    user_messages = [message for message in request.messages if message.role == "user"]
    if len(user_messages) != 1:
        return None
    try:
        payload = json.loads(user_messages[0].content)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None

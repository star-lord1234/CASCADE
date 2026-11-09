"""Isolated per-agent context and validated belief probing."""

from __future__ import annotations

import json
from typing import Literal

from .model_client import ModelClient
from .schemas import (
    AgentContext,
    AgentTurnResult,
    BeliefSnapshot,
    ChatMessage,
    DeliveredMessage,
    ModelOutput,
    ModelRequest,
)


class AgentResponseValidationError(ValueError):
    """Raised when a valid JSON reply violates this agent's authorization."""


class IsolatedAgent:
    """One model session whose prompt boundary contains only authorized data."""

    def __init__(self, context: AgentContext, model_client: ModelClient) -> None:
        self._context = context
        self._model_client = model_client

    @property
    def context(self) -> AgentContext:
        return self._context

    def deliver(self, message: DeliveredMessage) -> None:
        """Add one already-routed message without exposing any sender-private context."""

        candidate = self._context.model_dump()
        candidate["delivered_messages"] = (
            self._context.delivered_messages + (message,)
        )
        # Validate before assignment so a rejected delivery cannot corrupt context.
        self._context = AgentContext.model_validate(candidate)

    def build_request(
        self,
        *,
        request_id: str,
        round_index: int,
        purpose: Literal["belief", "message"] = "belief",
    ) -> ModelRequest:
        visible = {
            "task_id": self._context.task_id,
            "agent_id": self._context.agent_id,
            "question": self._context.question,
            "options": list(self._context.options),
            "authorized_evidence": [
                evidence.model_dump(mode="json")
                for evidence in self._context.authorized_evidence
            ],
            "delivered_messages": [
                message.model_dump(mode="json")
                for message in self._context.delivered_messages
            ],
        }
        phase_instruction = (
            "Set outgoing_message to null; report your current private belief and public recommendation."
            if purpose == "belief"
            else "You may produce one natural outgoing_message for your neighbors, or null if you have nothing useful to send."
        )
        system = ChatMessage(
            role="system",
            content=(
                "You are one isolated decision agent. Use only the supplied authorized "
                "evidence and delivered messages. Missing facts must not be assumed; "
                "UNKNOWN is allowed. Return exactly one JSON object with no prose or "
                "Markdown fences. Include exactly these top-level keys: private_belief, "
                "confidence, supporting_fact_ids, uncertainty, public_recommendation, "
                "and outgoing_message. Use an empty array when there are no supporting "
                "fact IDs and null when uncertainty or outgoing_message is absent. "
                "supporting_fact_ids and outgoing source_fact_ids may cite only "
                "authorized evidence IDs. parent_message_ids may cite only delivered "
                "message IDs. Confidence is self-reported from 0 to 1. "
                + phase_instruction
            ),
        )
        user = ChatMessage(
            role="user",
            content=json.dumps(visible, sort_keys=True, separators=(",", ":")),
        )
        return ModelRequest(
            request_id=request_id,
            task_id=self._context.task_id,
            agent_id=self._context.agent_id,
            round_index=round_index,
            purpose=purpose,
            messages=(system, user),
        )

    def respond(
        self,
        *,
        request_id: str,
        round_index: int,
        purpose: Literal["belief", "message"] = "belief",
    ) -> ModelOutput:
        request = self.build_request(
            request_id=request_id,
            round_index=round_index,
            purpose=purpose,
        )
        output = self._model_client.generate(request)
        reply = output.reply
        authorized_fact_ids = {
            evidence.fact_id for evidence in self._context.authorized_evidence
        }
        delivered_message_ids = {
            message.message_id for message in self._context.delivered_messages
        }
        unknown_support = set(reply.supporting_fact_ids) - authorized_fact_ids
        if unknown_support:
            raise AgentResponseValidationError(
                f"reply cites unauthorized supporting facts: {sorted(unknown_support)}"
            )
        outgoing = reply.outgoing_message
        if outgoing is not None:
            unknown_sources = set(outgoing.source_fact_ids) - authorized_fact_ids
            if unknown_sources:
                raise AgentResponseValidationError(
                    f"outgoing message cites unauthorized facts: {sorted(unknown_sources)}"
                )
            unknown_parents = set(outgoing.parent_message_ids) - delivered_message_ids
            if unknown_parents:
                raise AgentResponseValidationError(
                    f"outgoing message cites undelivered messages: {sorted(unknown_parents)}"
                )
        return output

    def probe(
        self,
        *,
        request_id: str,
        snapshot_id: str,
        episode_id: str,
        round_index: int,
        purpose: Literal["belief", "message"] = "belief",
    ) -> AgentTurnResult:
        output = self.respond(
            request_id=request_id,
            round_index=round_index,
            purpose=purpose,
        )
        reply = output.reply
        snapshot = BeliefSnapshot(
            snapshot_id=snapshot_id,
            episode_id=episode_id,
            task_id=self._context.task_id,
            agent_id=self._context.agent_id,
            round_index=round_index,
            private_belief=reply.private_belief,
            confidence=reply.confidence,
            supporting_fact_ids=reply.supporting_fact_ids,
            uncertainty=reply.uncertainty,
            received_message_ids=tuple(
                message.message_id for message in self._context.delivered_messages
            ),
            public_recommendation=reply.public_recommendation,
        )
        return AgentTurnResult(
            snapshot=snapshot,
            outgoing_message=reply.outgoing_message,
            model_name=output.model_name,
            response_id=output.response_id,
            input_tokens=output.input_tokens,
            output_tokens=output.output_tokens,
        )

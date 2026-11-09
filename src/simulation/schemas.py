"""Strict schemas at the Phase 2 agent/model privacy boundary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.tasks.schemas import Identifier, VisibleEvidence

SIMULATION_SCHEMA_VERSION = "1.0"
Answer = Literal["YES", "NO", "UNKNOWN"]
Condition = Literal["independent", "clear", "ambiguous", "omission"]
TopologyName = Literal["fully_connected", "ring", "star"]


class StrictSimulationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PublicMessageDraft(StrictSimulationModel):
    """Agent-authored message before orchestration assigns routing metadata."""

    text: str = Field(min_length=1)
    source_fact_ids: tuple[Identifier, ...] = ()
    parent_message_ids: tuple[Identifier, ...] = ()
    public_recommendation: Answer


class DeliveredMessage(StrictSimulationModel):
    """A message already authorized for one isolated recipient context."""

    schema_version: Literal[SIMULATION_SCHEMA_VERSION] = SIMULATION_SCHEMA_VERSION
    message_id: Identifier
    task_id: Identifier
    sender_id: Identifier
    recipient_id: Identifier
    round_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    source_fact_ids: tuple[Identifier, ...] = ()
    parent_message_ids: tuple[Identifier, ...] = ()
    public_recommendation: Answer


class AgentModelReply(StrictSimulationModel):
    """Only accepted structured reply from a participating model."""

    private_belief: Answer
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_fact_ids: tuple[Identifier, ...] = ()
    uncertainty: str | None = None
    public_recommendation: Answer
    outgoing_message: PublicMessageDraft | None = None

    @model_validator(mode="after")
    def unique_references(self) -> "AgentModelReply":
        if len(self.supporting_fact_ids) != len(set(self.supporting_fact_ids)):
            raise ValueError("supporting fact IDs must be unique")
        if self.outgoing_message is not None:
            draft = self.outgoing_message
            if len(draft.source_fact_ids) != len(set(draft.source_fact_ids)):
                raise ValueError("outgoing source fact IDs must be unique")
            if len(draft.parent_message_ids) != len(set(draft.parent_message_ids)):
                raise ValueError("parent message IDs must be unique")
        return self


class BeliefSnapshot(StrictSimulationModel):
    schema_version: Literal[SIMULATION_SCHEMA_VERSION] = SIMULATION_SCHEMA_VERSION
    snapshot_id: Identifier
    episode_id: Identifier
    task_id: Identifier
    agent_id: Identifier
    round_index: int = Field(ge=0)
    private_belief: Answer
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_fact_ids: tuple[Identifier, ...] = ()
    uncertainty: str | None = None
    received_message_ids: tuple[Identifier, ...] = ()
    public_recommendation: Answer


class ChatMessage(StrictSimulationModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ModelRequest(StrictSimulationModel):
    request_id: Identifier
    task_id: Identifier
    agent_id: Identifier
    round_index: int = Field(ge=0)
    purpose: Literal["belief", "message"] = "belief"
    messages: tuple[ChatMessage, ...] = Field(min_length=1)


class ModelOutput(StrictSimulationModel):
    reply: AgentModelReply
    model_name: str = Field(min_length=1)
    response_id: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class AgentContext(StrictSimulationModel):
    """The complete and exclusive context visible to one participating agent."""

    schema_version: Literal[SIMULATION_SCHEMA_VERSION] = SIMULATION_SCHEMA_VERSION
    task_id: Identifier
    agent_id: Identifier
    question: str = Field(min_length=1)
    options: tuple[Answer, Answer, Answer]
    authorized_evidence: tuple[VisibleEvidence, ...]
    delivered_messages: tuple[DeliveredMessage, ...] = ()

    @model_validator(mode="after")
    def validate_isolated_context(self) -> "AgentContext":
        if set(self.options) != {"YES", "NO", "UNKNOWN"}:
            raise ValueError("agent options must be YES, NO, and UNKNOWN")
        evidence_ids = [item.fact_id for item in self.authorized_evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("authorized evidence IDs must be unique")
        message_ids = [message.message_id for message in self.delivered_messages]
        if len(message_ids) != len(set(message_ids)):
            raise ValueError("delivered message IDs must be unique")
        for message in self.delivered_messages:
            if message.task_id != self.task_id:
                raise ValueError("delivered message belongs to another task")
            if message.recipient_id != self.agent_id:
                raise ValueError("delivered message belongs to another recipient")
        return self


class AgentTurnResult(StrictSimulationModel):
    snapshot: BeliefSnapshot
    outgoing_message: PublicMessageDraft | None = None
    model_name: str = Field(min_length=1)
    response_id: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class ControlledStimulus(StrictSimulationModel):
    """Experimenter-only matched stimulus; never serialized into an agent prompt."""

    task_id: Identifier
    condition: Literal["clear", "ambiguous", "omission"]
    variant_id: Identifier
    text: str = Field(min_length=1)
    source_fact_ids: tuple[Identifier, ...] = Field(min_length=1)


class EpisodeConfig(StrictSimulationModel):
    condition: Condition
    topology: TopologyName = "fully_connected"
    repetition: int = Field(default=1, ge=1)
    random_seed: int = 42
    communication_rounds: int = Field(default=1, ge=0)
    agent_count: int = Field(default=5, ge=2, le=5)
    injection_round: int | None = 1
    stimulus_sender_id: Identifier | None = None
    star_center_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_condition_and_topology(self) -> "EpisodeConfig":
        if self.condition == "independent":
            if self.communication_rounds != 0:
                raise ValueError("independent condition requires zero communication rounds")
            if self.injection_round is not None or self.stimulus_sender_id is not None:
                raise ValueError("independent condition cannot inject a stimulus")
        else:
            if self.communication_rounds < 1:
                raise ValueError("message conditions require at least one communication round")
            if self.injection_round is None:
                raise ValueError("message conditions require an injection round")
            if not 1 <= self.injection_round <= self.communication_rounds:
                raise ValueError("injection round must occur within communication rounds")
            if self.stimulus_sender_id is None:
                raise ValueError("message conditions require an explicit stimulus sender")
        if self.topology == "star" and self.star_center_id is None:
            raise ValueError("star topology requires an explicit center")
        if self.topology != "star" and self.star_center_id is not None:
            raise ValueError("star center may be set only for star topology")
        return self


class RoutedMessage(StrictSimulationModel):
    """Experimenter-side routing record with provenance stripped on delivery."""

    message_id: Identifier
    task_id: Identifier
    round_index: int = Field(ge=1)
    sender_id: Identifier
    recipient_ids: tuple[Identifier, ...] = Field(min_length=1)
    text: str = Field(min_length=1)
    source_fact_ids: tuple[Identifier, ...] = ()
    parent_message_ids: tuple[Identifier, ...] = ()
    public_recommendation: Answer
    origin: Literal["organic", "controlled"]
    condition_tag: Literal["clear", "ambiguous", "omission"] | None = None
    variant_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_routing_and_provenance(self) -> "RoutedMessage":
        if self.sender_id in self.recipient_ids:
            raise ValueError("sender cannot receive its own routed message")
        if len(self.recipient_ids) != len(set(self.recipient_ids)):
            raise ValueError("routed recipients must be unique")
        if self.origin == "controlled":
            if self.condition_tag is None or self.variant_id is None:
                raise ValueError("controlled messages require condition and variant provenance")
        elif self.condition_tag is not None or self.variant_id is not None:
            raise ValueError("organic messages cannot claim controlled provenance")
        return self

    def for_recipient(self, recipient_id: str) -> DeliveredMessage:
        if recipient_id not in self.recipient_ids:
            raise ValueError("recipient is not authorized for this routed message")
        return DeliveredMessage(
            message_id=self.message_id,
            task_id=self.task_id,
            sender_id=self.sender_id,
            recipient_id=recipient_id,
            round_index=self.round_index,
            text=self.text,
            # Controlled source IDs are experimenter provenance, not message text.
            # Keep them on RoutedMessage for validation/analysis, but do not reveal
            # identifiers for facts outside a recipient's private allocation.
            source_fact_ids=() if self.origin == "controlled" else self.source_fact_ids,
            parent_message_ids=self.parent_message_ids,
            public_recommendation=self.public_recommendation,
        )


class RoundResult(StrictSimulationModel):
    round_index: int = Field(ge=1)
    controlled_message_ids: tuple[Identifier, ...] = ()
    organic_message_ids: tuple[Identifier, ...] = ()
    belief_snapshot_ids: tuple[Identifier, ...] = Field(min_length=1)


class GroupDecision(StrictSimulationModel):
    answer: Literal["YES", "NO", "ABSTAIN"]
    yes_votes: int = Field(ge=0)
    no_votes: int = Field(ge=0)
    unknown_votes: int = Field(ge=0)
    total_agents: int = Field(ge=2)
    rule: Literal["strict_majority_all_agents_tie_or_insufficient_abstain"] = (
        "strict_majority_all_agents_tie_or_insufficient_abstain"
    )

    @model_validator(mode="after")
    def validate_vote_counts(self) -> "GroupDecision":
        if self.yes_votes + self.no_votes + self.unknown_votes != self.total_agents:
            raise ValueError("group vote counts must equal total agents")
        return self


class EpisodeResult(StrictSimulationModel):
    episode_id: Identifier
    task_id: Identifier
    config: EpisodeConfig
    selected_agent_ids: tuple[Identifier, ...] = Field(min_length=2)
    belief_snapshots: tuple[BeliefSnapshot, ...] = Field(min_length=2)
    routed_messages: tuple[RoutedMessage, ...] = ()
    rounds: tuple[RoundResult, ...] = ()
    final_group_decision: GroupDecision

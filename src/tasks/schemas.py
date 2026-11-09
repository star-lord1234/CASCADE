"""Versioned canonical schemas for CASCADE Phase 1 artifacts."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "2.0"
Scalar = str | int | float | bool
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ComparisonOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    LT = "lt"
    LE = "le"
    GT = "gt"
    GE = "ge"


class VariantType(str, Enum):
    COMPLETE = "complete"
    AMBIGUOUS = "ambiguous"
    SELECTIVE_OMISSION = "selective_omission"
    EXPLICIT_FALSEHOOD = "explicit_falsehood"


class TruthStatus(str, Enum):
    ENTAILED = "entailed"
    CONTRADICTED = "contradicted"
    NEEDS_REVIEW = "needs_review"


class ReviewStatus(str, Enum):
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class AmbiguityCategory(str, Enum):
    REFERENTIAL = "referential_ambiguity"
    SELECTIVE_OMISSION = "selective_omission"
    SCOPE = "scope_quantifier"
    TEMPORAL = "temporal_ambiguity"


class AtomicFact(StrictModel):
    id: Identifier
    subject: str = Field(min_length=1)
    entity_id: Identifier | None = None
    predicate: Identifier
    value: Scalar
    evidence_text: str = Field(min_length=1)


class Constraint(StrictModel):
    id: Identifier
    left_fact_id: Identifier
    operator: ComparisonOperator
    right_fact_id: Identifier | None = None
    expected_value: Scalar | None = None
    description: str = Field(min_length=1)

    @model_validator(mode="after")
    def exactly_one_right_operand(self) -> "Constraint":
        if (self.right_fact_id is None) == (self.expected_value is None):
            raise ValueError("constraint needs exactly one right operand")
        return self


class DecisionRule(StrictModel):
    rule_type: Literal["all_constraints"] = "all_constraints"
    constraints: tuple[Constraint, ...] = Field(min_length=1)
    satisfied_answer: str = Field(min_length=1)
    violated_answer: str = Field(min_length=1)
    unknown_answer: Literal["UNKNOWN"] = "UNKNOWN"


class GroundTruth(StrictModel):
    answer: str = Field(min_length=1)
    required_fact_ids: tuple[Identifier, ...] = Field(min_length=1)
    decisive_fact_ids: tuple[Identifier, ...] = Field(min_length=1)
    explanation: str = Field(min_length=1)


class EvidenceAllocation(StrictModel):
    shared_fact_ids: tuple[Identifier, ...] = ()
    private_fact_ids: dict[Identifier, tuple[Identifier, ...]]


class TaskDefinition(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    task_id: Identifier
    variant_group_id: Identifier
    family: Literal["hidden_profile"] = "hidden_profile"
    domain: Identifier
    entity_ids: tuple[Identifier, ...] = ()
    question: str = Field(min_length=1)
    options: tuple[str, ...] = Field(min_length=3)
    facts: tuple[AtomicFact, ...] = Field(min_length=1)
    decision_rule: DecisionRule
    ground_truth: GroundTruth
    allocation: EvidenceAllocation
    generation_seed: int

    @model_validator(mode="after")
    def validate_internal_references(self) -> "TaskDefinition":
        fact_ids = [fact.id for fact in self.facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("fact IDs must be unique")
        known = set(fact_ids)
        if len(self.entity_ids) != len(set(self.entity_ids)):
            raise ValueError("entity IDs must be unique")
        unknown_entities = {
            fact.entity_id
            for fact in self.facts
            if fact.entity_id is not None and fact.entity_id not in self.entity_ids
        }
        if unknown_entities:
            raise ValueError(f"undefined entity references: {sorted(unknown_entities)}")
        referenced: set[str] = set(self.ground_truth.required_fact_ids)
        referenced.update(self.ground_truth.decisive_fact_ids)
        referenced.update(self.allocation.shared_fact_ids)
        for assigned in self.allocation.private_fact_ids.values():
            referenced.update(assigned)
        for constraint in self.decision_rule.constraints:
            referenced.add(constraint.left_fact_id)
            if constraint.right_fact_id:
                referenced.add(constraint.right_fact_id)
        missing = referenced - known
        if missing:
            raise ValueError(f"unknown fact references: {sorted(missing)}")
        assigned = list(self.allocation.shared_fact_ids)
        for private_ids in self.allocation.private_fact_ids.values():
            assigned.extend(private_ids)
        if len(assigned) != len(set(assigned)):
            raise ValueError("a fact may be allocated only once")
        if set(assigned) != known:
            raise ValueError("every fact must be allocated exactly once")
        rule_answers = {
            self.decision_rule.satisfied_answer,
            self.decision_rule.violated_answer,
            self.decision_rule.unknown_answer,
        }
        if len(rule_answers) != 3 or len(self.options) != len(set(self.options)):
            raise ValueError("decision answers and options must be distinct")
        if set(self.options) != rule_answers:
            raise ValueError("options must exactly match the rule answers")
        if self.ground_truth.answer == "UNKNOWN":
            raise ValueError("complete evidence may not have UNKNOWN ground truth")
        values = {fact.id: fact.value for fact in self.facts}
        ordered = {
            ComparisonOperator.LT,
            ComparisonOperator.LE,
            ComparisonOperator.GT,
            ComparisonOperator.GE,
        }
        for constraint in self.decision_rule.constraints:
            if constraint.operator not in ordered:
                continue
            right = (
                values[constraint.right_fact_id]
                if constraint.right_fact_id is not None
                else constraint.expected_value
            )
            if isinstance(values[constraint.left_fact_id], str) or isinstance(right, str):
                raise ValueError("ordered comparisons may not use string values")
        return self


class MessageVariant(StrictModel):
    id: Identifier
    type: VariantType
    text: str = Field(min_length=1)
    source_fact_ids: tuple[Identifier, ...] = Field(min_length=1)
    truth_status: TruthStatus
    ambiguity_type: Identifier
    omitted_fact_ids: tuple[Identifier, ...] = ()
    defensible_interpretation: str | None = None
    misleading_interpretation: str | None = None
    truth_constraints: tuple[Constraint, ...] = ()
    recommended_answer: str | None = None


class SemanticReview(StrictModel):
    status: ReviewStatus = ReviewStatus.NEEDS_REVIEW
    reviewer: str | None = None
    notes: str | None = None


class ReferentialAmbiguityContract(StrictModel):
    kind: Literal["referential"] = "referential"
    surface_form: str = Field(min_length=1)
    defensible_entity_id: Identifier
    misleading_entity_id: Identifier


class OmissionAmbiguityContract(StrictModel):
    kind: Literal["omission"] = "omission"
    omitted_qualifier_fact_ids: tuple[Identifier, ...] = Field(min_length=1)


class ScopeAmbiguityContract(StrictModel):
    kind: Literal["scope"] = "scope"
    quantifier: Literal["all", "every", "some"]
    defensible_scope_entity_ids: tuple[Identifier, ...] = Field(min_length=1)
    misleading_scope_entity_ids: tuple[Identifier, ...] = Field(min_length=1)


class TemporalAmbiguityContract(StrictModel):
    kind: Literal["temporal"] = "temporal"
    time_unit: Literal["minute", "day", "phase"]
    defensible_time_fact_id: Identifier
    misleading_time_fact_id: Identifier


AmbiguityContract = (
    ReferentialAmbiguityContract
    | OmissionAmbiguityContract
    | ScopeAmbiguityContract
    | TemporalAmbiguityContract
)


class MessageVariantGroup(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    variant_group_id: Identifier
    task_id: Identifier
    ambiguity_category: AmbiguityCategory | None = None
    ambiguity_contract: AmbiguityContract | None = None
    source_fact_ids: tuple[Identifier, ...] = Field(min_length=1)
    intended_misleading_inference: str = Field(min_length=1)
    intended_incorrect_answer: str | None = None
    intended_inference_overrides: dict[Identifier, Scalar] = Field(default_factory=dict)
    decisive_qualifier_fact_ids: tuple[Identifier, ...] = Field(min_length=1)
    variants: tuple[MessageVariant, ...] = Field(min_length=3)
    semantic_review: SemanticReview = SemanticReview()

    @model_validator(mode="after")
    def validate_matched_variants(self) -> "MessageVariantGroup":
        variant_types = [variant.type for variant in self.variants]
        required = {
            VariantType.COMPLETE,
            VariantType.AMBIGUOUS,
            VariantType.SELECTIVE_OMISSION,
        }
        if not required.issubset(variant_types):
            raise ValueError("group needs complete, ambiguous, and omission variants")
        if len(variant_types) != len(set(variant_types)):
            raise ValueError("variant types must be unique within a group")
        if len({variant.id for variant in self.variants}) != len(self.variants):
            raise ValueError("variant IDs must be unique")
        group_sources = set(self.source_fact_ids)
        for variant in self.variants:
            if not set(variant.source_fact_ids).issubset(group_sources):
                raise ValueError("variant source facts must belong to its group")
            if not set(variant.omitted_fact_ids).issubset(group_sources):
                raise ValueError("omitted facts must belong to its group")
            if variant.type is VariantType.COMPLETE and variant.omitted_fact_ids:
                raise ValueError("complete variant may not omit facts")
            if variant.type is VariantType.AMBIGUOUS and not variant.defensible_interpretation:
                raise ValueError("ambiguous variant needs a defensible interpretation")
            if variant.type is VariantType.SELECTIVE_OMISSION and not variant.omitted_fact_ids:
                raise ValueError("omission variant must identify omitted facts")
        if self.ambiguity_category is not None:
            expected_kind = {
                AmbiguityCategory.REFERENTIAL: "referential",
                AmbiguityCategory.SELECTIVE_OMISSION: "omission",
                AmbiguityCategory.SCOPE: "scope",
                AmbiguityCategory.TEMPORAL: "temporal",
            }[self.ambiguity_category]
            if self.ambiguity_contract is None or self.ambiguity_contract.kind != expected_kind:
                raise ValueError("ambiguity category and contract do not match")
        return self


class VisibleEvidence(StrictModel):
    fact_id: Identifier
    text: str = Field(min_length=1)


class AgentInstructions(StrictModel):
    may_abstain: Literal[True] = True
    must_reference_evidence: Literal[True] = True
    do_not_assume_missing_facts: Literal[True] = True


class AgentView(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    task_id: Identifier
    agent_id: Identifier
    question: str = Field(min_length=1)
    options: tuple[str, ...] = Field(min_length=3)
    visible_evidence: tuple[VisibleEvidence, ...]
    instructions: AgentInstructions = AgentInstructions()


class GenerationProvenance(StrictModel):
    source_kind: Literal["independent_programmatic"] = "independent_programmatic"
    generator_id: Literal["cascade_deterministic_benchmark"] = "cascade_deterministic_benchmark"
    generator_version: Literal["1.0"] = "1.0"
    blueprint_id: Identifier
    template_id: Identifier
    seed: int
    dataset_split: Literal["development"] = "development"
    external_content_dependencies: tuple[()] = ()


class TaskArtifact(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    task_definition: TaskDefinition
    message_variant_group: MessageVariantGroup
    agent_views: tuple[AgentView, ...] = Field(min_length=2)
    generation_provenance: GenerationProvenance | None = None

    @model_validator(mode="after")
    def validate_links(self) -> "TaskArtifact":
        task = self.task_definition
        group = self.message_variant_group
        if group.task_id != task.task_id or group.variant_group_id != task.variant_group_id:
            raise ValueError("artifact task and variant group links do not match")
        if any(view.task_id != task.task_id for view in self.agent_views):
            raise ValueError("agent views must link to their parent task")
        if len({view.agent_id for view in self.agent_views}) != len(self.agent_views):
            raise ValueError("agent IDs must be unique")
        known = {fact.id for fact in task.facts}
        if not set(group.source_fact_ids).issubset(known):
            raise ValueError("variant group refers to unknown facts")
        if not set(group.decisive_qualifier_fact_ids).issubset(known):
            raise ValueError("variant group has unknown qualifier facts")
        if not set(group.intended_inference_overrides).issubset(known):
            raise ValueError("intended inference overrides unknown facts")
        for variant in group.variants:
            for claim in variant.truth_constraints:
                if claim.left_fact_id not in known or (
                    claim.right_fact_id is not None and claim.right_fact_id not in known
                ):
                    raise ValueError("variant truth constraint refers to unknown facts")
        return self


def jsonable(model: BaseModel) -> dict[str, Any]:
    """Return a JSON-compatible object with enums serialized to values."""

    return model.model_dump(mode="json")

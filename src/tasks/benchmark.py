"""Independent deterministic generator for the 40-task CASCADE benchmark."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .allocator import allocate_fact_ids, build_agent_views
from .export import write_jsonl
from .schemas import (
    AmbiguityCategory,
    AtomicFact,
    ComparisonOperator,
    Constraint,
    DecisionRule,
    GenerationProvenance,
    GroundTruth,
    MessageVariant,
    MessageVariantGroup,
    OmissionAmbiguityContract,
    ReferentialAmbiguityContract,
    ReviewStatus,
    ScopeAmbiguityContract,
    SemanticReview,
    TaskArtifact,
    TaskDefinition,
    TemporalAmbiguityContract,
    TruthStatus,
    VariantType,
    jsonable,
)
from .solver import solve_task

DEFAULT_SEED = 42


@dataclass(frozen=True)
class ReferentialBlueprint:
    blueprint_id: str
    domain: str
    target_id: str
    target_name: str
    other_id: str
    other_name: str
    shared_surface: str
    question: str
    positive_predicate: str
    negative_predicate: str
    answer_yes: bool
    template_id: str = "referential_v1"


@dataclass(frozen=True)
class OmissionBlueprint:
    blueprint_id: str
    domain: str
    entity_id: str
    entity_name: str
    question: str
    screen_clause: str
    record_clause: str
    qualifier_positive: str
    qualifier_negative: str
    issue_noun: str
    answer_yes: bool
    resolved_issue_context: str | None = None
    incomplete_issue_statement: str | None = None
    template_id: str = "omission_v1"


@dataclass(frozen=True)
class ScopeBlueprint:
    blueprint_id: str
    domain: str
    subject_id: str
    subject_name: str
    question: str
    item_plural: str


@dataclass(frozen=True)
class TemporalBlueprint:
    blueprint_id: str
    domain: str
    subject_id: str
    subject_name: str
    question: str
    positive_predicate: str
    negative_predicate: str
    answer_yes: bool


REFERENTIAL_BLUEPRINTS = (
    ReferentialBlueprint("ref_grant", "grant_eligibility", "northstar_analytics", "Northstar Analytics", "northstar_robotics", "Northstar Robotics", "Northstar", "Should Northstar Analytics receive the Horizon grant?", "completed the required audit", "did not complete the required audit", False),
    ReferentialBlueprint("ref_incident", "incident_closure", "atlas_gateway", "Atlas Gateway", "atlas_archive", "Atlas Archive", "Atlas", "May the Atlas Gateway incident be closed?", "was restored", "was not restored", True),
    ReferentialBlueprint("ref_permit_v2", "permit_compliance", "cedar_center_north", "Cedar Center North", "cedar_center_south", "Cedar Center South", "Cedar Center", "Is Cedar Center North compliant with the operating permit rule?", "holds a valid permit", "does not hold a valid permit", False, "referential_shared_shorthand_v2"),
    ReferentialBlueprint("ref_research", "research_selection", "nova_coastal", "Nova Coastal", "nova_climate", "Nova Climate", "Nova", "Should Nova Coastal be selected for the research program?", "uses an approved public dataset", "does not use an approved public dataset", True),
    ReferentialBlueprint("ref_satellite", "satellite_clearance", "orion_relay", "Orion Relay", "orion_archive", "Orion Archive", "Orion", "Should Orion Relay receive transmission clearance?", "passed the interference check", "failed the interference check", False),
    ReferentialBlueprint("ref_warehouse", "warehouse_dispatch", "meridian_east", "Meridian East", "meridian_west", "Meridian West", "Meridian", "Should Meridian East dispatch the emergency shipment?", "has a certified loading crew", "does not have a certified loading crew", True),
    ReferentialBlueprint("ref_trial", "trial_evaluation", "lumen_alpha", "Lumen Alpha", "lumen_beta", "Lumen Beta", "Lumen", "Should Lumen Alpha advance to the next trial stage?", "met the primary endpoint", "did not meet the primary endpoint", False),
    ReferentialBlueprint("ref_school", "school_procurement", "pine_ridge_school", "Pine Ridge School", "pine_ridge_district", "Pine Ridge District", "Pine Ridge", "Should Pine Ridge School receive the equipment order?", "submitted the safety certificate", "did not submit the safety certificate", True),
    ReferentialBlueprint("ref_marine", "marine_inspection", "harbor_one", "Harbor One", "harbor_two", "Harbor Two", "Harbor", "Should Harbor One receive sailing clearance?", "passed the hull inspection", "failed the hull inspection", False),
    ReferentialBlueprint("ref_datacenter", "datacenter_failover", "aurora_core", "Aurora Core", "aurora_backup", "Aurora Backup", "Aurora", "Should traffic remain on Aurora Core?", "passed the stability check", "failed the stability check", True),
    ReferentialBlueprint("ref_rail", "rail_maintenance", "summit_line", "Summit Line", "summit_yard", "Summit Yard", "Summit", "Should Summit Line reopen for service?", "completed the brake inspection", "did not complete the brake inspection", False),
    ReferentialBlueprint("ref_claim", "insurance_claims", "beacon_home", "Beacon Home", "beacon_auto", "Beacon Auto", "Beacon", "Should the Beacon Home claim be paid?", "has active incident coverage", "does not have active incident coverage", True),
    ReferentialBlueprint("ref_energy", "energy_projects", "solace_solar", "Solace Solar", "solace_storage", "Solace Storage", "Solace", "Should Solace Solar receive grid approval?", "passed the grid-impact review", "failed the grid-impact review", False),
    ReferentialBlueprint("ref_airport", "airport_gates", "crescent_gate_a", "Crescent Gate A", "crescent_gate_b", "Crescent Gate B", "Crescent Gate", "Should Crescent Gate A open for boarding?", "completed the security sweep", "did not complete the security sweep", True),
    ReferentialBlueprint("ref_food", "food_safety", "meadow_plant", "Meadow Plant", "meadow_depot", "Meadow Depot", "Meadow", "Should Meadow Plant release the production batch?", "passed the contamination screen", "failed the contamination screen", False),
)


OMISSION_BLUEPRINTS = (
    OmissionBlueprint("omit_vendor", "vendor_approval", "ember_supply", "Ember Supply", "Should Ember Supply be approved as a vendor?", "identity screening passed", "the ownership record is complete", "the sanctions check is clear", "the sanctions check is not clear", "a sanctions-review alert", False),
    OmissionBlueprint("omit_medication_v2", "medication_dispensing", "caldra_rx", "Caldra prescription", "Should the Caldra prescription be dispensed?", "the prescription is valid", "the stock record is complete", "the allergy check is clear", "the allergy check is not clear", "an allergy-review alert", True, "When recorded, the allergy-review alert placed the Caldra prescription on a dispensing hold pending review.", "The allergy-review alert placed the Caldra prescription on a dispensing hold pending review.", "omission_resolved_context_v2"),
    OmissionBlueprint("omit_loan", "loan_underwriting", "juniper_loan", "Juniper loan", "Should the Juniper loan be approved?", "identity verification passed", "the income record is complete", "the collateral check is sufficient", "the collateral check is insufficient", "a collateral-review issue", False),
    OmissionBlueprint("omit_access", "access_control", "keystone_access", "Keystone access request", "Should the Keystone access request be granted?", "password verification passed", "the account record is complete", "multi-factor verification is complete", "multi-factor verification is incomplete", "a multi-factor alert", True),
    OmissionBlueprint("omit_bridge", "bridge_operations", "silver_bridge", "Silver Bridge", "Should Silver Bridge open to traffic?", "the structural screen passed", "the inspection record is complete", "the wind check is within limits", "the wind check exceeds limits", "a wind-review alert", False),
    OmissionBlueprint("omit_claim_v2", "claim_payment", "river_claim", "River claim", "Should the River claim be paid?", "policy verification passed", "the filing record is complete", "the incident is covered", "the incident is not covered", "a coverage-review issue", True, "The coverage-review issue was opened because the incident date initially appeared outside the policy period.", "River claim was flagged because the incident date initially appeared outside the policy period.", "omission_resolved_context_v2"),
    OmissionBlueprint("omit_release", "software_release", "vertex_release", "Vertex release", "Should the Vertex release enter production?", "the build screen passed", "the test record is complete", "the rollback check is ready", "the rollback check is not ready", "a rollback-readiness alert", False),
    OmissionBlueprint("omit_cargo", "cargo_clearance", "tide_cargo", "Tide cargo", "Should Tide cargo receive loading clearance?", "the manifest screen passed", "the customs record is complete", "the weight check is within limits", "the weight check exceeds limits", "a weight-review alert", True),
    OmissionBlueprint("omit_hiring", "hiring_decision", "alder_candidate", "Alder candidate", "Should the Alder candidate receive an offer?", "identity screening passed", "the interview record is complete", "the required certification is valid", "the required certification is invalid", "a certification-review issue", False),
    OmissionBlueprint("omit_water", "water_quality", "delta_reservoir", "Delta Reservoir", "Should Delta Reservoir return to service?", "the intake screen passed", "the sample record is complete", "the contaminant check is within limits", "the contaminant check exceeds limits", "a contaminant-review alert", True),
    OmissionBlueprint("omit_drone", "drone_flight", "kestrel_drone", "Kestrel drone", "Should the Kestrel drone launch?", "the route screen passed", "the flight record is complete", "the battery check is sufficient", "the battery check is insufficient", "a battery-review issue", False),
    OmissionBlueprint("omit_invoice", "invoice_payment", "opal_invoice", "Opal invoice", "Should the Opal invoice be paid?", "the vendor screen passed", "the receipt record is complete", "the authorization check is complete", "the authorization check is incomplete", "an authorization-review alert", True),
    OmissionBlueprint("omit_lab", "laboratory_access", "quartz_lab", "Quartz laboratory request", "Should the Quartz laboratory request be approved?", "identity screening passed", "the training record is complete", "the hazard briefing is current", "the hazard briefing is expired", "a hazard-briefing issue", False),
    OmissionBlueprint("omit_route_v2", "route_approval", "willow_route", "Willow route", "Should the Willow route be approved for the convoy?", "the map screen passed", "the vehicle record is complete", "the clearance check is sufficient", "the clearance check is insufficient", "an insufficient-clearance alert", True, "The earlier clearance alert concerned the same Willow route and convoy configuration named in the decision question.", "The clearance log contains an insufficient-clearance alert for the same Willow route and convoy configuration.", "omission_resolved_context_v2"),
    OmissionBlueprint("omit_archive", "records_retention", "mosaic_archive", "Mosaic archive transfer", "Should the Mosaic archive transfer proceed?", "the inventory screen passed", "the custody record is complete", "the retention check is satisfied", "the retention check is not satisfied", "a retention-review issue", False),
)


SCOPE_BLUEPRINTS = (
    ScopeBlueprint("scope_batch", "quality_control", "batch_elm", "Batch Elm", "Should Batch Elm be released?", "tests"),
    ScopeBlueprint("scope_project", "project_completion", "project_iris", "Project Iris", "Should Project Iris be marked complete?", "tasks"),
    ScopeBlueprint("scope_audit", "compliance_audit", "audit_lake", "Lake audit", "Should the Lake audit be accepted?", "checks"),
    ScopeBlueprint("scope_trial", "trial_readiness", "trial_prairie", "Prairie trial", "Should the Prairie trial advance?", "assessments"),
    ScopeBlueprint("scope_fleet", "fleet_certification", "fleet_maple", "Maple fleet", "Should the Maple fleet be certified?", "inspections"),
)


TEMPORAL_BLUEPRINTS = (
    TemporalBlueprint("temp_certificate", "certificate_validity", "cobalt_certificate", "Cobalt certificate", "Is the Cobalt certificate valid at the decision time?", "was valid", "was not valid", False),
    TemporalBlueprint("temp_service", "service_recovery", "drift_service", "Drift service", "May the Drift service incident close at the decision time?", "was restored", "was not restored", True),
    TemporalBlueprint("temp_permit", "permit_window", "fern_permit", "Fern permit", "Is the Fern permit active at the decision time?", "was active", "was not active", False),
    TemporalBlueprint("temp_inventory", "inventory_release", "glacier_inventory", "Glacier inventory", "May Glacier inventory be released at the decision time?", "was cleared", "was not cleared", True),
    TemporalBlueprint("temp_patch", "patch_readiness", "horizon_patch", "Horizon patch", "Should the Horizon patch deploy at the decision time?", "was approved", "was not approved", False),
)


def _fact(fid: str, entity_id: str, subject: str, predicate: str, value: str | int | float | bool, text: str) -> AtomicFact:
    return AtomicFact(id=fid, entity_id=entity_id, subject=subject, predicate=predicate, value=value, evidence_text=text)


def _literal(cid: str, fid: str, expected: str | int | float | bool, description: str) -> Constraint:
    return Constraint(id=cid, left_fact_id=fid, operator=ComparisonOperator.EQ, expected_value=expected, description=description)


def _compare(cid: str, left: str, op: ComparisonOperator, right: str, description: str) -> Constraint:
    return Constraint(id=cid, left_fact_id=left, operator=op, right_fact_id=right, description=description)


def _stable_id(prefix: str, seed: int, ordinal: int, blueprint_id: str) -> str:
    digest = hashlib.sha256(f"{seed}:{ordinal}:{blueprint_id}".encode()).hexdigest()[:14]
    return f"{prefix}_{digest}"


def _safe_allocation(facts: tuple[AtomicFact, ...], required: tuple[str, ...], seed: int):
    for offset in range(200):
        allocation = allocate_fact_ids([fact.id for fact in facts], agent_count=5, seed=seed + offset)
        if all(not set(required).issubset(ids) for ids in allocation.private_fact_ids.values()):
            return allocation
    raise ValueError("could not construct hidden-profile allocation")


def _truth(cid: str, fid: str, value: str | int | float | bool) -> Constraint:
    return _literal(cid, fid, value, "Controlled-template truth condition.")


def _build_task(
    *,
    ordinal: int,
    seed: int,
    blueprint_id: str,
    template_id: str,
    domain: str,
    entity_ids: tuple[str, ...],
    question: str,
    facts: tuple[AtomicFact, ...],
    constraints: tuple[Constraint, ...],
    decisive: tuple[str, ...],
    category: AmbiguityCategory,
    contract,
    complete_text: str,
    ambiguous_text: str,
    omission_text: str,
    group_sources: tuple[str, ...],
    ambiguous_sources: tuple[str, ...],
    omission_sources: tuple[str, ...],
    omitted: tuple[str, ...],
    ambiguous_truth: tuple[Constraint, ...],
    omission_truth: tuple[Constraint, ...],
    intended_text: str,
    intended_answer: str,
    overrides: dict[str, str | int | float | bool],
) -> TaskArtifact:
    task_id = _stable_id("MB", seed, ordinal, blueprint_id)
    group_id = _stable_id("VG", seed, ordinal, blueprint_id)
    required_set = {c.left_fact_id for c in constraints}
    required_set.update(c.right_fact_id for c in constraints if c.right_fact_id)
    required = tuple(f.id for f in facts if f.id in required_set)
    allocation_seed = seed ^ int(hashlib.sha256(blueprint_id.encode()).hexdigest()[:16], 16)
    allocation = _safe_allocation(facts, required, allocation_seed)
    rule = DecisionRule(constraints=constraints, satisfied_answer="YES", violated_answer="NO")
    provisional = TaskDefinition(
        task_id=task_id,
        variant_group_id=group_id,
        domain=domain,
        entity_ids=entity_ids,
        question=question,
        options=("YES", "NO", "UNKNOWN"),
        facts=facts,
        decision_rule=rule,
        ground_truth=GroundTruth(answer="YES", required_fact_ids=required, decisive_fact_ids=decisive, explanation="Pending solver evaluation."),
        allocation=allocation,
        generation_seed=seed,
    )
    answer = solve_task(provisional)
    task = provisional.model_copy(update={"ground_truth": GroundTruth(answer=answer, required_fact_ids=required, decisive_fact_ids=decisive, explanation=f"The deterministic all-constraints solver returns {answer}.")})
    if category is AmbiguityCategory.REFERENTIAL:
        defensible_interpretation = (
            f"The surface form '{contract.surface_form}' denotes entity "
            f"{contract.defensible_entity_id}, not decision target {contract.misleading_entity_id}."
        )
    elif category is AmbiguityCategory.SELECTIVE_OMISSION:
        defensible_interpretation = (
            "The statement asserts only its cited facts and makes no claim about omitted "
            f"qualifier facts {', '.join(contract.omitted_qualifier_fact_ids)}."
        )
    elif category is AmbiguityCategory.SCOPE:
        defensible_interpretation = (
            "Use wide-scope negation: it is not the case that all items in the declared "
            "scope passed; this does not mean every item failed."
        )
    else:
        defensible_interpretation = (
            "The unanchored status refers to the earlier observation identified by fact "
            f"{contract.defensible_time_fact_id}, not the decision time in {contract.misleading_time_fact_id}."
        )
    values_by_id = {fact.id: fact.value for fact in facts}
    complete_truth = tuple(
        _truth(f"TC{index:03d}", fact_id, values_by_id[fact_id])
        for index, fact_id in enumerate(group_sources, start=1)
    )
    variants = (
        MessageVariant(id="V001", type=VariantType.COMPLETE, text=complete_text, source_fact_ids=group_sources, truth_status=TruthStatus.ENTAILED, ambiguity_type="none", truth_constraints=complete_truth, recommended_answer=answer),
        MessageVariant(id="V002", type=VariantType.AMBIGUOUS, text=ambiguous_text, source_fact_ids=ambiguous_sources, truth_status=TruthStatus.ENTAILED, ambiguity_type=category.value, omitted_fact_ids=omitted, defensible_interpretation=defensible_interpretation, misleading_interpretation=intended_text, truth_constraints=ambiguous_truth),
        MessageVariant(id="V003", type=VariantType.SELECTIVE_OMISSION, text=omission_text, source_fact_ids=omission_sources, truth_status=TruthStatus.ENTAILED, ambiguity_type="context_omission", omitted_fact_ids=omitted, misleading_interpretation=intended_text, truth_constraints=omission_truth),
    )
    group = MessageVariantGroup(
        variant_group_id=group_id,
        task_id=task_id,
        ambiguity_category=category,
        ambiguity_contract=contract,
        source_fact_ids=group_sources,
        intended_misleading_inference=intended_text,
        intended_incorrect_answer=intended_answer,
        intended_inference_overrides=overrides,
        decisive_qualifier_fact_ids=decisive,
        variants=variants,
        semantic_review=SemanticReview(status=ReviewStatus.NEEDS_REVIEW, notes="Mechanical checks passed by construction; natural-language truthfulness, ambiguity strength, and misleadingness require human review."),
    )
    return TaskArtifact(
        task_definition=task,
        message_variant_group=group,
        agent_views=build_agent_views(task),
        generation_provenance=GenerationProvenance(blueprint_id=blueprint_id, template_id=template_id, seed=seed),
    )


def _referential(bp: ReferentialBlueprint, ordinal: int, seed: int) -> TaskArtifact:
    target_good = bp.answer_yes
    other_good = not target_good
    facts = (
        _fact("F001", bp.target_id, bp.target_name, "is_decision_target", True, f"{bp.target_name} is the entity named in the decision question."),
        _fact("F002", bp.target_id, bp.target_name, "baseline_check_passed", True, f"{bp.target_name} passed the baseline check."),
        _fact("F003", bp.target_id, bp.target_name, "record_complete", True, f"{bp.target_name}'s required record is complete."),
        _fact("F004", bp.target_id, bp.target_name, "decisive_qualifier_met", target_good, f"{bp.target_name} {bp.positive_predicate if target_good else bp.negative_predicate}."),
        _fact("F005", bp.other_id, bp.other_name, "decisive_qualifier_met", other_good, f"{bp.other_name} {bp.positive_predicate if other_good else bp.negative_predicate}."),
        _fact("F006", "policy", "Decision policy", "baseline_required", True, "The decision policy requires the baseline check to pass."),
        _fact("F007", "policy", "Decision policy", "complete_record_required", True, "The decision policy requires a complete record and the decisive qualifier."),
    )
    constraints = (_literal("C001", "F002", True, "Target passed baseline."), _literal("C002", "F003", True, "Target record is complete."), _literal("C003", "F004", True, "Target meets decisive qualifier."))
    answer = "YES" if target_good else "NO"
    wrong = "NO" if target_good else "YES"
    other_clause = bp.positive_predicate if other_good else bp.negative_predicate
    target_clause = bp.positive_predicate if target_good else bp.negative_predicate
    return _build_task(
        ordinal=ordinal, seed=seed, blueprint_id=bp.blueprint_id, template_id=bp.template_id, domain=bp.domain,
        entity_ids=(bp.target_id, bp.other_id, "policy"), question=bp.question, facts=facts, constraints=constraints, decisive=("F004",), category=AmbiguityCategory.REFERENTIAL,
        contract=ReferentialAmbiguityContract(surface_form=bp.shared_surface, defensible_entity_id=bp.other_id, misleading_entity_id=bp.target_id),
        complete_text=f"{bp.target_name} passed the baseline and record checks and {target_clause}; {bp.other_name} {other_clause}. Therefore the answer is {answer}.",
        ambiguous_text=f"{bp.shared_surface} {other_clause}.", omission_text=f"{bp.other_name} {other_clause}.",
        group_sources=("F002", "F003", "F004", "F005"), ambiguous_sources=("F005",), omission_sources=("F005",), omitted=("F004",),
        ambiguous_truth=(_truth("T001", "F005", other_good),), omission_truth=(_truth("T002", "F005", other_good),),
        intended_text=f"Interpret {bp.shared_surface} as {bp.target_name}, infer that its decisive qualifier is {other_good}, and answer {wrong}.", intended_answer=wrong, overrides={"F004": other_good},
    )


def _omission(bp: OmissionBlueprint, ordinal: int, seed: int) -> TaskArtifact:
    if bp.answer_yes:
        facts = (
            _fact("F001", bp.entity_id, bp.entity_name, "initial_screen_passed", True, f"For {bp.entity_name}, {bp.screen_clause}."),
            _fact("F002", bp.entity_id, bp.entity_name, "record_complete", True, f"For {bp.entity_name}, {bp.record_clause}."),
            _fact("F003", bp.entity_id, bp.entity_name, "issue_detected", True, f"For {bp.entity_name}, {bp.issue_noun} was recorded."),
            _fact("F004", bp.entity_id, bp.entity_name, "decisive_qualifier_met", True, f"For {bp.entity_name}, {bp.qualifier_positive}."),
            _fact("F005", "policy", "Decision policy", "resolution_required", True, "The policy permits approval only when any recorded issue is resolved."),
            _fact("F006", bp.entity_id, bp.entity_name, "review_logged", True, f"The review for {bp.entity_name} was logged."),
        )
        if bp.resolved_issue_context:
            facts += (
                _fact(
                    "F007",
                    bp.entity_id,
                    bp.entity_name,
                    "issue_context_recorded",
                    True,
                    bp.resolved_issue_context,
                ),
            )
        constraints = (_literal("C001", "F001", True, "Initial screen passed."), _literal("C002", "F002", True, "Record complete."), _literal("C003", "F004", True, "Decisive qualifier met."))
        context = f" {bp.resolved_issue_context}" if bp.resolved_issue_context else ""
        complete = f"For {bp.entity_name}, {bp.screen_clause}, {bp.record_clause}, and {bp.issue_noun} was recorded.{context} However, {bp.qualifier_positive}. Therefore the answer is YES."
        incomplete = bp.incomplete_issue_statement
        ambiguous = incomplete or f"The review for {bp.entity_name} found {bp.issue_noun}."
        omission = incomplete or f"For {bp.entity_name}, {bp.issue_noun} was recorded."
        sources = ("F001", "F002", "F003", "F004") + (("F007",) if bp.resolved_issue_context else ())
        truth = (_truth("T001", "F003", True),) + (
            (_truth("T002", "F007", True),) if bp.resolved_issue_context else ()
        )
        incomplete_sources = ("F003",) + (("F007",) if bp.resolved_issue_context else ())
        wrong, override = "NO", False
    else:
        facts = (
            _fact("F001", bp.entity_id, bp.entity_name, "initial_screen_passed", True, f"For {bp.entity_name}, {bp.screen_clause}."),
            _fact("F002", bp.entity_id, bp.entity_name, "record_complete", True, f"For {bp.entity_name}, {bp.record_clause}."),
            _fact("F003", bp.entity_id, bp.entity_name, "decisive_qualifier_met", False, f"For {bp.entity_name}, {bp.qualifier_negative}."),
            _fact("F004", "policy", "Decision policy", "screen_required", True, "The policy requires the initial screen to pass."),
            _fact("F005", "policy", "Decision policy", "record_required", True, "The policy requires a complete record."),
            _fact("F006", "policy", "Decision policy", "qualifier_required", True, "The policy requires the decisive qualifier to be met."),
        )
        constraints = (_literal("C001", "F001", True, "Initial screen passed."), _literal("C002", "F002", True, "Record complete."), _literal("C003", "F003", True, "Decisive qualifier met."))
        complete = f"For {bp.entity_name}, {bp.screen_clause} and {bp.record_clause}, but {bp.qualifier_negative}. Therefore the answer is NO."
        ambiguous = f"{bp.entity_name} met the preliminary review checks."
        omission = f"For {bp.entity_name}, {bp.screen_clause} and {bp.record_clause}."
        sources = ("F001", "F002", "F003")
        truth = (_truth("T001", "F001", True), _truth("T002", "F002", True))
        incomplete_sources = ("F001", "F002")
        wrong, override = "YES", True
    return _build_task(
        ordinal=ordinal, seed=seed, blueprint_id=bp.blueprint_id, template_id=bp.template_id, domain=bp.domain,
        entity_ids=(bp.entity_id, "policy"), question=bp.question, facts=facts, constraints=constraints, decisive=(("F004",) if bp.answer_yes else ("F003",)), category=AmbiguityCategory.SELECTIVE_OMISSION,
        contract=OmissionAmbiguityContract(omitted_qualifier_fact_ids=(("F004",) if bp.answer_yes else ("F003",))),
        complete_text=complete, ambiguous_text=ambiguous, omission_text=omission, group_sources=sources,
        ambiguous_sources=incomplete_sources, omission_sources=incomplete_sources,
        omitted=(("F004",) if bp.answer_yes else ("F003",)), ambiguous_truth=truth, omission_truth=truth,
        intended_text=f"Treat the omitted decisive qualifier as {override} and answer {wrong}.", intended_answer=wrong, overrides={("F004" if bp.answer_yes else "F003"): override},
    )


def _scope(bp: ScopeBlueprint, ordinal: int, seed: int) -> TaskArtifact:
    m1, m2, optional = f"{bp.subject_id}_mandatory_1", f"{bp.subject_id}_mandatory_2", f"{bp.subject_id}_optional"
    facts = (
        _fact("F001", m1, f"{bp.subject_name} mandatory {bp.item_plural[:-1]} A", "passed", True, f"Mandatory {bp.item_plural[:-1]} A for {bp.subject_name} passed."),
        _fact("F002", m2, f"{bp.subject_name} mandatory {bp.item_plural[:-1]} B", "passed", True, f"Mandatory {bp.item_plural[:-1]} B for {bp.subject_name} passed."),
        _fact("F003", optional, f"{bp.subject_name} optional {bp.item_plural[:-1]}", "passed", False, f"The optional {bp.item_plural[:-1]} for {bp.subject_name} did not pass."),
        _fact("F004", bp.subject_id, bp.subject_name, "record_complete", True, f"The record for {bp.subject_name} is complete."),
        _fact("F005", "policy", "Decision policy", "mandatory_items_control", True, f"The decision depends on mandatory {bp.item_plural}, not optional ones."),
        _fact("F006", "policy", "Decision policy", "complete_record_required", True, "The decision policy requires a complete record."),
    )
    constraints = (_literal("C001", "F001", True, "Mandatory item A passed."), _literal("C002", "F002", True, "Mandatory item B passed."), _literal("C003", "F004", True, "Record complete."))
    return _build_task(
        ordinal=ordinal, seed=seed, blueprint_id=bp.blueprint_id, template_id="scope_v1", domain=bp.domain,
        entity_ids=(bp.subject_id, m1, m2, optional, "policy"), question=bp.question, facts=facts, constraints=constraints, decisive=("F001", "F002"), category=AmbiguityCategory.SCOPE,
        contract=ScopeAmbiguityContract(quantifier="all", defensible_scope_entity_ids=(m1, m2, optional), misleading_scope_entity_ids=(m1, m2, optional)),
        complete_text=f"Both mandatory {bp.item_plural} for {bp.subject_name} passed; one optional {bp.item_plural[:-1]} did not pass, and the record is complete. Therefore the answer is YES.",
        ambiguous_text=f"All {bp.item_plural} did not pass.", omission_text=f"One {bp.item_plural[:-1]} for {bp.subject_name} did not pass.",
        group_sources=("F001", "F002", "F003", "F004", "F005"), ambiguous_sources=("F003",), omission_sources=("F003",), omitted=("F001", "F002", "F005"),
        ambiguous_truth=(_truth("T001", "F003", False),), omission_truth=(_truth("T002", "F003", False),),
        intended_text=f"Read 'all {bp.item_plural} did not pass' as every mandatory item failing and answer NO, rather than as not all items passing.", intended_answer="NO", overrides={"F001": False, "F002": False},
    )


def _temporal(bp: TemporalBlueprint, ordinal: int, seed: int) -> TaskArtifact:
    current = bp.answer_yes
    historical = not current
    decision_minute = 600 + ordinal
    deadline_minute = 900 + ordinal
    historical_minute = 300 + ordinal
    facts = (
        _fact("F001", bp.subject_id, bp.subject_name, "decision_time_minute", decision_minute, f"The decision time for {bp.subject_name} is minute {decision_minute}."),
        _fact("F002", "policy", "Decision policy", "deadline_minute", deadline_minute, f"The applicable deadline is minute {deadline_minute}."),
        _fact("F003", bp.subject_id, bp.subject_name, "status_at_decision_time", current, f"At the decision time, {bp.subject_name} {bp.positive_predicate if current else bp.negative_predicate}."),
        _fact("F004", bp.subject_id, bp.subject_name, "historical_time_minute", historical_minute, f"The earlier observation occurred at minute {historical_minute}."),
        _fact("F005", bp.subject_id, bp.subject_name, "status_at_historical_time", historical, f"At the earlier observation, {bp.subject_name} {bp.positive_predicate if historical else bp.negative_predicate}."),
        _fact("F006", bp.subject_id, bp.subject_name, "record_complete", True, f"The time-stamped record for {bp.subject_name} is complete."),
        _fact("F007", "policy", "Decision policy", "current_status_controls", True, "The status at the decision time controls the decision."),
    )
    constraints = (_compare("C001", "F001", ComparisonOperator.LE, "F002", "Decision occurs by the deadline."), _literal("C002", "F003", True, "Status is positive at decision time."), _literal("C003", "F006", True, "Time-stamped record complete."))
    answer, wrong = ("YES", "NO") if current else ("NO", "YES")
    historical_clause = bp.positive_predicate if historical else bp.negative_predicate
    current_clause = bp.positive_predicate if current else bp.negative_predicate
    return _build_task(
        ordinal=ordinal, seed=seed, blueprint_id=bp.blueprint_id, template_id="temporal_v1", domain=bp.domain,
        entity_ids=(bp.subject_id, "policy"), question=bp.question, facts=facts, constraints=constraints, decisive=("F003",), category=AmbiguityCategory.TEMPORAL,
        contract=TemporalAmbiguityContract(time_unit="minute", defensible_time_fact_id="F004", misleading_time_fact_id="F001"),
        complete_text=f"At minute {decision_minute}, before the minute-{deadline_minute} deadline, {bp.subject_name} {current_clause}; earlier at minute {historical_minute}, it {historical_clause}. The record is complete. Therefore the answer is {answer}.",
        ambiguous_text=f"{bp.subject_name} {historical_clause}.", omission_text=f"At the earlier observation, {bp.subject_name} {historical_clause}.",
        group_sources=("F001", "F002", "F003", "F004", "F005", "F006", "F007"), ambiguous_sources=("F004", "F005"), omission_sources=("F004", "F005"), omitted=("F001", "F003", "F007"),
        ambiguous_truth=(_truth("T001", "F005", historical),), omission_truth=(_truth("T002", "F005", historical),),
        intended_text=f"Apply the earlier status to the decision time and answer {wrong}.", intended_answer=wrong, overrides={"F003": historical},
    )


def generate_benchmark(*, seed: int = DEFAULT_SEED) -> list[TaskArtifact]:
    artifacts: list[TaskArtifact] = []
    ordinal = 1
    for blueprint in REFERENTIAL_BLUEPRINTS:
        artifacts.append(_referential(blueprint, ordinal, seed)); ordinal += 1
    for blueprint in OMISSION_BLUEPRINTS:
        artifacts.append(_omission(blueprint, ordinal, seed)); ordinal += 1
    for blueprint in SCOPE_BLUEPRINTS:
        artifacts.append(_scope(blueprint, ordinal, seed)); ordinal += 1
    for blueprint in TEMPORAL_BLUEPRINTS:
        artifacts.append(_temporal(blueprint, ordinal, seed)); ordinal += 1
    return artifacts


def export_agent_views(artifacts: list[TaskArtifact], output: str | Path) -> int:
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for artifact in artifacts:
            for view in artifact.agent_views:
                handle.write(json.dumps(jsonable(view), sort_keys=True) + "\n"); count += 1
    return count


def export_review_queue(
    artifacts: list[TaskArtifact], output: str | Path, *, mechanical_status: str
) -> int:
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["task_id", "domain", "ambiguity_category", "solver_answer", "mechanical_validation", "truthfulness_review", "misleadingness_review", "ambiguity_strength_review", "evidence_sufficiency_review", "reviewer", "review_notes"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for artifact in artifacts:
            task, group = artifact.task_definition, artifact.message_variant_group
            writer.writerow({"task_id": task.task_id, "domain": task.domain, "ambiguity_category": group.ambiguity_category.value, "solver_answer": task.ground_truth.answer, "mechanical_validation": mechanical_status, "truthfulness_review": "pending", "misleadingness_review": "pending", "ambiguity_strength_review": "pending", "evidence_sufficiency_review": "pending", "reviewer": "", "review_notes": ""})
    return len(artifacts)


def main() -> int:
    from .benchmark_validators import validate_benchmark, write_validation_report

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out-dir", default="data/benchmark")
    args = parser.parse_args()
    out = Path(args.out_dir)
    artifacts = generate_benchmark(seed=args.seed)
    report = validate_benchmark(artifacts, expected_seed=args.seed)
    if report["failed_checks"]:
        raise SystemExit(f"benchmark validation failed: {report['failed_checks']} checks")
    write_jsonl(artifacts, out / "canonical_tasks.jsonl")
    export_agent_views(artifacts, out / "agent_views.jsonl")
    export_review_queue(artifacts, out / "semantic_review.csv", mechanical_status="passed")
    write_validation_report(report, out / "validation_report.json")
    print(f"tasks={len(artifacts)} agent_views={sum(len(a.agent_views) for a in artifacts)} passed_checks={report['passed_checks']} failed_checks={report['failed_checks']} semantic_reviews_pending={len(artifacts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

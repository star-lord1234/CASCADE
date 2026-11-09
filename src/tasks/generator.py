"""Seeded generator for the five hand-reviewable CASCADE Phase 1 examples."""

from __future__ import annotations

import argparse
import hashlib
import random
from collections.abc import Callable

from .allocator import allocate_fact_ids, build_agent_views
from .ambiguity import VariantPlan, build_variant_group
from .export import write_jsonl
from .schemas import (
    AtomicFact,
    ComparisonOperator,
    Constraint,
    DecisionRule,
    GroundTruth,
    TaskArtifact,
    TaskDefinition,
)
from .solver import solve_task
from .validators import validate_dataset


def _fact(
    fact_id: str, subject: str, predicate: str, value: str | int | float | bool, text: str
) -> AtomicFact:
    return AtomicFact(
        id=fact_id,
        subject=subject,
        predicate=predicate,
        value=value,
        evidence_text=text,
    )


def _literal_constraint(
    constraint_id: str,
    fact_id: str,
    operator: ComparisonOperator,
    expected: str | int | float | bool,
    description: str,
) -> Constraint:
    return Constraint(
        id=constraint_id,
        left_fact_id=fact_id,
        operator=operator,
        expected_value=expected,
        description=description,
    )


def _fact_constraint(
    constraint_id: str,
    left_fact_id: str,
    operator: ComparisonOperator,
    right_fact_id: str,
    description: str,
) -> Constraint:
    return Constraint(
        id=constraint_id,
        left_fact_id=left_fact_id,
        operator=operator,
        right_fact_id=right_fact_id,
        description=description,
    )


def _grant_template() -> dict[str, object]:
    return {
        "key": "grant",
        "domain": "grant_eligibility",
        "question": "Is Northstar Analytics eligible for the Horizon grant?",
        "options": ("ELIGIBLE", "NOT_ELIGIBLE", "UNKNOWN"),
        "facts": (
            _fact("F001", "Horizon grant", "named_applicant", "Northstar Analytics", "Northstar Analytics is the named applicant for the Horizon grant."),
            _fact("F002", "Northstar Analytics", "revenue_million", 18, "Northstar Analytics has annual revenue of 18 million credits."),
            _fact("F003", "Horizon grant", "max_revenue_exclusive_million", 25, "The Horizon grant requires annual revenue below 25 million credits."),
            _fact("F004", "Northstar Analytics", "employee_count", 82, "Northstar Analytics has 82 employees."),
            _fact("F005", "Horizon grant", "max_employees_exclusive", 100, "The Horizon grant requires fewer than 100 employees."),
            _fact("F006", "Northstar Analytics", "audit_completed", False, "Northstar Analytics has not completed the required audit."),
            _fact("F007", "Northstar Robotics", "audit_completed", True, "Northstar Robotics has completed the required audit."),
        ),
        "constraints": (
            _fact_constraint("C001", "F002", ComparisonOperator.LT, "F003", "Applicant revenue is below the exclusive cap."),
            _fact_constraint("C002", "F004", ComparisonOperator.LT, "F005", "Applicant employee count is below the exclusive cap."),
            _literal_constraint("C003", "F006", ComparisonOperator.EQ, True, "Applicant completed the required audit."),
        ),
        "satisfied": "ELIGIBLE",
        "violated": "NOT_ELIGIBLE",
        "explanation": "The named applicant has not completed the required audit.",
        "decisive": ("F006",),
        "variant_plan": VariantPlan(
            source_fact_ids=("F001", "F006", "F007"),
            decisive_qualifier_fact_ids=("F001", "F006"),
            intended_misleading_inference="Northstar Analytics completed the audit, so the applicant is ELIGIBLE.",
            complete_text="Northstar Analytics, the grant applicant, has not completed the required audit; Northstar Robotics has completed it.",
            ambiguous_text="Northstar has completed the required audit.",
            omission_text="Northstar Robotics has completed the required audit.",
            ambiguous_source_fact_ids=("F007",),
            omission_source_fact_ids=("F007",),
            omission_omitted_fact_ids=("F001", "F006"),
            ambiguity_type="referential_ambiguity",
            defensible_interpretation="Northstar refers to Northstar Robotics, for which the statement is true.",
            misleading_interpretation="Northstar refers to the applicant, Northstar Analytics.",
        ),
    }


def _incident_template() -> dict[str, object]:
    return {
        "key": "incident",
        "domain": "incident_classification",
        "question": "May incident IR-27 be closed?",
        "options": ("CLOSE_INCIDENT", "ESCALATE", "UNKNOWN"),
        "facts": (
            _fact("F001", "IR-27", "critical_service", "Atlas Gateway", "Atlas Gateway is the critical service affected by incident IR-27."),
            _fact("F002", "Atlas Gateway", "service_restored", False, "Atlas Gateway has not been restored."),
            _fact("F003", "Atlas Archive", "service_restored", True, "Atlas Archive has been restored."),
            _fact("F004", "IR-27", "exposed_record_count", 0, "No records were exposed in incident IR-27."),
            _fact("F005", "closure policy", "max_exposed_records", 0, "Incident closure requires zero exposed records."),
            _fact("F006", "IR-27", "alert_acknowledged", True, "The IR-27 alert has been acknowledged."),
        ),
        "constraints": (
            _literal_constraint("C001", "F002", ComparisonOperator.EQ, True, "The affected critical service is restored."),
            _fact_constraint("C002", "F004", ComparisonOperator.LE, "F005", "Exposed records do not exceed the closure maximum."),
            _literal_constraint("C003", "F006", ComparisonOperator.EQ, True, "The alert is acknowledged."),
        ),
        "satisfied": "CLOSE_INCIDENT",
        "violated": "ESCALATE",
        "explanation": "The affected critical service, Atlas Gateway, remains unrestored.",
        "decisive": ("F002",),
        "variant_plan": VariantPlan(
            source_fact_ids=("F001", "F002", "F003"),
            decisive_qualifier_fact_ids=("F001", "F002"),
            intended_misleading_inference="The affected Atlas service was restored, so CLOSE_INCIDENT is warranted.",
            complete_text="Atlas Gateway, the critical service in IR-27, has not been restored; Atlas Archive has been restored.",
            ambiguous_text="Atlas has been restored.",
            omission_text="Atlas Archive has been restored.",
            ambiguous_source_fact_ids=("F003",),
            omission_source_fact_ids=("F003",),
            omission_omitted_fact_ids=("F001", "F002"),
            ambiguity_type="referential_ambiguity",
            defensible_interpretation="Atlas refers to Atlas Archive, which has been restored.",
            misleading_interpretation="Atlas refers to the affected critical service, Atlas Gateway.",
        ),
    }


def _trial_template() -> dict[str, object]:
    return {
        "key": "trial",
        "domain": "trial_evaluation",
        "question": "Should trial Lumen-4 receive approval under the stated rule?",
        "options": ("APPROVE", "REJECT", "UNKNOWN"),
        "facts": (
            _fact("F001", "Lumen-4 primary endpoint", "succeeded", False, "Trial Lumen-4 did not meet its primary endpoint."),
            _fact("F002", "Lumen-4 secondary endpoint", "succeeded", True, "Trial Lumen-4 met its secondary endpoint."),
            _fact("F003", "Lumen-4", "severe_adverse_event_count", 0, "Trial Lumen-4 recorded zero severe adverse events."),
            _fact("F004", "approval rule", "max_severe_adverse_events", 0, "Approval permits at most zero severe adverse events."),
            _fact("F005", "approval rule", "required_endpoint", "primary", "The approval rule requires success on the primary endpoint."),
        ),
        "constraints": (
            _literal_constraint("C001", "F001", ComparisonOperator.EQ, True, "The primary endpoint succeeded."),
            _fact_constraint("C002", "F003", ComparisonOperator.LE, "F004", "Severe adverse events do not exceed the permitted maximum."),
        ),
        "satisfied": "APPROVE",
        "violated": "REJECT",
        "explanation": "The primary endpoint required by the rule did not succeed.",
        "decisive": ("F001", "F005"),
        "variant_plan": VariantPlan(
            source_fact_ids=("F001", "F002", "F005"),
            decisive_qualifier_fact_ids=("F001", "F005"),
            intended_misleading_inference="The required primary endpoint succeeded, so the trial should be APPROVED.",
            complete_text="Lumen-4 met its secondary endpoint but did not meet the required primary endpoint.",
            ambiguous_text="Lumen-4 met an endpoint.",
            omission_text="Lumen-4 met its secondary endpoint.",
            ambiguous_source_fact_ids=("F002",),
            omission_source_fact_ids=("F002",),
            omission_omitted_fact_ids=("F001", "F005"),
            ambiguity_type="referential_underspecification",
            defensible_interpretation="An endpoint refers existentially to the secondary endpoint, which succeeded.",
            misleading_interpretation="The unspecified endpoint is taken to be the required primary endpoint.",
        ),
    }


def _permit_template() -> dict[str, object]:
    return {
        "key": "permit",
        "domain": "compliance_eligibility",
        "question": "Is Cedar Works compliant with the operating rule?",
        "options": ("COMPLIANT", "NON_COMPLIANT", "UNKNOWN"),
        "facts": (
            _fact("F001", "operating rule", "named_facility", "Cedar Works", "Cedar Works is the facility being assessed."),
            _fact("F002", "Cedar Works", "permit_status", "valid", "Cedar Works has a valid operating permit."),
            _fact("F003", "Cedar Works Annex", "permit_status", "expired", "Cedar Works Annex has an expired operating permit."),
            _fact("F004", "Cedar Works", "emissions_units", 41, "Cedar Works emits 41 units under the relevant measure."),
            _fact("F005", "operating rule", "max_emissions_units", 50, "The operating rule permits at most 50 emissions units."),
            _fact("F006", "Cedar Works", "filing_complete", True, "Cedar Works completed the required filing."),
        ),
        "constraints": (
            _literal_constraint("C001", "F002", ComparisonOperator.EQ, "valid", "The assessed facility has a valid permit."),
            _fact_constraint("C002", "F004", ComparisonOperator.LE, "F005", "Emissions are within the permitted maximum."),
            _literal_constraint("C003", "F006", ComparisonOperator.EQ, True, "The assessed facility completed its filing."),
        ),
        "satisfied": "COMPLIANT",
        "violated": "NON_COMPLIANT",
        "explanation": "The assessed facility has a valid permit, compliant emissions, and a complete filing.",
        "decisive": ("F001", "F002"),
        "variant_plan": VariantPlan(
            source_fact_ids=("F001", "F002", "F003"),
            decisive_qualifier_fact_ids=("F001", "F002"),
            intended_misleading_inference="The assessed facility's permit expired, so it is NON_COMPLIANT.",
            complete_text="Cedar Works, the assessed facility, has a valid permit; Cedar Works Annex has an expired permit.",
            ambiguous_text="Cedar's permit has expired.",
            omission_text="Cedar Works Annex has an expired permit.",
            ambiguous_source_fact_ids=("F003",),
            omission_source_fact_ids=("F003",),
            omission_omitted_fact_ids=("F001", "F002"),
            ambiguity_type="referential_ambiguity",
            defensible_interpretation="Cedar refers to Cedar Works Annex, whose permit is expired.",
            misleading_interpretation="Cedar refers to the assessed facility, Cedar Works.",
        ),
    }


def _proposal_template() -> dict[str, object]:
    return {
        "key": "proposal",
        "domain": "research_selection",
        "question": "Should proposal Nova Coastal be selected for the program?",
        "options": ("SELECT", "DO_NOT_SELECT", "UNKNOWN"),
        "facts": (
            _fact("F001", "selection program", "named_proposal", "Nova Coastal", "Nova Coastal is the proposal being assessed."),
            _fact("F002", "Nova Coastal dataset", "access_status", "public", "Nova Coastal uses a public dataset."),
            _fact("F003", "Nova Climate dataset", "access_status", "embargoed", "Nova Climate uses an embargoed dataset."),
            _fact("F004", "Nova Coastal", "conflict_declared", False, "Nova Coastal has no declared conflict."),
            _fact("F005", "Nova Coastal", "review_score", 91, "Nova Coastal received a review score of 91."),
            _fact("F006", "selection program", "minimum_review_score", 85, "The program requires a review score of at least 85."),
        ),
        "constraints": (
            _literal_constraint("C001", "F002", ComparisonOperator.EQ, "public", "The assessed proposal uses a public dataset."),
            _literal_constraint("C002", "F004", ComparisonOperator.EQ, False, "The assessed proposal has no declared conflict."),
            _fact_constraint("C003", "F005", ComparisonOperator.GE, "F006", "The review score meets the minimum."),
        ),
        "satisfied": "SELECT",
        "violated": "DO_NOT_SELECT",
        "explanation": "The assessed proposal meets the access, conflict, and score requirements.",
        "decisive": ("F001", "F002"),
        "variant_plan": VariantPlan(
            source_fact_ids=("F001", "F002", "F003"),
            decisive_qualifier_fact_ids=("F001", "F002"),
            intended_misleading_inference="The assessed proposal uses embargoed data, so it should be rejected.",
            complete_text="Nova Coastal, the assessed proposal, uses a public dataset; Nova Climate uses an embargoed dataset.",
            ambiguous_text="Nova's dataset is under embargo.",
            omission_text="Nova Climate uses an embargoed dataset.",
            ambiguous_source_fact_ids=("F003",),
            omission_source_fact_ids=("F003",),
            omission_omitted_fact_ids=("F001", "F002"),
            ambiguity_type="referential_ambiguity",
            defensible_interpretation="Nova refers to Nova Climate, whose dataset is embargoed.",
            misleading_interpretation="Nova refers to the assessed proposal, Nova Coastal.",
        ),
    }


TEMPLATE_BUILDERS: tuple[Callable[[], dict[str, object]], ...] = (
    _grant_template,
    _incident_template,
    _trial_template,
    _permit_template,
    _proposal_template,
)


def _stable_id(prefix: str, *, seed: int, ordinal: int, key: str) -> str:
    digest = hashlib.sha256(f"{seed}:{ordinal}:{key}".encode()).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _build_artifact(spec: dict[str, object], *, seed: int, ordinal: int) -> TaskArtifact:
    key = str(spec["key"])
    task_id = _stable_id("T", seed=seed, ordinal=ordinal, key=key)
    group_id = _stable_id("G", seed=seed, ordinal=ordinal, key=key)
    facts = tuple(spec["facts"])
    constraints = tuple(spec["constraints"])
    required_set: set[str] = set()
    for constraint in constraints:
        required_set.add(constraint.left_fact_id)
        if constraint.right_fact_id:
            required_set.add(constraint.right_fact_id)
    required = tuple(fact.id for fact in facts if fact.id in required_set)
    allocation_seed = int(
        hashlib.sha256(f"allocation:{seed}:{ordinal}:{key}".encode()).hexdigest()[:16], 16
    )
    allocation = allocate_fact_ids(
        [fact.id for fact in facts], agent_count=5, seed=allocation_seed
    )
    rule = DecisionRule(
        constraints=constraints,
        satisfied_answer=str(spec["satisfied"]),
        violated_answer=str(spec["violated"]),
    )
    provisional = TaskDefinition(
        task_id=task_id,
        variant_group_id=group_id,
        domain=str(spec["domain"]),
        question=str(spec["question"]),
        options=tuple(spec["options"]),
        facts=facts,
        decision_rule=rule,
        ground_truth=GroundTruth(
            answer=str(spec["satisfied"]),
            required_fact_ids=required,
            decisive_fact_ids=tuple(spec["decisive"]),
            explanation=str(spec["explanation"]),
        ),
        allocation=allocation,
        generation_seed=seed,
    )
    answer = solve_task(provisional)
    task = provisional.model_copy(
        update={
            "ground_truth": GroundTruth(
                answer=answer,
                required_fact_ids=required,
                decisive_fact_ids=tuple(spec["decisive"]),
                explanation=str(spec["explanation"]),
            )
        }
    )
    group = build_variant_group(
        task_id=task_id,
        variant_group_id=group_id,
        plan=spec["variant_plan"],
    )
    return TaskArtifact(
        task_definition=task,
        message_variant_group=group,
        agent_views=build_agent_views(task),
    )


def generate_artifacts(*, count: int, seed: int) -> list[TaskArtifact]:
    if count < 1:
        raise ValueError("count must be positive")
    if count > len(TEMPLATE_BUILDERS):
        raise ValueError(
            f"this hand-review milestone supports at most {len(TEMPLATE_BUILDERS)} distinct tasks"
        )
    builders = list(TEMPLATE_BUILDERS)
    random.Random(seed).shuffle(builders)
    artifacts = [
        _build_artifact(builder(), seed=seed, ordinal=index)
        for index, builder in enumerate(builders[:count], start=1)
    ]
    issues = validate_dataset(artifacts)
    if issues:
        details = "; ".join(f"{issue.code}: {issue.message}" for issue in issues)
        raise ValueError(f"generated dataset failed structural validation: {details}")
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    artifacts = generate_artifacts(count=args.count, seed=args.seed)
    written = write_jsonl(artifacts, args.out)
    pending = sum(
        artifact.message_variant_group.semantic_review.status.value == "needs_review"
        for artifact in artifacts
    )
    print(
        f"wrote={written} structurally_valid={written} "
        f"semantic_review_pending={pending} path={args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

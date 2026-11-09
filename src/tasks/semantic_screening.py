"""Risk-based semantic screening for the 40-task CASCADE draft benchmark.

Deterministic checks route tasks to low-risk batch review or detailed flagged
review. Optional independent LLM judgments may add flags or agreement metadata,
but can never set human approval or change deterministic ground truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .export import read_jsonl
from .schemas import (
    AmbiguityCategory,
    MessageVariant,
    TaskArtifact,
    VariantType,
)
from .solver import evaluate_constraint, solve_task

SCREENING_VERSION = "1.0"


class JudgeAssessment(BaseModel):
    """Provider-neutral result from one independent semantic screening run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    judge_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    factual_entailment: Literal["pass", "fail", "uncertain"]
    correct_referent: Literal["pass", "fail", "uncertain"]
    plausible_alternative: Literal["pass", "fail", "uncertain"]
    decision_relevance: Literal["pass", "fail", "uncertain"]
    evidence_sufficiency: Literal["pass", "fail", "uncertain"]
    risk_decision: Literal["low_risk", "flagged", "uncertain"]
    rationale: str = Field(min_length=1)


class HumanReviewRecord(BaseModel):
    """Review state that keeps summary judgments distinct from certification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    status: Literal[
        "provisional_summary_approved",
        "revised_pending_summary_review",
        "pending_detailed_review",
    ]
    review_basis: Literal["summary_only", "not_reviewed"]
    source_record_review: Literal["pending", "complete"] = "pending"
    evidence_view_review: Literal["pending", "complete"] = "pending"
    ambiguity_entailment_review: Literal["pending", "complete"] = "pending"
    strength_note: Literal["standard", "valid_low_strength", "revision_pending"]
    notes: str = Field(min_length=1)


def _variant(artifact: TaskArtifact, variant_type: VariantType) -> MessageVariant:
    return next(
        variant
        for variant in artifact.message_variant_group.variants
        if variant.type is variant_type
    )


def _truth_passes(artifact: TaskArtifact, variant: MessageVariant) -> bool:
    values = {fact.id: fact.value for fact in artifact.task_definition.facts}
    return bool(variant.truth_constraints) and all(
        evaluate_constraint(claim, values) is True
        for claim in variant.truth_constraints
    )


def _counterfactual_answer(artifact: TaskArtifact) -> str:
    values = {fact.id: fact.value for fact in artifact.task_definition.facts}
    values.update(artifact.message_variant_group.intended_inference_overrides)
    rule = artifact.task_definition.decision_rule
    results = [evaluate_constraint(constraint, values) for constraint in rule.constraints]
    if any(result is False for result in results):
        return rule.violated_answer
    if all(result is True for result in results):
        return rule.satisfied_answer
    return rule.unknown_answer


def _correct_referent_proxy(artifact: TaskArtifact) -> tuple[bool, str]:
    task = artifact.task_definition
    group = artifact.message_variant_group
    contract = group.ambiguity_contract
    entities = set(task.entity_ids)
    category = group.ambiguity_category
    if category is AmbiguityCategory.REFERENTIAL:
        defensible = contract.defensible_entity_id
        misleading = contract.misleading_entity_id
        subjects = {
            fact.entity_id: fact.subject
            for fact in task.facts
            if fact.entity_id in {defensible, misleading}
        }
        surface = contract.surface_form.lower()
        passed = (
            defensible in entities
            and misleading in entities
            and defensible != misleading
            and surface in subjects.get(defensible, "").lower()
            and surface in subjects.get(misleading, "").lower()
        )
        return passed, "Shared surface resolves to two declared entities with distinct roles."
    if category is AmbiguityCategory.SELECTIVE_OMISSION:
        omitted = set(contract.omitted_qualifier_fact_ids)
        omission = _variant(artifact, VariantType.SELECTIVE_OMISSION)
        passed = omitted == set(group.decisive_qualifier_fact_ids) and omitted.isdisjoint(
            omission.source_fact_ids
        )
        return passed, "Omitted qualifiers are explicit, decisive, and absent from the omission sources."
    if category is AmbiguityCategory.SCOPE:
        ids = set(contract.defensible_scope_entity_ids) | set(
            contract.misleading_scope_entity_ids
        )
        passed = bool(ids) and ids.issubset(entities)
        return passed, "Quantifier scopes refer only to declared entities."
    values = {fact.id: fact.value for fact in task.facts}
    defensible = values.get(contract.defensible_time_fact_id)
    misleading = values.get(contract.misleading_time_fact_id)
    passed = (
        isinstance(defensible, (int, float))
        and not isinstance(defensible, bool)
        and isinstance(misleading, (int, float))
        and not isinstance(misleading, bool)
        and defensible != misleading
    )
    return passed, "Defensible and misleading temporal anchors are distinct typed values."


def _alternative_interpretation_proxy(artifact: TaskArtifact) -> tuple[bool, str]:
    group = artifact.message_variant_group
    ambiguous = _variant(artifact, VariantType.AMBIGUOUS)
    category = group.ambiguity_category
    contract = group.ambiguity_contract
    text = ambiguous.text.lower()
    if category is AmbiguityCategory.REFERENTIAL:
        passed = contract.surface_form.lower() in text
        return passed, "Ambiguous text contains the shared surface without a disambiguating entity suffix."
    if category is AmbiguityCategory.SELECTIVE_OMISSION:
        passed = bool(ambiguous.omitted_fact_ids) and set(
            ambiguous.omitted_fact_ids
        ).isdisjoint(ambiguous.source_fact_ids)
        return passed, "Underspecified text omits the decisive qualifier while retaining true source facts."
    if category is AmbiguityCategory.SCOPE:
        passed = "all" in text and "did not" in text
        return passed, "Text contains the intended all/negation scope configuration."
    passed = (
        "minute" not in text
        and "earlier" not in text
        and not any(character.isdigit() for character in text)
    )
    return passed, "Ambiguous text omits the time anchor stored in the contract."


def _evidence_sufficiency(artifact: TaskArtifact) -> tuple[bool, str]:
    task = artifact.task_definition
    all_visible = {
        evidence.fact_id
        for view in artifact.agent_views
        for evidence in view.visible_evidence
    }
    no_complete_private_view = all(
        not set(task.ground_truth.required_fact_ids).issubset(
            {evidence.fact_id for evidence in view.visible_evidence}
        )
        for view in artifact.agent_views
    )
    passed = (
        all_visible == {fact.id for fact in task.facts}
        and solve_task(task, all_visible) == task.ground_truth.answer
        and no_complete_private_view
        and len(task.ground_truth.required_fact_ids) >= 2
    )
    return passed, "Combined views solve the task; no private view contains every rule fact."


def _screen_task(artifact: TaskArtifact) -> dict[str, Any]:
    task = artifact.task_definition
    group = artifact.message_variant_group
    complete = _variant(artifact, VariantType.COMPLETE)
    ambiguous = _variant(artifact, VariantType.AMBIGUOUS)
    omission = _variant(artifact, VariantType.SELECTIVE_OMISSION)

    complete_truth = _truth_passes(artifact, complete)
    ambiguous_truth = _truth_passes(artifact, ambiguous)
    omission_truth = _truth_passes(artifact, omission)
    referent_ok, referent_detail = _correct_referent_proxy(artifact)
    alternative_ok, alternative_detail = _alternative_interpretation_proxy(artifact)
    evidence_ok, evidence_detail = _evidence_sufficiency(artifact)
    counterfactual = _counterfactual_answer(artifact)
    decision_relevant = (
        counterfactual == group.intended_incorrect_answer
        and counterfactual != task.ground_truth.answer
        and counterfactual != "UNKNOWN"
    )
    complete_function = (
        complete_truth
        and complete.recommended_answer == task.ground_truth.answer
        and not complete.omitted_fact_ids
    )
    ambiguous_function = (
        ambiguous_truth
        and referent_ok
        and alternative_ok
        and decision_relevant
        and bool(ambiguous.defensible_interpretation)
        and bool(ambiguous.misleading_interpretation)
    )
    omission_function = (
        omission_truth
        and bool(omission.omitted_fact_ids)
        and bool(set(omission.omitted_fact_ids) & set(group.decisive_qualifier_fact_ids))
        and set(omission.omitted_fact_ids).isdisjoint(omission.source_fact_ids)
        and decision_relevant
    )

    risk_codes: list[str] = []
    risk_notes: list[str] = []
    deterministic = {
        "factual_entailment": complete_truth and ambiguous_truth and omission_truth,
        "correct_referent_or_scope": referent_ok,
        "plausible_alternative_proxy": alternative_ok,
        "decision_relevance": decision_relevant,
        "evidence_sufficiency": evidence_ok,
        "complete_condition_function": complete_function,
        "ambiguous_condition_function": ambiguous_function,
        "omission_condition_function": omission_function,
    }
    failed = [name for name, passed in deterministic.items() if not passed]
    if failed:
        risk_codes.append("DETERMINISTIC_SEMANTIC_CHECK_FAILED")
        risk_notes.append("Failed checks: " + ", ".join(failed) + ".")
    if group.ambiguity_category is AmbiguityCategory.SCOPE:
        risk_codes.append("MARKED_SCOPE_NEGATION_TEMPLATE")
        risk_notes.append(
            "The repeated 'all … did not' construction is logically interpretable but may be marked, unnatural, or language-model-specific."
        )
    if group.ambiguity_category is AmbiguityCategory.TEMPORAL:
        risk_codes.append("TEMPORAL_PAST_TENSE_CUE")
        risk_notes.append(
            "Past-tense wording may itself cue a historical reading, weakening the intended decision-time misinterpretation."
        )
    if not risk_notes:
        risk_notes.append(
            "No task-specific deterministic or heuristic risk was found; pragmatic strength still requires human review."
        )
    return {
        "task_id": task.task_id,
        "domain": task.domain,
        "category": group.ambiguity_category.value,
        "ground_truth": task.ground_truth.answer,
        "clear_statement": complete.text,
        "ambiguous_statement": ambiguous.text,
        "omission_statement": omission.text,
        "intended_incorrect_inference": group.intended_misleading_inference,
        "intended_incorrect_answer": group.intended_incorrect_answer,
        "condition_checks": {
            "clear": {
                "factual_entailment": complete_truth,
                "complete_and_solver_consistent": complete_function,
            },
            "ambiguous": {
                "factual_entailment": ambiguous_truth,
                "correct_referent_or_scope": referent_ok,
                "plausible_alternative_proxy": alternative_ok,
                "decision_relevant": decision_relevant,
            },
            "omission": {
                "factual_entailment": omission_truth,
                "decisive_qualifier_omitted": omission_function,
                "misleading_strength_required": False,
            },
            "evidence": {"combined_sufficient_and_private_incomplete": evidence_ok},
        },
        "check_details": [referent_detail, alternative_detail, evidence_detail],
        "risk_codes": risk_codes,
        "specific_risk": " ".join(risk_notes),
        "deterministic_route": "flagged" if risk_codes else "low_risk",
        "human_review_status": "pending",
    }


def _agreement(
    task_id: str, judgments: list[JudgeAssessment]
) -> tuple[str, list[str], bool]:
    task_judgments = [judgment for judgment in judgments if judgment.task_id == task_id]
    if not task_judgments:
        return "not_screened", [], False
    identities = {(judgment.judge_id, judgment.run_id) for judgment in task_judgments}
    if len(identities) != len(task_judgments):
        raise ValueError(f"duplicate judge/run assessment for {task_id}")
    decisions = [judgment.risk_decision for judgment in task_judgments]
    rationales = [f"{j.judge_id}/{j.run_id}: {j.rationale}" for j in task_judgments]
    adds_flag = any(decision != "low_risk" for decision in decisions)
    if len(decisions) == 1:
        return f"single_judge:{decisions[0]}", rationales, adds_flag
    if len(set(decisions)) == 1:
        return f"unanimous_{len(decisions)}:{decisions[0]}", rationales, adds_flag
    return f"disagreement_{len(decisions)}", rationales, True


def _template_diversity(artifacts: list[TaskArtifact]) -> dict[str, Any]:
    template_counts = Counter(
        artifact.generation_provenance.template_id for artifact in artifacts
    )
    structural_signatures = Counter(
        f"{artifact.generation_provenance.template_id}:{artifact.task_definition.ground_truth.answer}"
        for artifact in artifacts
    )
    category_answers: dict[str, Counter[str]] = defaultdict(Counter)
    for artifact in artifacts:
        category_answers[artifact.message_variant_group.ambiguity_category.value][
            artifact.task_definition.ground_truth.answer
        ] += 1
    return {
        "domain_count": len({artifact.task_definition.domain for artifact in artifacts}),
        "surface_ambiguous_statement_count": len(
            {
                _variant(artifact, VariantType.AMBIGUOUS).text
                for artifact in artifacts
            }
        ),
        "template_counts": dict(sorted(template_counts.items())),
        "structural_signature_count": len(structural_signatures),
        "structural_signature_counts": dict(sorted(structural_signatures.items())),
        "category_answer_counts": {
            category: dict(sorted(counts.items()))
            for category, counts in sorted(category_answers.items())
        },
        "systematic_weaknesses": [
            f"Forty surface-distinct tasks reduce to {len(structural_signatures)} template/answer structural signatures, creating memorization and template-artifact risk.",
            "All five scope tasks use the same marked wide-scope-negation construction and all have ground truth YES, creating category/answer confounding.",
            "All five temporal tasks use the same historical-versus-current-status pattern; past tense may reveal the defensible reading.",
            "All fifteen referential tasks use shared-name-prefix ambiguity; pronouns, roles, descriptions, and discourse anaphora are absent.",
            "Omission tasks remain concentrated in failed-qualifier and detected-but-resolved-issue patterns, despite three contextualized resolved-issue revisions.",
            "Complete controls always state the answer explicitly and are longer than treatment messages, creating condition-specific style cues.",
            "Evidence allocations are structurally sufficient but generated by deterministic shuffling rather than domain-role modeling.",
        ],
    }


def load_judgments(paths: list[str | Path]) -> list[JudgeAssessment]:
    judgments: list[JudgeAssessment] = []
    for path_like in paths:
        path = Path(path_like)
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    judgments.append(JudgeAssessment.model_validate_json(line))
                except ValueError as exc:
                    raise ValueError(f"invalid judgment at {path}:{line_number}: {exc}") from exc
    return judgments


def load_human_reviews(path_like: str | Path | None) -> list[HumanReviewRecord]:
    if path_like is None:
        return []
    payload = json.loads(Path(path_like).read_text(encoding="utf-8"))
    return [HumanReviewRecord.model_validate(row) for row in payload["records"]]


def screen_benchmark(
    artifacts: list[TaskArtifact],
    judgments: list[JudgeAssessment] | None = None,
    human_reviews: list[HumanReviewRecord] | None = None,
) -> dict[str, Any]:
    judgments = judgments or []
    human_reviews = human_reviews or []
    known_ids = {artifact.task_definition.task_id for artifact in artifacts}
    unknown = {judgment.task_id for judgment in judgments} - known_ids
    if unknown:
        raise ValueError(f"judgments refer to unknown tasks: {sorted(unknown)}")
    review_ids = [review.task_id for review in human_reviews]
    if len(review_ids) != len(set(review_ids)):
        raise ValueError("human review state contains duplicate task IDs")
    unknown_reviews = set(review_ids) - known_ids
    if unknown_reviews:
        raise ValueError(
            f"human reviews refer to unknown tasks: {sorted(unknown_reviews)}"
        )
    reviews_by_id = {review.task_id: review for review in human_reviews}
    task_rows = []
    for artifact in artifacts:
        row = _screen_task(artifact)
        agreement, rationales, llm_adds_flag = _agreement(row["task_id"], judgments)
        row["screening_agreement"] = agreement
        row["llm_screening_rationales"] = rationales
        if llm_adds_flag:
            row["risk_codes"].append("INDEPENDENT_SCREENING_FLAG")
            row["specific_risk"] += " At least one independent screening run flagged or was uncertain about the task."
        row["validation_status"] = (
            "flagged_pending_human"
            if row["risk_codes"]
            else "low_risk_pending_human"
        )
        human_review = reviews_by_id.get(row["task_id"])
        if human_review:
            row.update(
                human_review.model_dump(exclude={"task_id", "status", "notes"})
            )
            row["human_review_status"] = human_review.status
            row["human_review_notes"] = human_review.notes
        else:
            row.update(
                {
                    "human_review_status": "pending",
                    "review_basis": "not_reviewed",
                    "source_record_review": "pending",
                    "evidence_view_review": "pending",
                    "ambiguity_entailment_review": "pending",
                    "strength_note": "standard",
                    "human_review_notes": "No human review decision has been recorded.",
                }
            )
        task_rows.append(row)
    low_risk = sum(row["validation_status"] == "low_risk_pending_human" for row in task_rows)
    flagged = len(task_rows) - low_risk
    return {
        "screening_version": SCREENING_VERSION,
        "benchmark_task_count": len(artifacts),
        "low_risk_pending_human": low_risk,
        "flagged_pending_human": flagged,
        "provisional_summary_approved": sum(
            row["human_review_status"] == "provisional_summary_approved"
            for row in task_rows
        ),
        "revised_pending_summary_review": sum(
            row["human_review_status"] == "revised_pending_summary_review"
            for row in task_rows
        ),
        "full_human_approved": 0,
        "human_approved": 0,
        "full_human_review_pending": len(task_rows),
        "llm_judgment_count": len(judgments),
        "authority_statement": (
            "Deterministic screening and optional LLM judgments route review effort only. "
            "Neither can set human approval or redefine solver ground truth."
        ),
        "template_diversity": _template_diversity(artifacts),
        "tasks": task_rows,
    }


def _escape_markdown(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _write_review_table(report: dict[str, Any], output: Path) -> None:
    lines = [
        "# CASCADE risk-based semantic review table",
        "",
        "All tasks remain pending full source-record and evidence-view review. Provisional summary approval and low-risk routing are not full human certification.",
        "",
        "| Task ID | Category | Ground truth | Ambiguous statement | Intended incorrect inference | Validation status | Human review status | Specific risk | Screening agreement |",
        "|---|---|:---:|---|---|---|---|---|---|",
    ]
    for row in report["tasks"]:
        lines.append(
            "| "
            + " | ".join(
                _escape_markdown(value)
                for value in (
                    f"`{row['task_id']}`",
                    row["category"],
                    row["ground_truth"],
                    row["ambiguous_statement"],
                    row["intended_incorrect_inference"],
                    row["validation_status"],
                    row["human_review_status"],
                    row["specific_risk"],
                    row["screening_agreement"],
                )
            )
            + " |"
        )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_low_risk_batch(report: dict[str, Any], output: Path) -> None:
    fields = [
        "task_id",
        "category",
        "ground_truth",
        "clear_statement",
        "ambiguous_statement",
        "omission_statement",
        "intended_incorrect_inference",
        "specific_risk",
        "screening_agreement",
        "human_decision",
        "human_notes",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report["tasks"]:
            if row["validation_status"] != "low_risk_pending_human":
                continue
            writer.writerow(
                {
                    **{field: row.get(field, "") for field in fields[:-2]},
                    "human_decision": row["human_review_status"],
                    "human_notes": row["human_review_notes"],
                }
            )


def _write_flagged_review(report: dict[str, Any], output: Path) -> None:
    lines = [
        "# CASCADE flagged semantic review",
        "",
        "These tasks require individual human review. No task is approved by this file.",
        "",
    ]
    for row in report["tasks"]:
        if row["validation_status"] != "flagged_pending_human":
            continue
        lines.extend(
            [
                f"## `{row['task_id']}` — {row['category']}",
                "",
                f"- Ground truth: `{row['ground_truth']}`",
                f"- Clear: {row['clear_statement']}",
                f"- Ambiguous: {row['ambiguous_statement']}",
                f"- Omission: {row['omission_statement']}",
                f"- Intended incorrect inference: {row['intended_incorrect_inference']}",
                f"- Risk codes: {', '.join(row['risk_codes'])}",
                f"- Specific risk: {row['specific_risk']}",
                f"- Screening agreement: {row['screening_agreement']}",
                f"- Human decision: **{row['human_review_status']}**",
                f"- Human notes: {row['human_review_notes']}",
                "",
            ]
        )
    output.write_text("\n".join(lines), encoding="utf-8")


def _write_judge_packets(artifacts: list[TaskArtifact], output: Path) -> None:
    instruction = (
        "Independently screen semantic risk. Do not infer or redefine ground truth. "
        "Judge factual entailment, referent/scope correctness, plausible alternative "
        "interpretation, decision relevance, and evidence sufficiency. Return one "
        "JudgeAssessment JSON object. An omission statement need not be covert or "
        "independently misleading; it must be true and omit a decision-relevant qualifier."
    )
    with output.open("w", encoding="utf-8") as handle:
        for artifact in artifacts:
            task = artifact.task_definition
            group = artifact.message_variant_group
            packet = {
                "screening_instruction": instruction,
                "task_id": task.task_id,
                "category": group.ambiguity_category.value,
                "question": task.question,
                "structured_facts": [
                    {"fact_id": fact.id, "entity_id": fact.entity_id, "predicate": fact.predicate, "value": fact.value}
                    for fact in task.facts
                ],
                "solver_answer_read_only": task.ground_truth.answer,
                "variants": {
                    variant.type.value: {
                        "text": variant.text,
                        "source_fact_ids": list(variant.source_fact_ids),
                        "omitted_fact_ids": list(variant.omitted_fact_ids),
                    }
                    for variant in group.variants
                },
                "defensible_interpretation": _variant(artifact, VariantType.AMBIGUOUS).defensible_interpretation,
                "intended_incorrect_inference": group.intended_misleading_inference,
                "intended_incorrect_answer": group.intended_incorrect_answer,
            }
            handle.write(json.dumps(packet, sort_keys=True) + "\n")


def write_screening_outputs(
    report: dict[str, Any], artifacts: list[TaskArtifact], output_dir: str | Path
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "semantic_screening.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_review_table(report, out / "semantic_review_table.md")
    _write_low_risk_batch(report, out / "low_risk_batch_review.csv")
    _write_flagged_review(report, out / "flagged_review.md")
    _write_judge_packets(artifacts, out / "llm_judge_packets.jsonl")
    (out / "llm_judgment_schema.json").write_text(
        json.dumps(JudgeAssessment.model_json_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    canonical_path = out / "canonical_tasks.jsonl"
    canonical_hash = (
        hashlib.sha256(canonical_path.read_bytes()).hexdigest()
        if canonical_path.exists()
        else None
    )
    manifest = {
        "screening_version": SCREENING_VERSION,
        "canonical_tasks_sha256": canonical_hash,
        "canonical_tasks_modified": False,
        "previous_review_preserved_at": "data/benchmark/history/v2/",
        "provisional_summary_approved": report["provisional_summary_approved"],
        "revised_pending_summary_review": report[
            "revised_pending_summary_review"
        ],
        "full_human_approved": 0,
        "full_human_review_pending": report["full_human_review_pending"],
    }
    (out / "review_workflow_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", default="data/benchmark/canonical_tasks.jsonl")
    parser.add_argument("--out-dir", default="data/benchmark")
    parser.add_argument("--judgments", action="append", default=[])
    parser.add_argument("--human-review-state")
    args = parser.parse_args()
    artifacts = read_jsonl(args.canonical)
    judgments = load_judgments(args.judgments)
    human_reviews = load_human_reviews(args.human_review_state)
    report = screen_benchmark(artifacts, judgments, human_reviews)
    write_screening_outputs(report, artifacts, args.out_dir)
    print(
        f"tasks={report['benchmark_task_count']} "
        f"low_risk={report['low_risk_pending_human']} "
        f"flagged={report['flagged_pending_human']} "
        f"llm_judgments={report['llm_judgment_count']} "
        f"provisional_summary_approved={report['provisional_summary_approved']} "
        "full_human_approved=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

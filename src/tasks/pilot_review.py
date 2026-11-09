"""Render a source-backed Phase 3 semantic-review packet without approving tasks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from .export import read_jsonl
from .schemas import TaskArtifact, VariantType
from .solver import evaluate_constraint, solve_task


def artifact_sha256(artifact: TaskArtifact) -> str:
    payload = json.dumps(
        artifact.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _counterfactual_answer(artifact: TaskArtifact) -> str:
    values = {fact.id: fact.value for fact in artifact.task_definition.facts}
    values.update(artifact.message_variant_group.intended_inference_overrides)
    rule = artifact.task_definition.decision_rule
    results = [evaluate_constraint(item, values) for item in rule.constraints]
    if any(result is False for result in results):
        return rule.violated_answer
    if all(result is True for result in results):
        return rule.satisfied_answer
    return rule.unknown_answer


def _escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _load_adjudications(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["task_id"]: row for row in csv.DictReader(handle)}


def render_review_packet(
    canonical_path: Path,
    manifest_path: Path,
    adjudication_path: Path,
) -> str:
    artifacts = {
        item.task_definition.task_id: item for item in read_jsonl(canonical_path)
    }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    adjudications = _load_adjudications(adjudication_path)
    lines = [
        "# Phase 3 pilot source-record review queue",
        "",
        "**Queue version:** 1.0  ",
        f"**Source manifest:** `{manifest['manifest_id']}` ({manifest['execution_tier']})  ",
        f"**Tasks:** {manifest['task_count']}  ",
        "**Certification status:** 0 fully certified; every decision below begins pending.",
        "",
        "This packet expands each exact hash-pinned exploratory task into its full facts, "
        "five private views, executable rule, matched messages, and mechanical checks. "
        "Mechanical pass does not settle natural truthfulness, ambiguity/omission function, "
        "or experimental naturalness.",
        "",
        "## Fast adjudication",
        "",
        "For each task, inspect the source record below and fill the matching row in "
        "`data/development/phase3/pilot_adjudication.csv`. Set each dimension to "
        "`approved`, `revise`, or `rejected`; add reviewer, ISO date, and notes. "
        "Only an `approved` overall decision with all component dimensions approved may "
        "enter a future confirmatory manifest. The exploratory manifest is unchanged.",
        "",
    ]
    for index, manifest_row in enumerate(manifest["tasks"], start=1):
        task_id = manifest_row["task_id"]
        artifact = artifacts[task_id]
        if artifact_sha256(artifact) != manifest_row["task_content_sha256"]:
            raise ValueError(f"manifest hash mismatch for {task_id}")
        task = artifact.task_definition
        group = artifact.message_variant_group
        decisions = adjudications[task_id]
        values = {fact.id: fact.value for fact in task.facts}
        truth_checks = {
            variant.type.value: bool(variant.truth_constraints)
            and all(
                evaluate_constraint(constraint, values) is True
                for constraint in variant.truth_constraints
            )
            for variant in group.variants
        }
        combined_ids = {
            evidence.fact_id
            for view in artifact.agent_views
            for evidence in view.visible_evidence
        }
        private_incomplete = all(
            not set(task.ground_truth.required_fact_ids).issubset(
                {evidence.fact_id for evidence in view.visible_evidence}
            )
            for view in artifact.agent_views
        )
        lines.extend(
            [
                f"<details><summary><strong>{index}. {task_id}</strong> — "
                f"{task.domain} / {group.ambiguity_category.value} / answer "
                f"{task.ground_truth.answer}</summary>",
                "",
                f"- Content SHA-256: `{manifest_row['task_content_sha256']}`",
                f"- Variant group: `{task.variant_group_id}`",
                f"- Review state: `{manifest_row['review_status']}` / "
                f"`{manifest_row['review_basis']}`; human-certified: `false`",
                f"- Question: {_escape(task.question)}",
                f"- Ground-truth explanation: {_escape(task.ground_truth.explanation)}",
                f"- Intended incorrect answer: `{group.intended_incorrect_answer}`",
                f"- Intended incorrect inference: {_escape(group.intended_misleading_inference)}",
                "",
                "### Atomic facts",
                "",
                "| Fact | Entity | Predicate | Value | Evidence text |",
                "|---|---|---|---|---|",
            ]
        )
        for fact in task.facts:
            lines.append(
                f"| `{fact.id}` | `{fact.entity_id or '-'}` | `{fact.predicate}` | "
                f"`{_escape(json.dumps(fact.value))}` | {_escape(fact.evidence_text)} |"
            )
        lines.extend(["", "### Executable rule", ""])
        for constraint in task.decision_rule.constraints:
            right = (
                f"fact `{constraint.right_fact_id}`"
                if constraint.right_fact_id is not None
                else f"value `{constraint.expected_value}`"
            )
            lines.append(
                f"- `{constraint.id}`: fact `{constraint.left_fact_id}` "
                f"{constraint.operator.value} {right} — {_escape(constraint.description)}"
            )
        lines.extend(
            [
                f"- All satisfied → `{task.decision_rule.satisfied_answer}`; any violated → "
                f"`{task.decision_rule.violated_answer}`; insufficient → `UNKNOWN`.",
                "",
                "### Five private evidence views",
                "",
            ]
        )
        for view in artifact.agent_views:
            evidence = "; ".join(
                f"`{item.fact_id}` {_escape(item.text)}" for item in view.visible_evidence
            )
            lines.append(f"- **{view.agent_id}:** {evidence}")
        lines.extend(["", "### Exact matched messages", ""])
        for variant_type in (
            VariantType.COMPLETE,
            VariantType.AMBIGUOUS,
            VariantType.SELECTIVE_OMISSION,
        ):
            variant = next(item for item in group.variants if item.type is variant_type)
            lines.extend(
                [
                    f"- **{variant.type.value}:** {_escape(variant.text)}",
                    f"  - Sources: {', '.join(f'`{item}`' for item in variant.source_fact_ids)}; "
                    f"omitted: {', '.join(f'`{item}`' for item in variant.omitted_fact_ids) or 'none'}",
                ]
            )
            if variant.defensible_interpretation:
                lines.append(
                    f"  - Defensible interpretation: {_escape(variant.defensible_interpretation)}"
                )
            if variant.misleading_interpretation:
                lines.append(
                    f"  - Misleading interpretation: {_escape(variant.misleading_interpretation)}"
                )
        lines.extend(
            [
                "",
                "### Mechanical evidence (not semantic certification)",
                "",
                f"- Solver reproduces stored answer: `{solve_task(task) == task.ground_truth.answer}`",
                f"- Complete/ambiguous/omission truth constraints pass: "
                f"`{truth_checks.get('complete')}` / `{truth_checks.get('ambiguous')}` / "
                f"`{truth_checks.get('selective_omission')}`",
                f"- Intended overrides produce `{_counterfactual_answer(artifact)}`: "
                f"`{_counterfactual_answer(artifact) == group.intended_incorrect_answer}`",
                f"- Combined views cover all facts and solve correctly: "
                f"`{combined_ids == set(values) and solve_task(task, combined_ids) == task.ground_truth.answer}`",
                f"- No private view contains every required fact: `{private_incomplete}`",
                "- Known semantic risks:",
            ]
        )
        lines.extend(f"  - {_escape(risk)}" for risk in manifest_row["known_semantic_risks"])
        lines.extend(
            [
                f"- Current adjudication: truth `{decisions['truthfulness']}`, function "
                f"`{decisions['ambiguity_or_omission_function']}`, relevance "
                f"`{decisions['decision_relevance']}`, evidence "
                f"`{decisions['evidence_allocation']}`, overall "
                f"`{decisions['overall_confirmatory_decision']}`.",
                "",
                "</details>",
                "",
            ]
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", default="data/benchmark/canonical_tasks.jsonl")
    parser.add_argument(
        "--manifest", default="configs/phase3_exploratory_pilot_manifest.json"
    )
    parser.add_argument(
        "--adjudication", default="data/development/phase3/pilot_adjudication.csv"
    )
    parser.add_argument("--out", default="research/phase3_pilot_review.md")
    args = parser.parse_args(argv)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    packet = render_review_packet(
        Path(args.canonical), Path(args.manifest), Path(args.adjudication)
    )
    output.write_text(packet + "\n", encoding="utf-8")
    print(f"review_tasks={packet.count('<details>')} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

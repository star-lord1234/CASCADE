import hashlib
import json

from src.tasks.export import read_jsonl


def _artifact_hash(artifact) -> str:
    encoded = json.dumps(
        artifact.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_exploratory_manifest_is_hash_pinned_and_not_confirmatory() -> None:
    manifest = json.loads(
        open(
            "configs/phase3_exploratory_pilot_manifest.json",
            encoding="utf-8",
        ).read()
    )
    review_state = json.loads(
        open("data/benchmark/human_review_state.json", encoding="utf-8").read()
    )
    artifacts = {
        artifact.task_definition.task_id: artifact
        for artifact in read_jsonl("data/benchmark/canonical_tasks.jsonl")
    }
    reviews = {row["task_id"]: row for row in review_state["records"]}

    assert manifest["execution_tier"] == "EXPLORATORY"
    assert manifest["required_result_label"] == "exploratory/non-confirmatory"
    assert manifest["confirmatory_eligible"] is False
    assert manifest["human_certified_task_count"] == 0
    assert 10 <= manifest["task_count"] <= 12
    assert manifest["task_count"] == len(manifest["tasks"])
    assert len({row["task_id"] for row in manifest["tasks"]}) == manifest["task_count"]

    for row in manifest["tasks"]:
        task_id = row["task_id"]
        assert reviews[task_id]["status"] == "provisional_summary_approved"
        assert row["review_status"] == "provisional_summary_approved"
        assert row["review_basis"] == "summary_only"
        assert row["human_certified"] is False
        assert row["confirmatory_eligible"] is False
        assert row["known_semantic_risks"]
        assert row["task_content_sha256"] == _artifact_hash(artifacts[task_id])


def test_exploratory_manifest_excludes_revisions_and_is_balanced() -> None:
    manifest = json.loads(
        open(
            "configs/phase3_exploratory_pilot_manifest.json",
            encoding="utf-8",
        ).read()
    )
    task_ids = {row["task_id"] for row in manifest["tasks"]}
    excluded = set(
        manifest["selection_summary"]["excluded_unresolved_revision_task_ids"]
    )
    assert task_ids.isdisjoint(excluded)
    assert {row["ambiguity_category"] for row in manifest["tasks"]} == {
        "referential_ambiguity",
        "selective_omission",
    }
    assert sum(row["solver_answer"] == "YES" for row in manifest["tasks"]) == 6
    assert sum(row["solver_answer"] == "NO" for row in manifest["tasks"]) == 6

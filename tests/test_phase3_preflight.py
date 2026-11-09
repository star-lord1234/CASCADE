import csv
import json
from pathlib import Path

from src.tasks.pilot_review import render_review_packet


def test_review_packet_is_source_backed_and_all_decisions_pending() -> None:
    packet = render_review_packet(
        Path("data/benchmark/canonical_tasks.jsonl"),
        Path("configs/phase3_exploratory_pilot_manifest.json"),
        Path("data/development/phase3/pilot_adjudication.csv"),
    )
    assert packet.count("<details>") == 12
    assert packet.count("### Atomic facts") == 12
    assert packet.count("### Five private evidence views") == 12
    assert packet.count("### Exact matched messages") == 12
    assert "human-certified: `false`" in packet
    assert "overall `pending`" in packet

    with open(
        "data/development/phase3/pilot_adjudication.csv",
        newline="",
        encoding="utf-8",
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 12
    assert all(row["overall_confirmatory_decision"] == "pending" for row in rows)
    assert all(not row["reviewer"] and not row["reviewed_at"] for row in rows)


def test_confirmatory_manifest_is_empty_until_individual_approval() -> None:
    manifest = json.loads(
        Path("configs/phase3_confirmatory_pilot_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["execution_tier"] == "CONFIRMATORY"
    assert manifest["status"] == "blocked_pending_individual_semantic_review"
    assert manifest["required_approved_task_count"] == 10
    assert manifest["task_count"] == 0
    assert manifest["tasks"] == []


def test_protocol_freezes_required_rq1_definitions() -> None:
    protocol = Path("research/phase3_rq1_protocol.md").read_text(encoding="utf-8")
    required_phrases = [
        "exploratory/non-confirmatory",
        "Primary contrast",
        "Incorrect consensus",
        "Incorrect adoption",
        "Cascade-like propagation",
        "Evidence coverage",
        "strict majority",
        "UNKNOWN",
        "Full-information control",
        "Individual ambiguous-exposure control",
        "two synchronous rounds",
        "three per task/condition",
        "No task is removed",
    ]
    for phrase in required_phrases:
        assert phrase.lower() in protocol.lower()

from pathlib import Path

import pytest

from src.tasks.export import read_jsonl, write_jsonl
from src.tasks.generator import generate_artifacts


def test_jsonl_round_trip(tmp_path: Path) -> None:
    artifacts = generate_artifacts(count=5, seed=42)
    output = tmp_path / "nested" / "tasks.jsonl"
    assert write_jsonl(artifacts, output) == 5
    assert read_jsonl(output) == artifacts


def test_malformed_jsonl_is_rejected_with_line_number(tmp_path: Path) -> None:
    source = tmp_path / "bad.jsonl"
    source.write_text('{"not": "a task artifact"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"bad\.jsonl:1"):
        read_jsonl(source)


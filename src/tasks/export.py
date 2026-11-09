"""Standard JSONL export for canonical Phase 1 artifacts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from .schemas import TaskArtifact, jsonable


def write_jsonl(artifacts: Iterable[TaskArtifact], output: str | Path) -> int:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(artifacts)
    with path.open("w", encoding="utf-8") as handle:
        for artifact in rows:
            handle.write(json.dumps(jsonable(artifact), sort_keys=True) + "\n")
    return len(rows)


def read_jsonl(source: str | Path) -> list[TaskArtifact]:
    path = Path(source)
    artifacts: list[TaskArtifact] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                artifacts.append(TaskArtifact.model_validate_json(line))
            except ValueError as exc:
                raise ValueError(f"invalid artifact at {path}:{line_number}: {exc}") from exc
    return artifacts


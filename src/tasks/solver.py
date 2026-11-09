"""Deterministic ground-truth solver for structured task facts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .schemas import ComparisonOperator, Constraint, TaskDefinition


def _compare(left: Any, operator: ComparisonOperator, right: Any) -> bool:
    operations = {
        ComparisonOperator.EQ: lambda: left == right,
        ComparisonOperator.NE: lambda: left != right,
        ComparisonOperator.LT: lambda: left < right,
        ComparisonOperator.LE: lambda: left <= right,
        ComparisonOperator.GT: lambda: left > right,
        ComparisonOperator.GE: lambda: left >= right,
    }
    try:
        return bool(operations[operator]())
    except TypeError as exc:
        raise ValueError(
            f"constraint {operator.value} cannot compare {left!r} and {right!r}"
        ) from exc


def evaluate_constraint(
    constraint: Constraint, values: dict[str, Any]
) -> bool | None:
    if constraint.left_fact_id not in values:
        return None
    if constraint.right_fact_id is not None:
        if constraint.right_fact_id not in values:
            return None
        right = values[constraint.right_fact_id]
    else:
        right = constraint.expected_value
    return _compare(values[constraint.left_fact_id], constraint.operator, right)


def solve_task(
    task: TaskDefinition, available_fact_ids: Iterable[str] | None = None
) -> str:
    """Solve from structured facts only; return UNKNOWN when evidence is insufficient.

    For an all-constraints rule, one known violation is sufficient to establish the
    violated answer. The satisfied answer requires every constraint to be known and
    satisfied.
    """

    allowed = (
        {fact.id for fact in task.facts}
        if available_fact_ids is None
        else set(available_fact_ids)
    )
    values = {fact.id: fact.value for fact in task.facts if fact.id in allowed}
    results = [
        evaluate_constraint(constraint, values)
        for constraint in task.decision_rule.constraints
    ]
    if any(result is False for result in results):
        return task.decision_rule.violated_answer
    if all(result is True for result in results):
        return task.decision_rule.satisfied_answer
    return task.decision_rule.unknown_answer


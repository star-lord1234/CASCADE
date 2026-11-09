"""CLI for Phase 3.1 dry-run planning and deterministic mock verification."""

from __future__ import annotations

import argparse
import json
import sys

from .rq1_runner import (
    RQ1ConfigurationError,
    build_dry_run_plan,
    load_run_config,
    run_live_experiment,
    run_mock_experiment,
)


def _dry_run(args: argparse.Namespace) -> int:
    plan = build_dry_run_plan(load_run_config(args.config))
    print(json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


def _run_mock(args: argparse.Namespace) -> int:
    summary = run_mock_experiment(load_run_config(args.config))
    print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0 if summary.failed_units == 0 else 1


def _run_live(args: argparse.Namespace) -> int:
    summary = run_live_experiment(
        load_run_config(args.config),
        paid_calls_authorized=args.confirm_paid_calls,
    )
    print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0 if summary.failed_units == 0 else 1


def _run_pilot(args: argparse.Namespace) -> int:
    summary = run_live_experiment(
        load_run_config(args.config),
        paid_calls_authorized=args.confirm_paid_calls,
        integration_only=False,
        max_new_model_calls=args.max_new_calls,
    )
    print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0 if summary.failed_units == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CASCADE Phase 3 RQ1 runner")
    commands = parser.add_subparsers(dest="command", required=True)
    dry = commands.add_parser("dry-run", help="plan calls/tokens/cost; never call a model")
    dry.add_argument("--config", required=True)
    dry.set_defaults(handler=_dry_run)
    mock = commands.add_parser("run-mock", help="run deterministic mock controls/treatments")
    mock.add_argument("--config", required=True)
    mock.set_defaults(handler=_run_mock)
    live = commands.add_parser(
        "run-live",
        help="run the guarded one-task Groq integration after explicit authorization",
    )
    live.add_argument("--config", required=True)
    live.add_argument(
        "--confirm-paid-calls",
        action="store_true",
        help="required explicit opt-in; the command refuses live calls without it",
    )
    live.set_defaults(handler=_run_live)
    pilot = commands.add_parser(
        "run-pilot-chunk",
        help="run one resumable, daily-capped Phase 3.3 Groq pilot chunk",
    )
    pilot.add_argument("--config", required=True)
    pilot.add_argument("--max-new-calls", type=int, default=109)
    pilot.add_argument("--confirm-paid-calls", action="store_true")
    pilot.set_defaults(handler=_run_pilot)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except RQ1ConfigurationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

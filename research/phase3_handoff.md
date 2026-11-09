# CASCADE Phase 3 exploratory handoff

**Status:** Phase 3.2 live integration gate passes for the required clear/ambiguous pair; confirmatory gate remains blocked. Phase 3.3 is authorized for preflight and implementation, but its larger paid pilot is not yet authorized. No task is fully human-certified.

## Evidence entering Phase 3

- Phase 2 mock infrastructure and trace validation pass.
- The project owner reports a successful single-agent Groq smoke using `openai/gpt-oss-120b`: `task=MB_e8ed46b2e2ce70 agent=agent_1 belief=UNKNOWN`. This is user-reported and not independently trace-verified.
- `configs/phase3_exploratory_pilot_manifest.json` freezes 12 provisionally reviewed task versions: six referential, six omission, six YES, and six NO.
- `research/phase3_pilot_review.md` expands those exact hashes into the full source-record adjudication queue; all 12 decisions remain pending.
- `research/phase3_rq1_protocol.md` freezes the primary contrast, controls, metrics, aggregation, timing, rounds, repetitions, and exclusion rules before multi-agent live results.
- `configs/phase3_confirmatory_pilot_manifest.json` is intentionally empty, so provisional review cannot be mistaken for confirmatory certification.
- Four revised-pending tasks and all flagged scope/temporal tasks are excluded from exploratory v1.
- Three low-strength omission tasks remain included with that risk explicitly preserved for exploratory feasibility testing.

## Interpretation boundary

Every live result using this manifest must be labeled `exploratory/non-confirmatory`. It may test feasibility, request budgeting, trace integrity, and provisional RQ1 patterns. It is not a final RQ1 estimate and cannot justify selecting only favorable tasks for later confirmation.

Confirmatory work remains blocked until individual source-record and evidence-view review is complete and a separate confirmatory manifest is frozen.

## Phase 3.0 gate

- Exploratory manifest: **PASS** — 12 provisionally reviewed, risk-labeled, hash-pinned tasks.
- RQ1 protocol freeze: **PASS** — definitions and matched contrasts are prespecified.
- Confirmatory manifest: **BLOCKED as intended** — 0/10 required individually approved tasks.
- Paid execution: **NOT AUTHORIZED** — Phase 3.1 has now produced the required dry-run plan, but live calls still require a separate explicit authorization.

## Phase 3.1 implementation and gate

- Runner: `src/experiments/rq1_runner.py` builds matched, hash-pinned units and reuses the Phase 2 isolated-agent, orchestration, trace-validation and append-only logging infrastructure.
- Conditions: independent/no communication; full-information single-agent; five separate individual ambiguous-exposure controls; multi-agent clear; multi-agent ambiguous; and multi-agent omission.
- Matched contract: task hash, five evidence allocations, model configuration, two rounds, fully connected network, sender, injection round, aggregation policy, repetition and seed are fixed. Only the controlled message variant changes across the three multi-agent treatments.
- Injection point: the controlled message is sent by `agent_1` to `agent_2`–`agent_5` at round 1 before organic message drafting. Experimenter provenance stays in the routed trace; condition/variant labels and controlled source-fact annotations are stripped from agent-facing delivery.
- Resumption/failure behavior: existing episode IDs are skipped; both completed and failed units are append-only records; no failed output is fabricated. A replacement requires a new run/episode ID.
- Mock gate: **PASS** — one task × one repetition produced 10 units, 91 deterministic model calls, 4 validated group traces, and 6 validated control traces with zero failures.
- Test gate: **PASS** — tests verify paired identity, exact exposure, privacy, unique condition IDs, stale-hash rejection, rate accounting, failure recording and resumption.
- Live gate: **NOT RUN / NOT CLAIMED** — the Phase 3.1 CLI intentionally exposes only `dry-run` and `run-mock`.

### Dry-run budget for the frozen exploratory manifest

For 12 tasks × 3 repetitions, the runner plans 360 resumable units and 3,276 model calls: 36 independent, 36 full-information, 180 individual-exposure, and 36 for each multi-agent treatment. With planning assumptions of 1,200 input and 256 output tokens per call, this is approximately 3,931,200 input plus 838,656 output tokens. At the documented GPT-OSS 120B prices of $0.15/M input and $0.60/M output, the estimate is **$1.092874**, excluding retries and provider-side accounting differences.

The plan applies an 80% safety fraction to the documented base limits (30 RPM, 1,000 RPD, 8,000 TPM, 200,000 TPD). The token estimate is the binding constraint: 4 requests/minute and 109 requests/day, implying at least 31 days for the full exploratory plan at those base limits. The Groq account limits page remains authoritative. Sources: [GPT-OSS 120B model page](https://console.groq.com/docs/model/openai/gpt-oss-120b) and [Groq rate limits](https://console.groq.com/docs/rate-limits).

## Exact next command

Reproduce the complete one-task Phase 3.1 mock gate (no API calls):

```bash
.venv/bin/python -m src.experiments.rq1_cli run-mock \
  --config configs/phase3_rq1_mock_smoke.json
```

The next phase transition is Prompt 3.2 and requires explicit user instruction. Before any Groq call, rerun the dry plan with `.venv/bin/python -m src.experiments.rq1_cli dry-run --config configs/phase3_rq1_exploratory_plan.json`, select the one-task live subset, show its exact call/token/cost budget, and obtain explicit paid-call authorization. Do not infer authorization from this handoff.

## Phase 3.2 live integration — completed

The user separately authorized the exact 91-call Phase 3.2 batch on 2026-11-09. `configs/phase3_rq1_live_integration.json` froze one task (`MB_e8ed46b2e2ce70`), one repetition and all six prespecified conditions. Execution remained within scope and used the pinned Groq model and endpoint.

- Provider configuration: `GROQ_API_KEY`, `https://api.groq.com/openai/v1`, `openai/gpt-oss-120b`, strict JSON Schema, temperature 0, 1,024 maximum output tokens, no automatic retry or model substitution.
- Proposed execution: 10 resumable units and 91 provider calls — 5 independent, 1 full-information, 10 individual pre/post exposure, and 25 calls for each of clear, ambiguous and omission multi-agent episodes.
- Approximate budget: 109,200 input tokens, 23,296 output tokens and **$0.030358** under the frozen planning assumptions. Observed provider token usage will be recorded when supplied.
- Throttling: sequential calls no faster than one every 15 seconds. The batch is below the conservative 109-request daily estimate, but the Groq account limits page is authoritative.
- Actual accounting: **89 model calls**, of which 88 returned usage metadata; 79,613 input tokens and 39,616 output tokens; estimated actual cost **$0.035712** at the documented rates. The realized cost exceeded the planning estimate because average output length was higher than the assumed 256 tokens, not because the call cap was exceeded.
- Completed group episodes: clear, ambiguous and omission, 25 calls each. Every completed group aggregate was `ABSTAIN`.
- Completed controls: full-information (1 call) and all five individual ambiguous exposures (2 calls each).
- Preserved failure: independent/no-communication failed on agent 3 after two successful `UNKNOWN` reports because Groq returned HTTP 400 `json_validate_failed`. No group outcome was fabricated and no replacement was run.
- Belief transitions: clear and omission had four stable `UNKNOWN` agents and one stable `NO` agent; ambiguous had the same starting pattern, with agent 4 moving `NO → NO → UNKNOWN`. Individual exposure controls were stable: agents 1, 2, 3 and 5 remained `UNKNOWN`; agent 4 remained `NO`. Full-information returned `UNKNOWN` in this single integration repetition.
- Validation: all four group traces passed **2,312 trace cross-reference checks**. All six control records passed their strict schemas. Controlled delivery, belief updates, aggregation, usage metadata, and model settings are preserved in append-only trace files.
- Interpretation: **exploratory/non-confirmatory infrastructure evidence only**. A single task with ABSTAIN outcomes supports no RQ1 efficacy conclusion. Full-information feasibility for this task remains unresolved under the prespecified two-of-three rule.
- Phase 3.2 gate: **PASS** — actual complete clear and ambiguous multi-agent episodes validated end to end. The independent failure remains part of the record.

Phase 3.3 may prepare metrics and exports under the user's phase authorization. Its full 12-task paid pilot requires a new exact budget authorization and must not reuse Phase 3.2 authorization.

## Phase 3.3 authorization and chunk policy

On 2026-11-09, the user explicitly authorized the complete exploratory pilot exactly as budgeted: 12 frozen provisional tasks, six conditions, three repetitions, maximum 3,276 model calls, pinned `openai/gpt-oss-120b`, and no scope or model substitution. The prespecified estimate is $1.092874; projection from Phase 3.2 observed token lengths is approximately $1.329444. Both are estimates, not efficacy results.

`configs/phase3_rq1_exploratory_pilot.json` is the authorized execution configuration. `run-pilot-chunk` enforces the complete 12-task/3-repetition/six-condition plan and schedules at most 109 new calls per invocation. Completed and failed unit IDs are append-preserved and skipped on later invocations; unscheduled units are reported as deferred. Automatic provider retries are disabled, so transport retries cannot silently exceed the call authorization.

The first chunk has not been launched by Codex because `GROQ_API_KEY` is unavailable to the Codex subprocess and native Terminal automation is disallowed by the desktop safety boundary. The user must run the exact chunk command in the existing terminal session that holds the key. This is an execution-environment constraint, not an experimental failure.

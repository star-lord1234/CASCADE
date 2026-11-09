# CASCADE Phase 2 audit and handoff

**Audit date:** 2026-11-08  
**Scope:** Phase 2 infrastructure only; no RQ1/RQ3 analysis or scientific conclusions  
**Status:** Offline/mock Phase 2 engineering gate passes. The project owner reports one successful Groq single-agent live smoke. This observation is not independently trace-verified. Phase 3 engineering and explicitly labeled exploratory work may proceed under the tier policy; confirmatory work remains blocked by full semantic review.

## Implemented components

- `src/simulation/loader.py` — strict canonical JSONL loading, benchmark hashing, exact agent-view/allocation checks, and safe controlled-stimulus selection.
- `src/simulation/schemas.py` — isolated contexts, model I/O, messages, beliefs, episode configuration, routed messages, and group outcomes.
- `src/simulation/agent.py` — safe prompt construction, isolated delivery, and authorization checks for evidence and parent-message references.
- `src/simulation/model_client.py` — schema-checked OpenAI-compatible client, bounded configured retries, request-keyed mock, and evidence-echo mock.
- `src/simulation/network.py` and `communication.py` — deterministic fully connected, ring, and star routing plus batch delivery.
- `src/simulation/orchestrator.py` — independent Round 0, controlled injection, collect-before-deliver synchronous rounds, belief updates, and strict-majority aggregation.
- `src/simulation/event_logger.py`, `trace_schemas.py`, `trace_runner.py`, and `trace_validation.py` — append-only audit traces, global event order, run timestamps, model metadata, token accounting, error records, and cross-reference validation.
- `src/simulation/replay.py` — saved-event replay with no model invocation.
- `src/simulation/cli.py` — mock batch execution, validation, replay, and a one-call live-adapter smoke command.

## Run commands

```bash
.venv/bin/python -m pytest -q

.venv/bin/python -m src.simulation.cli run-mock \
  --config configs/phase2_mock_smoke.json

.venv/bin/python -m src.simulation.cli validate \
  --trace data/development/traces/phase2_mock_smoke.jsonl

.venv/bin/python -m src.simulation.cli replay \
  --trace data/development/traces/phase2_mock_smoke.jsonl
```

Optional single live call, only after configuring a key outside the repository:

```bash
GROQ_API_KEY='<configured outside the repository>' \
  .venv/bin/python -m src.simulation.cli live-smoke \
  --model 'openai/gpt-oss-120b' \
  --base-url 'https://api.groq.com/openai/v1' \
  --api-key-env 'GROQ_API_KEY' \
  --max-output-tokens 1024
```

## Schema and artifact paths

- Canonical benchmark: `data/benchmark/canonical_tasks.jsonl`
- Agent-safe views: `data/benchmark/agent_views.jsonl`
- Mock batch configuration: `configs/phase2_mock_smoke.json`
- Trace contracts: `src/simulation/trace_schemas.py`
- Trace validator: `src/simulation/trace_validation.py`
- Development smoke traces: `data/development/traces/phase2_mock_smoke.jsonl`
- Development-trace warning: `data/development/traces/README.md`

New traces use schema `1.1` and include UTC start/finish timestamps. The four original append-only smoke rows remain readable schema `1.0` records and are intentionally not rewritten.

## Actual audit results

- Full automated suite: **82 passed, 0 failed**.
- Cross-condition/topology audit: **12/12 completed** across independent, clear, ambiguous, and omission conditions crossed with fully connected, ring, and star topologies.
- Audit-matrix trace validation: **3,597 checks passed**.
- Persisted smoke log: **4/4 valid traces**, **1,408 checks passed**, file mode `0600`.
- Persisted replay: **4/4 reproduced**, `model_calls_executed=0`.
- Phase 1 mechanical benchmark: 40 draft tasks and 200 private views; 649/649 mechanical checks previously pass in the full suite.
- Live provider: **user-reported success, not independently trace-verified**. Reported output: `task=MB_e8ed46b2e2ce70 agent=agent_1 model=openai/gpt-oss-120b belief=UNKNOWN` (the user supplied the task, agent, and belief; the model identifier is the configured request model). No raw response or trace artifact was supplied.

The deterministic evidence-echo mock returns `UNKNOWN`, so audited group outcomes are `ABSTAIN`. This is expected mock behavior and is not an RQ1/RQ3 finding.

## Phase 2 exit checklist

- [x] Canonical tasks load and produce exact private agent views.
- [x] Agent contexts are isolated; `YES`/`NO`/`UNKNOWN` and abstention are supported.
- [x] Fully connected, ring, and star routing are deterministic.
- [x] Round 0 is independent and same-round organic messages are collected before delivery.
- [x] Clear, ambiguous, and omission stimuli are separate, explicitly injected conditions.
- [x] Controlled and organic message provenance is distinct in audit records but hidden from participating agents.
- [x] Beliefs, recommendations, messages, prompts, configuration, model metadata, errors, and observed token usage are machine-readable.
- [x] Strict-majority aggregation, ties, and insufficient-majority abstention are tested.
- [x] Append-only JSONL traces validate and preserve global event order.
- [x] Replay recomputes outcomes from saved events and never calls a model.
- [x] Failed/malformed model calls are retained without fabricating a group outcome.
- [x] Unreviewed benchmark tasks are confined to development smoke traces and excluded from empirical claims.
- [x] User-reported single-agent Groq smoke returned a schema-valid result; independent trace verification remains outstanding.
- [x] Hash-pinned exploratory manifest exists for provisionally reviewed tasks.
- [ ] Fully human-certified frozen manifest — required only for confirmatory evaluation.

## Known limitations

1. No task is fully human-certified. The current state is 26 provisional summary approvals, four revised tasks awaiting renewed review, and 10 flagged tasks.
2. The live adapter has a user-reported successful Groq smoke, but no independently captured trace verifies it.
3. Trace files use owner-only permissions but are not encrypted; storage security depends on the host filesystem.
4. The append-only logger prevents duplicate episode IDs in one process but does not implement multi-process file locking.
5. Model calls execute sequentially. The round boundary is synchronous because delivery waits for all drafts, but API calls are not parallelized.
6. Selecting fewer than five canonical views is useful for engineering tests but may remove collectively sufficient evidence.
7. Configured transient retries are bounded and immediate; there is no exponential backoff or provider-specific rate-limit policy.
8. Replay reproduces saved-event computations, not stochastic language-model text.
9. No experimental statistics, cascade classification, source-influence estimate, dashboard, or Phase 3 code is included.

## Phase 3 gate

- **ENGINEERING:** explicitly authorized Phase 3 runner and mock work may use draft tasks.
- **EXPLORATORY:** explicitly authorized, budgeted live work may use `configs/phase3_exploratory_pilot_manifest.json`; every output must retain the non-confirmatory label and review risks.
- **CONFIRMATORY:** blocked until source records, evidence views, fact allocation, and ambiguity entailment are individually approved and a separate confirmatory manifest is frozen.
- No large paid batch is authorized by this handoff.

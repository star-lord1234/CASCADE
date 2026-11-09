# CASCADE — Phase 1 benchmark and Phase 2.3 simulation

This repository implements deterministic hidden-profile task generation,
structural validation, isolated model contexts, and the controlled synchronous
episode infrastructure through Phase 2.3, including append-only traces and
saved-event replay. It does not contain experimental analysis, paid batch
inference, or a dashboard.

## Setup and run

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python -m src.tasks.benchmark --seed 42 --out-dir data/benchmark
.venv/bin/python -m src.tasks.semantic_screening \
  --canonical data/benchmark/canonical_tasks.jsonl \
  --out-dir data/benchmark \
  --human-review-state data/benchmark/human_review_state.json
```

The active benchmark contains 40 independently generated deterministic tasks:
15 referential, 15 selective omission, 5 scope/quantifier, and 5 temporal.
Each canonical row contains the experimenter-only task, matched messages,
five safe private views, and generation provenance. See
`multiagent_ambiguity_bench.md` for the authoritative specification.

Mechanical validation does not certify pragmatic ambiguity or misleadingness.
All generated tasks remain development drafts with `needs_review` status. The
current review state records 26 summary-level provisional approvals, four
revised tasks awaiting renewed summary review, and 10 flagged tasks awaiting
individual review. All 40 still require source-record, allocation, evidence-view,
and ambiguity-entailment review before full human certification. Historical Adaption material is archived under
`data/archive/adaption/` and is not read by the generator or validator.

Risk-based semantic screening routes the 30 referential/omission drafts into
one batch-review CSV and flags the 10 scope/temporal drafts for individual
review. Low-risk routing and provisional summary approval are not full human
certification. Optional independent LLM screening
uses exported JSONL packets and imported schema-validated judgments; it never
changes solver ground truth or approves a task.

Pre-revision task versions are preserved in `data/benchmark/history/v2/`, and
the append-only successor mapping is recorded in `data/benchmark/revisions.jsonl`.

## Phase 2.1: safe loading and model primitives

`src/simulation/loader.py` strictly loads canonical JSONL, verifies each private
view against its exact evidence allocation, and exposes safe per-agent contexts.
`src/simulation/agent.py` builds isolated prompts and rejects model replies that
cite unauthorized fact IDs or undelivered message IDs. Participating agents do
not receive ground truth, decision rules, ambiguity labels, other agents'
private evidence, or generation metadata.

`src/simulation/model_client.py` provides a deterministic request-keyed mock and
an OpenAI-compatible Chat Completions adapter. The live adapter reads its key
from a configured environment-variable name, supports JSON Schema or JSON
object response modes, and always validates the returned object locally. No
live inference is run by tests or repository commands.

Minimal mock usage:

```python
from src.simulation import DeterministicMockClient, IsolatedAgent, load_benchmark

catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl", expected_task_count=40)
task_id = catalog.task_ids()[0]
agent = IsolatedAgent(
    catalog.agent_context(task_id, "agent_1"),
    DeterministicMockClient(),
)
result = agent.probe(
    request_id="REQ_1",
    snapshot_id="B_1",
    episode_id="EP_1",
    round_index=0,
)
```

## Phase 2.2: synchronous communication and orchestration

`src/simulation/network.py` constructs deterministic fully connected, ring, and
star routing maps. A star center is structural and must be configured explicitly;
it is never labeled as a leader or given a different agent role.

`src/simulation/orchestrator.py` runs an independent Round 0 followed by a
configured number of synchronous communication rounds. In each round it:

1. Injects the configured controlled stimulus at the configured round, if any.
2. Collects every agent's natural outgoing-message draft without delivering any
   same-round organic message.
3. Routes and delivers the complete batch in stable sender order.
4. Collects private belief updates and computes the final strict-majority group
   decision, with ties, `UNKNOWN`-heavy results, and insufficient majorities
   returning `ABSTAIN`.

Controlled `clear`, `ambiguous`, and `omission` messages retain condition and
variant provenance in experimenter-side `RoutedMessage` records. Agent-facing
`DeliveredMessage` objects contain only sender, text, source references, parent
references, and public recommendation—not condition or variant labels.

Minimal deterministic episode:

```python
from src.simulation import (
    DeterministicMockClient,
    EpisodeConfig,
    load_benchmark,
    run_episode,
)

catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl", expected_task_count=40)
task_id = catalog.task_ids()[0]
agent_ids = catalog.agent_ids(task_id)[:3]
result = run_episode(
    catalog=catalog,
    task_id=task_id,
    episode_id="EP_SMOKE",
    config=EpisodeConfig(
        condition="ambiguous",
        topology="fully_connected",
        communication_rounds=1,
        agent_count=3,
        injection_round=1,
        stimulus_sender_id="agent_1",
    ),
    model_clients={agent_id: DeterministicMockClient() for agent_id in agent_ids},
)
```

## Phase 2.3: trace logging, replay, and CLI

Each traced episode is appended as one validated JSON object in a JSONL file.
Trace files are created with owner-only `0600` permissions. Existing rows are
never replaced, and duplicate episode IDs are rejected.

The trace records:

- benchmark hash, task/episode IDs, condition, topology, and agent selection;
- audit-only safe `AgentView` records, never full ground truth;
- model settings and exact safe prompts;
- parsed replies, observed token usage, and explicit model errors;
- globally ordered controlled/organic messages and their provenance;
- belief snapshots and the final group decision.

Run the checked-in one-task/four-condition mock configuration:

```bash
.venv/bin/python -m src.simulation.cli run-mock \
  --config configs/phase2_mock_smoke.json
```

The logger is append-only. Change the batch ID or output path before rerunning
the same configuration. Configurations may list 1–5 existing task IDs and any
subset of `independent`, `clear`, `ambiguous`, and `omission`.

Validate and replay a trace:

```bash
.venv/bin/python -m src.simulation.cli validate \
  --trace data/development/traces/phase2_mock_smoke.jsonl
.venv/bin/python -m src.simulation.cli replay \
  --trace data/development/traces/phase2_mock_smoke.jsonl
```

Replay consumes saved events only, recomputes the group result, and always
reports `model_calls_executed=0`. It is not a rerun of prompts and does not
pretend to reproduce stochastic model generations.

One optional live adapter smoke call can be made when the named environment
variable is configured:

```bash
OPENAI_API_KEY='<configured outside the repository>' \
  .venv/bin/python -m src.simulation.cli live-smoke \
  --model '<OpenAI-compatible model name>'
```

This performs one private Round 0 call, not a batch experiment. Never place the
key in a config file or commit it.

All 40 benchmark tasks remain development-only because full human semantic
certification is still pending. Mock traces demonstrate infrastructure behavior
only and must not be interpreted as RQ1/RQ3 findings.


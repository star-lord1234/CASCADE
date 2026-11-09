# CASCADE — Phase 2 Codex Prompts

**Phase:** Multi-Agent Simulation Infrastructure  
**Scope:** Engineering only. No RQ1/RQ3 conclusions or dashboard.  
**Standing context:** `AGENTS.md`, `project_bible.md`, `multiagent_ambiguity_bench.md` at repository root. These are authoritative; do not repeat project background in every prompt.

## Before you begin

1. Place this file at the repository root.
2. Confirm your revised Phase 1 benchmark is present and automated tests pass. Semantic review may remain incomplete; use such tasks only for engineering/smoke tests, **not** headline research results.
3. Run the prompts **sequentially in the same Codex workspace**. Ask Codex to report modified files, tests and unresolved issues after each step.
4. Do not commit API keys or change archived Adaption artifacts.

---

## Prompt 2.1 — Task loader, isolated agents and model interface

**Use in:** Codex. **Outcome:** Safe task loading and independently testable agent/model primitives.

```text
Read AGENTS.md, project_bible.md, and multiagent_ambiguity_bench.md. Implement Phase 2.1 only. First run the existing Phase 1 tests and check the revised benchmark; report unfinished semantic reviews but do not block engineering.

Build a strict benchmark loader, isolated per-agent contexts, a configurable OpenAI-compatible model client, a deterministic mock client, and validated schemas for private belief snapshots and messages. Agents see only their question, authorized evidence and delivered messages—never ground truth, ambiguity labels, other agents' private evidence, or experimental metadata. Support YES/NO/UNKNOWN, confidence, source evidence references and public recommendations. Ensure model replies are schema-checked and errors handled explicitly. Add unit tests for leakage prevention, parsing, serialization and mock behaviour.

Do not implement orchestration or run paid inference. Report files changed, test results, limitations and the next step.
```

**Acceptance checks:** Canonical tasks load; private views are properly isolated; malformed model responses fail safely; mock-client tests pass.

---

## Prompt 2.2 — Communication network and orchestration

**Use in:** Codex after 2.1. **Outcome:** Executable multi-agent episodes under controlled conditions.

```text
Implement Phase 2.2 using the existing primitives. Add deterministic synchronous rounds; independent Round 0 reasoning; configurable fully connected, ring and star topologies; sender/recipient routing; natural agent messages; separately tagged controlled clear/ambiguous/omission stimulus injection; belief updates; and a prespecified group aggregation rule with tie/abstention handling.

Collect each round's outgoing messages before delivery, preventing API completion order from changing who sees what. Keep per-agent contexts isolated and do not expose hidden task metadata. Make condition, injection timing, topology, rounds and agent count configurable. Use deterministic mock-agent integration tests for routing, delivery, belief transitions, condition separation, and group decisions.

No dashboard, statistical analysis, or paid batch runs. Report files changed, tests and limitations.
```

**Acceptance checks:** A full mock episode runs in all three message conditions; no premature delivery, leakage or implicit leader assignment.

---

## Prompt 2.3 — Trace logging, replay, CLI and smoke test

**Use in:** Codex after 2.2. **Outcome:** Reproducible, evaluation-ready execution traces.

```text
Complete Phase 2 with append-only JSONL logs capturing task and episode IDs, condition, agent views (stored securely for audit), network topology, prompts/model settings, event order, injected vs organic messages, senders/recipients, message provenance, belief snapshots, final group outcome, errors and token usage when available. Add trace validation, deterministic mock replay, and clear separation between replaying saved events and rerunning nondeterministic LLM calls.

Provide a CLI/config for running 1–5 tasks with mock agents under independent, clear, ambiguous and omission conditions. Add end-to-end tests and README instructions. After mock tests pass, perform at most one minimal live-model smoke test only if credentials are configured; otherwise give the exact command without requiring a secret. Do not infer scientific results from mock runs or use unreviewed tasks for final evaluation.

Run tests and report files changed, actual outputs, remaining issues and whether Phase 2 exit criteria are met. Do not start Phase 3.
```

**Acceptance checks:** Valid JSONL trace; reliable mock replay; live-model adapter tested if available; CLI works with existing task IDs.

---

## Optional Prompt 2.4 — Phase 2 audit and handoff

**Use in:** Codex only after 2.3, if you want a separate final audit before experiments.

```text
Audit Phase 2 against AGENTS.md and project_bible.md. Run the full test suite and a mock episode for every supported condition. Check ground-truth and private-evidence leakage, injection provenance, synchronization, belief logging, aggregation and replay semantics. Produce a concise PHASE2_HANDOFF.md with run commands, schema/trace paths, known limitations, test results and a pass/fail checklist. Make only necessary bug fixes; do not implement Phase 3.
```

---

## Phase 2 exit gate

- [ ] Task loader reads the canonical benchmark and constructs safe, private agent views.
- [ ] Independent model contexts; `UNKNOWN`/abstention handled.
- [ ] Synchronous rounds, reproducible routing and explicit controlled stimulus injection.
- [ ] Clear, ambiguous and omission conditions run as distinct configurations.
- [ ] Complete, machine-readable message and belief trajectories recorded.
- [ ] Mock replay reproduces saved events without pretending to reproduce stochastic model calls.
- [ ] Unit and end-to-end tests pass; one live-model smoke test succeeds where credentials are available.
- [ ] Unreviewed Phase 1 tasks remain excluded from final empirical claims.

**Then:** Move to Phase 3 (RQ1 experimental analysis) only after reviewing the pilot task subset and checking paired-condition reproducibility.

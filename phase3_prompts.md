# CASCADE — Phase 3 Codex Prompts

**Phase:** RQ1 — Ambiguity and information-cascade experiments  
**Research question:** How does ambiguity in communicated evidence affect incorrect belief adoption and consensus in multi-agent LLM networks?  
**Out of scope:** RQ3 source-influence interventions, training/fine-tuning, general failure-attribution systems, full dashboard.  
**Standing context:** `AGENTS.md`, `project_bible.md`, `multiagent_ambiguity_bench.md`, the current Phase 2 code and trace format. Read these locally rather than restating them in prompts.

## How to run this sequence

1. Put this file at the repository root. Run prompts **3.0 → 3.1 → 3.2 → 3.3 → 3.4** in Codex, one at a time. Prompts are short because project-wide requirements are already in `AGENTS.md` and `project_bible.md`.
2. Apply `research/execution_tiers.md`: drafts are ENGINEERING-only; hash-pinned provisionally reviewed tasks may support explicitly labeled EXPLORATORY pilots; only fully certified frozen tasks support CONFIRMATORY estimates. No task is automatically declared human-certified.
3. The project owner reports that a Groq live smoke succeeded with `openai/gpt-oss-120b` using `--base-url https://api.groq.com/openai/v1` and `--api-key-env GROQ_API_KEY`. Treat this as user-reported, not independently trace-verified. A single-agent smoke is **not** a full multi-agent live episode.
4. Before paid calls, require a dry-run budget estimate and explicit user authorization for the actual batch. Never print or persist API keys; never silently switch model/provider. Keep the same model and parameters across matched conditions.
5. Each prompt ends with a gate. Codex should report files changed, tests actually run, cost/request estimates or actual token use (when applicable), blockers and evidence for the gate. Do not start the next prompt automatically.

---

## Prompt 3.0 — Preflight: benchmark pilot + experimental contract

**Use in:** Codex. **Goal:** Approve a small, scientifically usable task subset and freeze the RQ1 comparison *before observing study results*.

```text
Start Phase 3.0 only. Read project instructions, benchmark, review state and Phase 2 handoff. Audit the current 40-task benchmark; do not infer human certification from provisional summary approvals. Build a compact, source-backed review queue for 10–15 diverse pilot tasks covering referential and omission types, plus scope/temporal where valid. Include full facts, five agent views, rule answer, exact clear/ambiguous/omission text, and entailment/decision-relevance checks. Flag any unresolved contradiction; never auto-certify. Provide a fast human-adjudication workflow and freeze only individually approved task IDs and content hashes into a versioned pilot manifest.

Write research/phase3_rq1_protocol.md with prespecified outcome definitions (incorrect consensus, incorrect adoption, cascade-like propagation, evidence coverage); primary clear-vs-ambiguous paired contrast; secondary omission contrast; fixed aggregation/UNKNOWN policy; injection timing, topology, rounds, repetitions, and exclusion rules. Define single-agent ambiguous-exposure and full-information checks to separate language misunderstanding from social amplification. No live batch, no RQ3, no result-driven protocol changes. Run tests and report the approval gate.
```

**Gate:** A versioned tier-labeled manifest exists and the main comparison and success/failure metrics are fixed. Exploratory manifests retain provisional status and risks; confirmatory estimates remain blocked until at least 10 tasks are fully approved in a separate confirmatory manifest.

---

## Prompt 3.1 — RQ1 runner and controlled-condition verification

**Use in:** Codex after 3.0. **Goal:** Ensure comparisons change only the intended experimental variable.

```text
Implement the Phase 3 RQ1 runner on existing Phase 2 infrastructure; reuse schemas, CLI and trace logger. Add paired conditions: independent/no communication, full-information single-agent control, individual ambiguous-exposure control, multi-agent clear, multi-agent ambiguous, and multi-agent omission. Keep the same task, evidence allocations, model/version, round limits, network and aggregation policy within each matched comparison. Inject one controlled message at a documented send/receive point; preserve naturally generated messages separately. Confirm the target receiver is actually exposed and do not leak ground truth or treatment labels into agent context.

Provide dry-run planning (task IDs × conditions × repetitions × expected model calls, token/cost estimate marked approximate, Groq rate-limit safeguards), resumable execution, failure records and unique condition IDs. Add deterministic mock tests verifying paired task identity, treatment isolation, exact exposure and no hidden evidence leakage. Do not call live APIs yet or build plots. Report the test gate.
```

**Gate:** Mock paired experiments produce validated traces with controlled condition differences and correct exposure. No live experimental claim yet.

---

## Prompt 3.2 — One complete live episode per condition

**Use in:** Codex after 3.1. **Goal:** Validate the *full* multi-agent live pipeline, not just one agent's API call.

```text
Perform a minimal Phase 3 live integration check on ONE task from the active tier-appropriate frozen manifest. First show the proposed model calls and confirm the live Groq configuration uses GROQ_API_KEY, https://api.groq.com/openai/v1, and openai/gpt-oss-120b. Do not execute paid calls without explicit user authorization. Once authorized, run one full multi-agent episode for clear and ambiguous conditions, plus the required comparison controls if within the approved budget; use identical settings and preserve complete traces. Validate JSON parsing, agent isolation, controlled stimulus delivery, belief updates, aggregation, error handling, token accounting and trace cross-references. If the manifest is exploratory, label all outputs `exploratory/non-confirmatory`. If a call fails, log the actual failed episode, do not fabricate completion or silently replace the model. Report observed issues and whether the end-to-end live gate passes. No efficacy conclusions from a single episode.
```

**Gate:** At least one actual complete live multi-agent episode validates end to end. Failed or unapproved live calls are not counted as a pass.

---

## Prompt 3.3 — RQ1 pilot execution and metrics

**Use in:** Codex after 3.2. **Goal:** Produce the first evidence for or against the RQ1 hypothesis.

```text
Run the prespecified RQ1 pilot ONLY on a frozen tier-appropriate manifest. Before live execution, print exact task/condition/repetition count and model-call/token/cost estimate; obtain explicit authorization for the run. Exploratory manifests yield exploratory/non-confirmatory outputs only; final estimates require the separate fully certified confirmatory manifest. Use the same Groq model, parameters, prompts, topology and evidence distributions across paired conditions; throttle/retry safely, never silently substitute models. Preserve all complete and failed episodes, raw traces, manifest hashes, prompts, response metadata and observed token usage. Separate independent/full-information/individual-exposure controls from the matched clear-vs-ambiguous vs omission comparison.

Implement src/analysis/cascades.py and metrics.py for group correctness, incorrect consensus, initial-to-final belief changes, per-exposure incorrect adoption, evidence coverage, and observed relay depth where message lineage is supported. Treat message order alone as association, not causal evidence. Label outcomes precisely: incorrect consensus, cascade-like propagation, or inconclusive; no causal cascade claims from traces alone. Export tidy episode-level and agent-round data and a run manifest. Do not edit benchmark/tasks or post-hoc redefine metrics.
```

**Gate:** Validated real-model traces for at least one paired reviewed pilot comparison; explicit missing/failed-call accounting and interpretable metric outputs. Null results are acceptable.

---

## Prompt 3.4 — Analysis, limitations and RQ1 handoff

**Use in:** Codex after 3.3. **Goal:** Turn the pilot into defensible, bounded research findings.

```text
Analyze the completed RQ1 pilot using the prespecified protocol. Compare matched clear vs ambiguous outcomes first, omission second; include individual ambiguous-exposure and independent-reflection baselines where available. Report task-level results, observed adoption/propagation patterns, effect sizes and uncertainty intervals suitable for the small paired sample; do not overstate significance. Flag confounds including prompt/template repetition, wording length, source-entity priors, task balance, UNKNOWN/abstention, model stochasticity, exposure mismatches and judge/review uncertainty. Select a few representative trajectories from actual logs with precise event IDs; do not invent a cascade example.

Create results/rq1_pilot_report.md and reproducible CSV/plots (simple figures, no dashboard), a traceability table from every finding to task/episode IDs, and research/phase3_handoff.md. State supported, unsupported and unresolved claims separately. Give a brief plan for expanding the sample or proceeding to RQ3 influence amplification without implementing RQ3. Run tests and summarize modified files, exact experiment counts, costs, limitations and next decision.
```

**Gate:** A self-contained RQ1 pilot report exists with authentic trace-backed findings, matched comparisons, uncertainty and explicit limits.

---

## RQ1 experiment contract (quick reference)

| Dimension | Primary design |
|---|---|
| Tasks | 10–15 version-frozen tasks at the declared tier; provisional for exploratory, fully certified for confirmatory |
| Agents | 5, identical base role, isolated private contexts |
| Baselines | Independent, full-information, individual ambiguous exposure |
| Primary conditions | Multi-agent complete/clear vs matched ambiguous |
| Secondary condition | Matched selective omission where semantically applicable |
| Topology | One fixed topology initially (e.g., fully connected); alternatives are robustness checks |
| Outcome | Final group correctness / incorrect consensus under prespecified aggregation |
| Mechanism measures | Belief flips, exposed-agent incorrect adoption, evidence coverage, supported relay chains |
| Interpretation | Incorrect consensus ≠ information cascade; evidence of copying ≠ established causality |
| Model | One pinned, accessible Groq model for all compared conditions; log provider/model/version and params |

### Critical operational cautions

- **No automatic human approval:** passing 649 mechanical checks, 81 tests, or an LLM semantic screen does not certify factual entailment or natural ambiguity. Review decisions and provenance stay explicit.
- **No outcome selection bias:** don't keep only scenarios that make agents fail; valid ambiguity tasks where agents resist the error are equally important.
- **Truthful but incomplete:** selective omission must be factually supported and omit decision-relevant context, but need not be covertly persuasive.
- **Measured belief is a model report:** do not describe structured output as direct access to internal mental states.
- **Reproducibility:** saved-event replay is exact event playback, not a promise that new live calls will be deterministic.
- **Rate limits and costs:** no uncontrolled concurrent jobs, no key logging, and no bulk calls without a dry-run estimate and approval.
- **RQ3 separation:** source influence and emergent leadership are next-phase questions, not explanatory claims inferred from RQ1 alone.

## Phase 3 exit checklist

- [ ] Prespecified RQ1 protocol and frozen tier-labeled pilot manifest.
- [ ] Paired-condition mock checks and a full live multi-agent test pass.
- [ ] Approved live pilot run executes with complete trace validation and failure accounting.
- [ ] Clear vs ambiguous primary contrast reported; omission contrast reported where valid.
- [ ] Single-agent baseline distinguishes misunderstanding from communication amplification.
- [ ] Incorrect consensus, belief adoption and cascade-like propagation are not conflated.
- [ ] Actual episode IDs support every example or case study.
- [ ] Effect sizes, uncertainty, limitations and next actions documented.

**After Phase 3:** Decide whether to expand/replicate RQ1 or begin controlled RQ3 source-influence experiments. Do not automatically proceed.

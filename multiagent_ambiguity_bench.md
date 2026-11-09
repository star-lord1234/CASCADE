# CASCADE Multi-Agent Ambiguity Benchmark

**Status:** Phase 1 mechanically validated draft, semantic review pending  
**Schema version:** 2.0  
**Generator:** `cascade_deterministic_benchmark` version 1.0  
**Canonical seed:** 42  
**Authority:** This document is the authoritative specification for the active Phase 1 benchmark. `project_bible.md` remains authoritative for the broader research design.

## 1. Motivation

CASCADE studies whether literally defensible but ambiguous or selectively incomplete messages can lead distributed agents toward an incorrect collective decision, and whether source influence amplifies adoption. The benchmark isolates task construction from model behavior: atomic facts and decision rules determine ground truth, while controlled message templates manipulate what a recipient may infer.

The active benchmark is independently generated. It does not use, paraphrase, transform, select, or derive content from Adaption or another generative service. Historical Adaption exports and audits are retained only under `data/archive/adaption/` for provenance and are excluded from all active code paths and outputs.

## 2. Phase 1 boundary

This repository currently provides task schemas, deterministic generation, evidence allocation, message construction, exports, validation, tests, and a semantic-review queue. It does **not** provide a swarm runner, model client, RQ1/RQ3 execution, causal attribution, dashboard, fine-tuning, or downstream statistical analysis.

The 40 tasks are a development-stage draft pool. They are not a frozen evaluation set and are not eligible for experimental claims until human semantic review is complete. A future 10–15 task pilot must be selected only from approved items.

## 3. Design principles

1. **Deterministic-first truth:** structured facts and executable constraints are the only source of the answer.
2. **Hidden-profile evidence:** every task has five private views; at least two rule facts are necessary; no private view contains all rule facts; combined evidence is sufficient.
3. **Matched treatments:** complete, ambiguous, and selective-omission messages are generated from the same facts and linked by explicit source and qualifier IDs.
4. **Explicit interpretation contract:** each task records a defensible interpretation, a misleading interpretation, an intended incorrect answer, and fact overrides that mechanically reproduce that wrong answer.
5. **Controlled language:** prose is emitted from repository-owned templates, not generated or labeled by an LLM.
6. **Privacy boundary:** `TaskDefinition` contains experimenter-only truth and rules; `AgentView` contains only the question, options, authorized evidence, and abstention instructions.
7. **Draft semantics:** fact-level claims and solver consistency are mechanically checked; pragmatic truthfulness, ambiguity strength, misleadingness, and naturalness remain human judgments.
8. **Artifact resistance:** opaque task IDs are content-independent hashes; correct answers are balanced 21 YES / 19 NO; source blueprint IDs never enter agent-facing views.

## 4. Benchmark composition

The generator produces exactly 40 unique tasks:

- 15 referential ambiguity tasks
- 15 selective omission tasks
- 5 scope/quantifier ambiguity tasks
- 5 temporal ambiguity tasks

### 4.1 Referential ambiguity

Two fictional entities share a shortened surface form, but only one is the decision target. The ambiguous message truthfully reports the non-target entity's decisive property. The misleading interpretation assigns that property to the target and changes the answer.

### 4.2 Selective omission

A true message reports preliminary checks or a recorded issue while omitting a decisive qualification. Negative-ground-truth tasks omit a failed requirement; positive-ground-truth tasks mention an issue but omit that it was resolved. The omitted fact is explicit and the counterfactual interpretation produces the opposite answer.

### 4.3 Scope and quantifier ambiguity

Mandatory items pass and an optional item fails. “All tests did not pass” is mechanically supported under a wide-scope-negation interpretation, while a distributive reading suggests every mandatory test failed. The solver depends only on the mandatory items and a complete record. Human review must assess whether the scope ambiguity is natural enough for use.

### 4.4 Temporal ambiguity

Each task stores typed integer decision, deadline, and historical times plus status at both observations. The ambiguous message reports the historical status without a time anchor. Applying that earlier status to the decision time produces the opposite answer. Ordered temporal constraints never compare strings.

## 5. Canonical schemas

### 5.1 `TaskDefinition`

Contains the opaque task and variant-group IDs, domain, declared canonical entity IDs, question, answer options, atomic facts, executable `all_constraints` rule, stored solver answer, required and decisive fact IDs, evidence allocation, and seed. Atomic facts link a fact ID to an entity ID, predicate, scalar value, and controlled evidence sentence.

### 5.2 `MessageVariantGroup`

Contains the ambiguity category and category-specific contract, full source-fact set, decisive qualifier IDs, intended incorrect inference and answer, explicit counterfactual fact overrides, three matched variants, and semantic-review state.

Each `MessageVariant` includes text, type, source facts, omitted facts, structured truth constraints, interpretations where relevant, and—only for the complete control—the recommended answer.

### 5.3 Category-specific contracts

- `ReferentialAmbiguityContract`: ambiguous surface, defensible entity, misleading target entity.
- `OmissionAmbiguityContract`: exact omitted qualifier fact IDs.
- `ScopeAmbiguityContract`: quantifier plus defensible and misleading entity scopes.
- `TemporalAmbiguityContract`: typed time unit and fact IDs for defensible and misleading reference times.

### 5.4 `AgentView`

Contains only schema version, task ID, agent ID, question, options, authorized natural-language evidence, and instructions permitting `UNKNOWN`. It excludes ground truth, decision rules, condition labels, ambiguity annotations, provenance, and other agents' facts.

### 5.5 `GenerationProvenance`

Records source kind `independent_programmatic`, generator ID/version, unique blueprint ID, controlled template ID, seed, development split, and an empty external-content dependency list.

## 6. Deterministic generation

Run:

```bash
.venv/bin/python -m src.tasks.benchmark --seed 42 --out-dir data/benchmark
```

Generation proceeds in a fixed blueprint order. Task and variant-group IDs are stable SHA-256-derived opaque identifiers. Facts are instantiated first, the rule is evaluated over those facts, and only then is the stored answer written. Evidence is shuffled with a seed derived from the global seed and blueprint ID; allocation retries deterministically until no private view contains every rule fact.

Message text is instantiated from category-specific controlled templates. Structured truth constraints accompany each message. The intended misleading interpretation is represented as explicit fact overrides; applying those overrides must yield the stored intended incorrect answer.

## 7. Worked example

For the grant task `MB_e8ed46b2e2ce70`, Northstar Analytics is the target and Northstar Robotics is the non-target. Both baseline and record checks for the target pass, but the target did not complete the decisive audit. Robotics did complete it. The solver therefore returns `NO`.

- Complete: “Northstar Analytics passed the baseline and record checks and did not complete the required audit; Northstar Robotics completed the required audit. Therefore the answer is NO.”
- Ambiguous: “Northstar completed the required audit.”
- Omission: “Northstar Robotics completed the required audit.”
- Defensible interpretation: “Northstar” denotes Northstar Robotics.
- Misleading interpretation: “Northstar” denotes the target, Northstar Analytics.
- Counterfactual check: replacing the target audit fact with Robotics' value makes the solver return `YES`, the intended incorrect answer.

This mechanical result does not certify that human reviewers will find the shortened referent natural or the misleading interpretation sufficiently plausible.

## 8. Validation procedure

`src/tasks/benchmark_validators.py` performs 16 checks per task plus 9 dataset checks, for 649 checks total.

### 8.1 Mechanically verified

- Pydantic schema validity and fact/entity/task/group references
- Unique, non-`UNKNOWN` solver answer from complete facts
- Reproduction of stored ground truth by executable constraints
- At least two decision-relevant facts
- Exactly five private views, complete combined coverage, and no all-facts private view
- Agent-view field isolation and authorized-evidence equality
- Structured fact-level truth conditions for complete, ambiguous, and omission messages
- Exact message source-fact provenance and decisive omission references
- Intended answer differs from ground truth and is reproduced by explicit counterfactual overrides
- Complete-control recommendation and wording agree with the solver
- Category-specific ambiguity contract presence and integrity
- Unique task, group, blueprint, and content fingerprints
- Exact 15/15/5/5 family distribution, answer balance, domain diversity, deterministic seed, and development-only split

### 8.2 Pending human review

- Whether each natural-language statement remains literally true under ordinary interpretation
- Whether the defensible interpretation is genuinely available rather than contrived
- Whether the intended misleading interpretation is plausible and strong enough to influence a recipient
- Whether complete, ambiguous, and omission wording is matched for tone, length, and specificity
- Whether evidence phrasing creates unintended answer, domain, or template artifacts
- Whether the five-agent evidence split is experimentally natural, not merely structurally sufficient

No task is labeled semantically validated. Every review field begins as `pending`, and all variant groups remain `needs_review`.

## 9. Negative tests

The automated suite includes explicit regressions for failures discovered in the retired pipeline:

- facts referring to undefined entities
- colliding source blueprint IDs
- empty or malformed quantifier scopes
- ordered temporal comparisons over strings
- private evidence allocations that give one agent every required fact
- full-context controls recommending an answer inconsistent with the solver

The suite also retains deterministic regeneration, solver, allocation, privacy, malformed JSONL, schema, and variant-consistency tests.

## 10. Exports

- `data/benchmark/canonical_tasks.jsonl` — 40 complete experimenter-only `TaskArtifact` rows
- `data/benchmark/agent_views.jsonl` — 200 standalone safe `AgentView` rows
- `data/benchmark/validation_report.json` — aggregate and per-task mechanical results
- `data/benchmark/semantic_review.csv` — one human-review row per task
- `multiagent_ambiguity_bench.md` — this specification and catalogue

All active exports are regenerated from code. Archived external candidates are not loaded, compared, sampled, or transformed.

## 11. Metrics enabled by the benchmark

Phase 1 does not compute experimental outcomes, but the task contract supports later preregistered measures from `project_bible.md`: collective accuracy, incorrect consensus, incorrect adoption, correct-to-wrong and wrong-to-correct belief flips, cascade reach/depth, evidence coverage, qualifier loss, source adoption effects, ambiguity-by-influence interaction, and intervention recovery. `UNKNOWN` must remain separate from an incorrect answer.

## 12. Intended RQ1 and RQ3 use

For RQ1, future infrastructure should compare the same approved task and allocation under complete, ambiguous, and selective-omission communications. Independent and full-information controls remain separate from the matched message comparison.

For RQ3, future infrastructure should hold task, message text, timing, and exposure fixed while randomizing a neutral versus credibly established source. The benchmark itself does not assign credibility, run agents, or claim an influence effect.

No experiment should use these draft tasks until semantic review approves the exact message group. Source influence must never be conflated with centrality, speaking frequency, formal authority, or competence.

## 13. Limitations

- Controlled templates improve auditability but may create repeated linguistic structure.
- Mechanical claim checks validate explicit structured propositions, not every pragmatic implication of prose.
- The five scope tasks use one negation/quantifier pattern and may require broader human-authored variation.
- Temporal tasks use integer minutes for safe computation, which abstracts away calendar and timezone complexity.
- The 40-task pool is balanced by answer but not yet calibrated for model difficulty.
- Domain realism is fictional and rule-based; it should not be generalized to real medical, legal, financial, or safety decisions.
- Semantic approval, full-information model feasibility, and pilot variance remain outstanding.

## 14. Task catalogue

All catalogue entries are mechanically valid drafts with semantic review pending.

| # | Task ID | Domain | Category | Solver answer | Decision question |
|---:|---|---|---|:---:|---|
| 1 | `MB_e8ed46b2e2ce70` | grant eligibility | referential ambiguity | NO | Should Northstar Analytics receive the Horizon grant? |
| 2 | `MB_d5206eff852e18` | incident closure | referential ambiguity | YES | May the Atlas Gateway incident be closed? |
| 3 | `MB_482ca9361ba403` | permit compliance | referential ambiguity | NO | Is Cedar Center North compliant with the operating permit rule? |
| 4 | `MB_9ec316c2d7ff71` | research selection | referential ambiguity | YES | Should Nova Coastal be selected for the research program? |
| 5 | `MB_f9e21e8df61435` | satellite clearance | referential ambiguity | NO | Should Orion Relay receive transmission clearance? |
| 6 | `MB_80996387a0137c` | warehouse dispatch | referential ambiguity | YES | Should Meridian East dispatch the emergency shipment? |
| 7 | `MB_97d92fb026f19e` | trial evaluation | referential ambiguity | NO | Should Lumen Alpha advance to the next trial stage? |
| 8 | `MB_21846374ba0e74` | school procurement | referential ambiguity | YES | Should Pine Ridge School receive the equipment order? |
| 9 | `MB_6b778c15634e9a` | marine inspection | referential ambiguity | NO | Should Harbor One receive sailing clearance? |
| 10 | `MB_a0058038f4d4a9` | datacenter failover | referential ambiguity | YES | Should traffic remain on Aurora Core? |
| 11 | `MB_49ce9657a6cda5` | rail maintenance | referential ambiguity | NO | Should Summit Line reopen for service? |
| 12 | `MB_5ffc2f0f863732` | insurance claims | referential ambiguity | YES | Should the Beacon Home claim be paid? |
| 13 | `MB_3a329f2a05491d` | energy projects | referential ambiguity | NO | Should Solace Solar receive grid approval? |
| 14 | `MB_7d06553adfd548` | airport gates | referential ambiguity | YES | Should Crescent Gate A open for boarding? |
| 15 | `MB_04e318d687abff` | food safety | referential ambiguity | NO | Should Meadow Plant release the production batch? |
| 16 | `MB_52eef22c193aa8` | vendor approval | selective omission | NO | Should Ember Supply be approved as a vendor? |
| 17 | `MB_fb428975faa243` | medication dispensing | selective omission | YES | Should the Caldra prescription be dispensed? |
| 18 | `MB_f84b52352800d4` | loan underwriting | selective omission | NO | Should the Juniper loan be approved? |
| 19 | `MB_7a8770e34f9507` | access control | selective omission | YES | Should the Keystone access request be granted? |
| 20 | `MB_b8ab36e84d7bcf` | bridge operations | selective omission | NO | Should Silver Bridge open to traffic? |
| 21 | `MB_172d7c88b0afc0` | claim payment | selective omission | YES | Should the River claim be paid? |
| 22 | `MB_396c78bb425b95` | software release | selective omission | NO | Should the Vertex release enter production? |
| 23 | `MB_df3bcb6b44ad99` | cargo clearance | selective omission | YES | Should Tide cargo receive loading clearance? |
| 24 | `MB_8152ca77a9f7c2` | hiring decision | selective omission | NO | Should the Alder candidate receive an offer? |
| 25 | `MB_449b417cca0a77` | water quality | selective omission | YES | Should Delta Reservoir return to service? |
| 26 | `MB_b24c2d9d0f58e3` | drone flight | selective omission | NO | Should the Kestrel drone launch? |
| 27 | `MB_a8d471a8ca045c` | invoice payment | selective omission | YES | Should the Opal invoice be paid? |
| 28 | `MB_268c0f4458c096` | laboratory access | selective omission | NO | Should the Quartz laboratory request be approved? |
| 29 | `MB_c5cc056589b5a9` | route approval | selective omission | YES | Should the Willow route be approved for the convoy? |
| 30 | `MB_9c492c32b1e544` | records retention | selective omission | NO | Should the Mosaic archive transfer proceed? |
| 31 | `MB_1701d7e6a17dbb` | quality control | scope/quantifier | YES | Should Batch Elm be released? |
| 32 | `MB_8b16a9d5a3d7dc` | project completion | scope/quantifier | YES | Should Project Iris be marked complete? |
| 33 | `MB_0b4bd44f4e22f2` | compliance audit | scope/quantifier | YES | Should the Lake audit be accepted? |
| 34 | `MB_2f21f7ce15cf87` | trial readiness | scope/quantifier | YES | Should the Prairie trial advance? |
| 35 | `MB_a292f5d33b1746` | fleet certification | scope/quantifier | YES | Should the Maple fleet be certified? |
| 36 | `MB_49307215f599c8` | certificate validity | temporal ambiguity | NO | Is the Cobalt certificate valid at the decision time? |
| 37 | `MB_7bb0c9d8ab42ee` | service recovery | temporal ambiguity | YES | May the Drift service incident close at the decision time? |
| 38 | `MB_48cc49b4a0476f` | permit window | temporal ambiguity | NO | Is the Fern permit active at the decision time? |
| 39 | `MB_8e69dfd30d7012` | inventory release | temporal ambiguity | YES | May Glacier inventory be released at the decision time? |
| 40 | `MB_9ad6958883eedc` | patch readiness | temporal ambiguity | NO | Should the Horizon patch deploy at the decision time? |

## 15. Risk-based semantic screening

Run:

```bash
.venv/bin/python -m src.tasks.semantic_screening \
  --canonical data/benchmark/canonical_tasks.jsonl \
  --out-dir data/benchmark \
  --human-review-state data/benchmark/human_review_state.json
```

The workflow separates validity from misleadingness and evaluates each condition by function:

- **Complete:** factually entailed, contains no omitted facts, and recommends the solver answer.
- **Ambiguous:** factually entailed under an explicit interpretation, has a mechanically represented alternative reading, and that reading changes the decision to the intended wrong answer.
- **Omission:** factually entailed, omits a decisive qualifier, and the omitted qualification is decision-relevant. An omission is not rejected merely because it explicitly names its source or would not independently fool a careful reader.

Deterministic screening checks factual claim constraints, referent/scope/time contracts, counterfactual decision relevance, and evidence sufficiency. It routes tasks into `low_risk_pending_human` and `flagged_pending_human`; neither status is approval.

Optional independent LLM screening is provider-neutral and offline by default. `llm_judge_packets.jsonl` contains screening packets, and `llm_judgment_schema.json` defines accepted results. Pass one or more JSONL files with repeated `--judgments`. Agreement is reported, but a judge cannot alter ground truth or set human approval. No API call is made by the repository.

Review outputs:

- `semantic_review_table.md` — compact 40-task status table
- `low_risk_batch_review.csv` — single batch interface for low-risk tasks
- `flagged_review.md` — detailed individual review for flagged tasks
- `semantic_screening.json` — condition checks, risks, agreement, and diversity analysis
- `review_workflow_manifest.json` — canonical hash and history pointer

Deterministic routing places 30 tasks in the low-risk batch and flags 10 scope/temporal tasks for individual review. After summary review, 26 low-risk tasks are provisionally approved, four revised tasks await renewed summary review, and the 10 flagged tasks remain pending. These judgments do not certify source records, evidence allocation, evidence views, or ambiguity entailment; all 40 remain pending full human review.

## 16. Template diversity and systematic risk

The 40 tasks use 40 domains and 40 surface-distinct ambiguous messages, but only nine template/answer structural signatures after the four revisions. This creates several systematic risks:

- All five scope tasks use the same marked “all … did not” construction and all have answer `YES`, producing category/answer confounding.
- All temporal tasks use the same historical-versus-current-status pattern, and past tense may reveal the defensible reading.
- Referential tasks cover shared-name-prefix ambiguity only; pronouns, role descriptions, and discourse anaphora are absent.
- Omission tasks remain concentrated in two answer-polarity patterns, although three revised resolved-issue tasks now add decision-relevant historical context.
- Complete controls explicitly state the answer and are systematically longer than treatments.
- Evidence allocation is structurally sufficient but not modeled around realistic organizational roles.

These weaknesses do not invalidate every task, but they limit benchmark diversity and may create learnable condition artifacts. They must be addressed before a frozen evaluation set is claimed.

## 17. Review and release gate

A reviewer may adjudicate all low-risk rows as one batch using `low_risk_batch_review.csv`, while flagged tasks require individual decisions in `flagged_review.md`. Approval still requires confirming literal truth, a defensible interpretation where applicable, decision relevance, natural evidence distribution, and no accidental clue. Omission approval does not require covert misleadingness. Rejected items remain recorded; revisions create new blueprint versions and new task IDs rather than silently changing a treatment.

Only fully reviewed tasks may enter a pilot. The benchmark may be described as **mechanically validated** when all automated checks pass, but never as **semantically validated** while any relevant human-review field is pending. Summary-level provisional approval is recorded separately and cannot satisfy this gate.

## 18. Provisional review and revision history

The 2026-11-08 batch review provisionally approved 26 low-risk summaries and requested revisions to task ordinals 3, 17, 21, and 29. Tasks 19, 23, 25, and 27 are retained as valid low-strength omission candidates; misleading strength is not an approval condition for them. The four revisions received new blueprint and task IDs and remain pending renewed summary review.

The complete pre-revision artifacts are preserved in `data/benchmark/history/v2/`. `data/benchmark/revisions.jsonl` records each old-to-new task mapping, reason, structured change, and approval effect. `data/benchmark/human_review_state.json` records the limited basis of the current judgments and keeps source-record, evidence-view, and ambiguity-entailment review pending for every task.

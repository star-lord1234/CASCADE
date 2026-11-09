# CASCADE — Phase 1 Prompt Playbook

Use these in order. `AGENTS.md` belongs at the **repository root** alongside `project_bible.md`. Codex convention uses uppercase **AGENTS.md**; use that exact filename. Prompts are intentionally short because Codex can read the standing instructions.

## Step 0 — Codex: set up shared context (once)

Place `AGENTS.md` and `project_bible.md` at the repository root. If not yet copied, paste/attach them into the repo first.

**Prompt (Codex):**

> Read `AGENTS.md` and `project_bible.md`. Set up only Phase 1. Audit existing files, propose the smallest file plan, and flag contradictory requirements. Do not code yet. Return a checklist of deliverables and acceptance tests in ≤20 lines.

**Output:** Short implementation plan confirming scope and file layout.

## Step 1 — Codex: build canonical schemas + deterministic ground truth

**Prompt (Codex):**

> Implement the Phase 1 canonical models, deterministic hidden-profile task generator, solver, evidence allocator, agent-view exporter, and pytest tests following `AGENTS.md`. Start with referential and omission-friendly task templates. Generate 5 seed-fixed example tasks; ensure combined facts uniquely solve each task and individual views do not leak hidden facts or labels. Expose `python -m src.tasks.generator --count 5 --seed 42 --out data/development/tasks.jsonl` or document the equivalent runnable command. Run tests and report results. No Adaption integration or LLM calls yet.

**Output:** Executable schema/solver/generator, 5 inspectable tasks, tests, exact command.

## Step 2 — Adaption: generate *candidate prose*, not labels

**Where:** Adaption dataset-generation UI (Invent-a-Dataset or equivalent). Ask for **20 candidate scenario/message groups** initially. Request JSONL/JSON export if supported; otherwise export structured rows. Do not spend heavily on large batches.

**Prompt (Adaption):**

> Create 20 **fictional** distributed-information decision scenarios for a multi-agent ambiguity benchmark. Prioritize: 8 referential ambiguity, 8 selective omission, 2 scope, 2 temporal. Each scenario must have (a) objective task/question; (b) 4–7 atomic facts in structured key/value form; (c) an explicit deterministic rule for the correct decision; (d) a decision-critical qualifier; (e) three matched messages from the SAME facts: `complete`, `ambiguous` (literally defensible under an explicit interpretation), and `selective_omission` (true but missing decision-relevant context); (f) the likely wrong inference and why it is unsupported. Use distinct realistic fictional entities. Vary which answer is correct. Output one JSON object per scenario with keys `scenario_id`, `domain`, `question`, `atomic_facts`, `decision_rule`, `critical_qualifier`, `message_variants`, `likely_wrong_inference`, `notes_for_human_review`. Do NOT supply authoritative `ground_truth` or `validated` flags; all outputs are unverified candidates. Avoid harmful real-world allegations, invented citations, and unqualified false statements labeled as true.

**Output:** Export a raw file, e.g. `data/raw/adaption_candidates.jsonl`, retaining the original unchanged.

**Note:** The exact UI names, availability, pricing, and export formats depend on your account. If an export is not possible, manually save the generated response as JSONL/JSON. Never assume promotional credits cover unrelated inference providers.

## Step 3 — Codex: ingest, formalize, reject and review

**Prompt (Codex):**

> Ingest `data/raw/adaption_candidates.jsonl` as untrusted suggestions. Build a conversion/validation pipeline to canonical schemas with an explicit review queue and rejection reasons. Deterministically rederive ground truth from parsed structured facts; never trust Adaption answer labels or self-reported truth status. Validate matched variants, fact references, unique answers, hidden-profile evidence allocation, split separation and agent-view privacy. If a candidate cannot be safely formalized or semantically certified, mark `needs_review`/`rejected`, don't fabricate certainty. Produce `data/development/candidates_review.csv`, `data/development/accepted_draft.jsonl`, and a summary by failure reason. Add negative pytest fixtures and run tests.

**Output:** Validated structural subset + human-review queue and rejection diagnostics. No semantic claims without review.

## Step 4 — Adaption: targeted repairs/paraphrases (only if needed)

**Where:** Adaption web UI. Supply **only the rejected/weak examples** and the relevant rejection reasons, not the full project Bible.

**Prompt (Adaption):**

> Revise ONLY the provided CASCADE candidate examples. Preserve the underlying objective facts and decision rule. For each example, fix the listed issue: [PASTE REJECTION REASON + CANDIDATE]. Return 2 alternate phrasings for the ambiguous message and 1 explicit full-context control. Every alternative must map to the same source facts, state which interpretation makes it literally true, and identify the omitted qualifier or likely incorrect inference. Do not invent additional facts or mark any result validated. Return structured JSON objects.

**Output:** `data/raw/adaption_revisions.jsonl`. Skip this step entirely if sufficient candidates survive review.

## Step 5 — Codex: finalize reviewed pilot + freeze test dataset

After reviewing the candidates yourself, fill the review status/notes in `candidates_review.csv` (or an equivalent review file), explicitly approve only the semantically sound examples.

**Prompt (Codex):**

> Finalize the Phase 1 pilot from human-approved candidate IDs only. Export canonical `TaskDefinition`, matched message variants, and safe `AgentView` JSONL; split into development/pilot with fixed seeds and a manifest recording provenance, schema version, ambiguity category, source export, and reviewer decisions. Target 10–15 pilot tasks, but report shortfall rather than padding with unreviewed data. Run full pytest suite, determinism tests, leakage tests, and a CLI validation report. Print exact paths, counts by type/split, pass/fail reasons, and unresolved review items. Do not start the swarm or paid inference.

**Output:** Phase 1 reproducible dataset and quality report ready for Phase 2.

## Minimal acceptance checklist

- [ ] Each task has executable ground truth with one correct decision from combined evidence.
- [ ] Private views contain only authorized facts, permit `UNKNOWN`, and never expose labels.
- [ ] Complete/ambiguous/omission variants reuse identical underlying facts and keep provenance.
- [ ] Entailment is not asserted by model self-report; doubtful semantics remain flagged.
- [ ] Deterministic generation and dataset split isolation are tested.
- [ ] Five human-inspectable examples and 10–15 pilot tasks exist, or shortfall is documented.
- [ ] Validated items have explicit human review; raw Adaption candidates remain archived.

## Suggested minimal command workflow

```bash
python -m pytest -q
python -m src.tasks.generator --count 5 --seed 42 --out data/development/tasks.jsonl
# After exporting candidate JSONL from Adaption into data/raw/:
python -m src.tasks.validators --input data/raw/adaption_candidates.jsonl
```

The commands are target interfaces for Codex to implement, not claims that the scripts already exist.

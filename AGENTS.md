# CASCADE — Agent Instructions (All Phases)

## Source of truth
- Read `project_bible.md` for the full research design and `multiagent_ambiguity_bench.md` for the authoritative Phase 1 benchmark contract. If they conflict, surface the conflict, do not silently decide.
- CASCADE studies whether **literally true but ambiguous or selectively incomplete messages** lead to incorrect collective beliefs (RQ1), and whether source influence amplifies adoption (RQ3). *Naro va Kunjaro va* is inspiration only.
- These instructions apply across all CASCADE phases. Phase-specific prompts and explicit user instructions determine which work is currently authorized.

## Phase governance
- Current active phase: **Phase 3 — RQ1 ambiguity experiments**, limited to the explicitly requested subphase or action. Do not infer authorization for later prompts, RQ3, or a larger batch.
- A phase or subphase transition requires explicit user instruction. This file records standing safeguards; it must not be used to block an explicitly authorized transition merely because an older handoff names a previous phase.
- Use three execution tiers:
  - **ENGINEERING:** mechanically valid draft tasks, deterministic mocks, schema/runner tests, and development traces only. No live efficacy claims.
  - **EXPLORATORY:** only hash-pinned tasks with recorded provisional review may be used for budgeted live pilots. Results must be labeled exploratory/non-confirmatory and cannot be reported as final estimates.
  - **CONFIRMATORY:** only fully semantically reviewed, individually approved, version-frozen tasks may support confirmatory evaluation or headline findings.
- Full human certification is required for CONFIRMATORY work, not for ENGINEERING or explicitly authorized EXPLORATORY work. Never silently promote a task between tiers.
- Paid API calls still require a dry-run request/token/cost estimate and explicit user authorization for the actual run. A phase transition alone does not authorize spending.

## Benchmark and experiment contract
- Core paradigm: synthetic **hidden-profile decisions** with discrete, objectively computable answers. Prioritize **referential ambiguity** and **selective omission**; scope/quantifier and temporal variants are secondary.
- Construct canonical tasks from structured facts + executable decision rules; compute ground truth with a deterministic solver. Never use generated prose or a model answer as the source of truth.
- Generate **matched** message variants for the *same* task/facts: `complete`, `ambiguous`, `selective_omission`; optional `explicit_falsehood` as separate positive control. Track variant group, source facts, intended misleading inference, decisive qualifiers, and truth/entailment status.
- An ambiguous variant must be *defensible under at least one explicit interpretation*, not secretly a false assertion. Omission variants must be entailed by known facts yet omit decision-relevant qualifications. Distinguish semantic ambiguity, pragmatic omission, and falsehood in labels.
- Separate `TaskDefinition` (experimenter-only ground truth and all facts) from `AgentView` (question + authorized evidence only). No correct answers, hidden facts, condition names, or annotations in agent-facing text.
- Agent-local knowledge can be insufficient: `UNKNOWN`/abstention is permitted. The *combined* complete evidence must imply a unique non-UNKNOWN answer; do not force a privately underinformed agent to guess.
- Avoid accidental artifacts: task IDs, names, evidence counts/order, templates, and labels must not reveal the correct option. Balance correct options and misleading interpretations where possible.
- Preserve isolated agent contexts in every simulation phase. Participating agents may receive only their question, authorized evidence, and messages explicitly delivered to them; never expose experimenter ground truth, ambiguity labels, condition metadata, other agents' private evidence, or scoring annotations.
- Keep controlled stimuli, organically generated messages, private belief snapshots, and public recommendations distinct in schemas and provenance. Never present injected content as if an agent generated it.
- Treat reported confidence, beliefs, recommendations, and message relays as observable outputs, not privileged access to internal psychological states or proof of causation.
- Do not describe incorrect consensus as an information cascade unless the prespecified propagation or intervention evidence supports that claim.

## Implementation requirements
- Python 3.11+, Pydantic, pytest, standard JSON/JSONL, deterministic seeds. Use small modules and a CLI, not a large framework.
- Prefer `src/tasks/{schemas,generator,ambiguity,allocator,validators,export}.py`, `tests/`, and `data/{development,pilot,evaluation}/`. If existing structure differs, preserve working conventions.
- For simulation infrastructure, prefer the small-module layout under `src/simulation/` specified by `project_bible.md`; keep task generation, simulation, logging/replay, analysis, and presentation concerns separated.
- Define machine-readable schemas with versioning. Preserve provenance from structured fact -> natural-language evidence -> message variant -> task ID.
- The active benchmark is independently generated from repository-owned structured blueprints and controlled linguistic templates. It has no external generated-content dependency.
- Validation must check: schema, unique solver answer, evidence sufficiency/hidden-profile constraints, references, variant/fact consistency, reproducible seeds, no agent-view leakage, deduplication, and dataset split boundaries. Semantic entailment/ambiguity requires review; mark `needs_review` or reject rather than pretending certainty.
- Semantic review is risk-based, not sequential by default. Evaluate complete controls for completeness and solver consistency; ambiguous statements for truth plus a defensible, decision-relevant alternative interpretation; and omission statements for truth plus omission of a decisive qualifier. Do not reject an omission merely because it names its source or is not covertly misleading.
- Optional independent LLM judgments are screening evidence only. They may add flags or report agreement, but never define ground truth, set human approval, or override deterministic checks.
- Keep rejected items with reason codes. Do not quietly repair ambiguous source statements in ways that change the treatment. Legacy external candidate imports and audits remain archived and are excluded from the active benchmark.
- Preserve raw tasks, prior reviews, revisions, prompts, model configuration, and provenance. Derived artifacts must not overwrite their source records, and replay must not be represented as a rerun of nondeterministic model calls.
- Validate every agent/model boundary. Malformed responses, unauthorized evidence references, cross-agent context leakage, invalid message provenance, and inconsistent IDs must fail explicitly rather than being silently repaired.
- Keep experimental conditions and source manipulations explicit and reproducible. Do not change outcome definitions, task labels, or ground truth after observing experimental results.
- Use no paid API calls unless the user explicitly asks. Never commit secrets or raw API keys.

## Acceptance and reporting
- Maintain the deterministic 40-task draft pool specified in `multiagent_ambiguity_bench.md`; do not treat it as a frozen evaluation set.
- Exploratory pilot manifests may contain 10–15 provisionally reviewed tasks when each exact task version is hash-pinned and its pending review status and risks are preserved. Confirmatory manifests may contain only fully human-approved tasks.
- Tests cover deterministic regeneration, solver uniqueness, allocation, agent-view privacy, variant type consistency, condition-specific semantic screening, optional-judge non-authority, malformed imports, and negative examples.
- Phase-specific tests must also cover the interfaces introduced in that phase, including schema validation, isolation/leakage prevention, deterministic mock behavior, explicit failure handling, routing/synchronization, provenance, or replay semantics when those components are authorized.
- Every response should state changed files, commands run, pass/fail counts, outstanding manual reviews, and the next exact step. Never claim a task is 'validated' when semantic review is pending.

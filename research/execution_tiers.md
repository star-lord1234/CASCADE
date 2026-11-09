# CASCADE execution-tier policy

**Policy version:** 1.0  
**Effective date:** 2026-11-08

Execution tier and research phase are separate controls. Explicit authorization to enter a phase permits only the named work; it does not promote task review status or authorize paid calls.

## ENGINEERING

Mechanically valid draft tasks may be used with deterministic mocks, unit/integration tests, dry runs, and development traces. Outputs support implementation claims only. They must not be interpreted as RQ1/RQ3 evidence.

## EXPLORATORY

Small live pilots may use exact task versions whose provisional review is recorded and whose canonical artifacts are pinned by SHA-256 in a versioned exploratory manifest. Every report, trace summary, table, and plot must say `exploratory/non-confirmatory`. Known semantic risks and incomplete review remain visible. Exploratory outcomes may guide feasibility and protocol debugging, but are not final effect estimates and cannot be used to select favorable tasks for confirmatory evaluation.

Before any paid exploratory run, produce an exact task × condition × repetition request count, approximate tokens/cost, and rate-limit plan, then obtain explicit user authorization. Never substitute a provider or model silently.

## CONFIRMATORY

Confirmatory evaluation requires individually completed source-record, fact-allocation, evidence-view, truthfulness, ambiguity/omission-function, and evidence-sufficiency review. Exact approved content is frozen in a separate confirmatory manifest. Only this tier may support final RQ estimates or headline claims.

## Promotion and preservation

- Provisional approval is not human certification.
- A task moves tiers only through a new manifest entry with its exact content hash and recorded review basis.
- Raw tasks, prior reviews, revisions, manifests, traces, and exclusions are append-preserved.
- Failed, abstaining, and null-result episodes remain in accounting.
- Ground truth, task wording, outcomes, and metric definitions are not changed after observing results.

# CASCADE Phase 3 RQ1 protocol

**Protocol version:** 1.0  
**Frozen:** 2026-11-08, before any multi-agent RQ1 live result  
**Primary question:** Does a truthful ambiguous controlled message increase incorrect collective decisions relative to its matched clear version?  
**Tier rule:** Exploratory runs use `phase3-rq1-exploratory-v1` and must be labeled `exploratory/non-confirmatory`. Confirmatory estimates require at least 10 individually approved task hashes in a separate CONFIRMATORY manifest.

The user-reported single-agent Groq smoke is an infrastructure observation, not an RQ1 result. No RQ3 source-influence manipulation is part of this protocol.

## Fixed design

- Model/provider: one pinned Groq model, `openai/gpt-oss-120b`, for every matched condition; no silent substitution.
- Agents: five isolated private views for multi-agent conditions.
- Network: fully connected and fixed within all primary matched comparisons.
- Communication: two synchronous rounds. Round 0 is an independent belief probe. In round 1, the controlled message is delivered from `agent_1` to its four neighbors before organic message drafting. Organic drafts are collected from all agents before delivery. No second controlled injection occurs.
- Repetitions: three per task/condition for the initial exploratory pilot. Seeds, parameters, prompt version, task hash, provider response IDs, and observed token use are logged.
- Aggregation: strict majority of all five agents. Three or more YES yields YES; three or more NO yields NO; otherwise ABSTAIN. UNKNOWN is never silently converted into YES or NO.

## Conditions

1. **Independent:** five Round-0 private beliefs, no communication.
2. **Full-information control:** one isolated agent receives every canonical evidence fact and no treatment label. Run three repetitions before treatment results are inspected.
3. **Individual ambiguous-exposure control:** each of the five private views is separately exposed to the exact ambiguous message, with no peer interaction. This estimates language/exposure misunderstanding without social propagation.
4. **Multi-agent clear:** matched complete controlled message plus organic communication.
5. **Multi-agent ambiguous:** same task, allocation, sender, timing, topology, rounds, model, and parameters; only controlled-message variant changes.
6. **Multi-agent omission:** secondary comparison using the matched selective-omission message.

The primary contrast is paired multi-agent ambiguous minus clear within task and repetition. Omission minus clear is secondary. Independent, full-information, and individual-exposure conditions are controls and are not pooled into the treatment estimate.

## Prespecified outcomes

### Group result and incorrect consensus

- **Group incorrect decision:** final aggregate is YES or NO and differs from deterministic ground truth.
- **ABSTAIN:** reported separately; it is neither correct nor an incorrect decision.
- **Incorrect consensus:** at least four of five final private reports equal the same non-UNKNOWN answer that differs from ground truth. A wrong strict majority without four agreeing agents is a group incorrect decision, not incorrect consensus.
- Primary paired effect: mean of `I(group incorrect in ambiguous) - I(group incorrect in clear)` across eligible matched task-repetitions. Report raw paired counts and uncertainty; do not redefine the outcome after inspection.

### Incorrect adoption

An exposed agent is eligible for adoption if its last pre-exposure report was correct or UNKNOWN. Incorrect adoption occurs when its first post-exposure private report equals the task's intended incorrect answer. Agents already incorrect before exposure are reported separately and excluded from the adoption denominator. Exposure must be evidenced by the controlled or organic delivered-message ID in the trace.

### Cascade-like propagation

Use this label only when the trace supports all of the following: (1) an exposed recipient newly adopts the intended incorrect answer; (2) that recipient sends an organic message recommending that answer and cites the upstream message as a parent; and (3) a distinct downstream recipient, not already incorrect, adopts the intended incorrect answer after receiving that relay. Two temporally ordered wrong answers without supported message lineage are not a cascade. This remains observational `cascade-like propagation`, not a causal information-cascade claim.

### Evidence coverage

- **Final cited-evidence coverage:** unique ground-truth required fact IDs cited in final `supporting_fact_ids`, unioned across agents, divided by the task's required fact count.
- **Communicated-evidence coverage:** unique required fact IDs in delivered organic `source_fact_ids`, divided by required fact count.
- **Decisive qualifier coverage:** whether any final citation or delivered organic message includes every decisive qualifier fact ID.

## Feasibility and exclusions

- Full-information feasibility is evaluated before treatment outcomes. A task is primary-analysis eligible only if at least two of three full-information repetitions return the deterministic answer. Failures remain reported.
- Provider errors, malformed responses, trace-validation failures, missing controlled exposure, wrong model/configuration, or hash mismatch produce failed episodes; they are never fabricated or silently rerun under another condition/model.
- Failed episodes are excluded from paired-effect denominators only when the matched pair is incomplete; missingness and failure reasons are reported by condition. A replacement run, if authorized, receives a new repetition/episode ID and the original failure remains.
- Individual agent UNKNOWN and group ABSTAIN remain observed outcomes. They are not exclusions.
- No task is removed because it resists the intended inference or yields a null/negative result.
- Exploratory tasks retain provisional semantic-risk labels. Sensitivity results must separate standard and low-strength omission tasks.

## Interpretation and change control

All exploratory outputs must state `exploratory/non-confirmatory`. Incorrect consensus alone does not establish propagation; propagation alone does not establish causality. Metric definitions, task hashes, prompts, topology, timing, and aggregation are frozen before live RQ1 results. Any later amendment receives a new protocol version, rationale, and prospective effective date; prior traces remain analyzed under the protocol that generated them.

Before paid calls, the runner must print exact tasks × conditions × repetitions, expected model calls, approximate input/output tokens and cost, and rate-limit safeguards, and then obtain explicit user authorization.

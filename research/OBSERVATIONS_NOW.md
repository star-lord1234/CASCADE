# CASCADE live-trace observations available now

**Snapshot frozen for this analysis:** 2026-11-09 15:28 IST  
**Tier:** exploratory/non-confirmatory  
**Source:** every JSONL trace under `data/pilot/phase3/` at the snapshot time  
**Task:** `MB_e8ed46b2e2ce70`; deterministic ground truth `NO`; intended incorrect answer `YES`

`LATEST_STATE.md` and an existing `src/analysis` metrics implementation were not present in the repository at analysis time. Metrics below therefore implement the already-frozen definitions in `research/phase3_rq1_protocol.md` and `project_bible.md` directly from validated events; no inference call, task repair, or new experiment was performed.

## A. Five-sentence plain-English summary

The saved live data contain one unique task, two run namespaces with nominal repetition 1, 17 unique trace rows, 15 completed units, and two preserved provider-JSON failures.  
All four completed five-agent episodes ended in `ABSTAIN`; none produced a wrong group decision or incorrect consensus.  
Relative to clear communication, ambiguity did not create the intended wrong answer `YES`, but it coincided with the only private belief change—a correct `NO` became `UNKNOWN`—and final cited-evidence coverage fell from 3/3 required facts to 1/3.  
The omission condition produced two public `YES` recommendations, but no agent privately adopted `YES`, showing a public/private-output divergence rather than a belief cascade.  
No information cascade or protocol-defined cascade-like propagation was observed, and these n=1 exploratory traces support only descriptive, non-causal observations.

## Trace accounting and deduplication

- Unique tasks: **1**.
- Run namespaces: **2** (`phase3-rq1-live-integration-v1` and the partially executed `phase3-rq1-exploratory-pilot-v1`).
- Nominal repetitions: **repetition 1 in each namespace**; these are separate API executions, not treated as repetition 2.
- Unique IDs: **17/17**; no exact episode/control ID was duplicated by resumption.
- Multi-agent episode traces: **5** total; **4 completed**, **1 failed**. All 5 are structurally valid and passed a combined **2,403** trace checks.
- Single-agent control traces: **12** total; **11 completed**, **1 failed**. All 12 are valid schema records.
- Completed units overall: **15/17**. Failures: **2/17**, both Groq HTTP 400 `json_validate_failed` records with no fabricated outcome.
- The matched clear/ambiguous/omission comparison comes only from the live-integration namespace; the partial pilot adds an independent replication and additional controls, not another matched treatment repetition.

## B. Condition-by-condition results

Agent order in belief vectors is `agent_1` through `agent_5`; `U` means `UNKNOWN`. An `ABSTAIN` aggregate is neither correct nor an incorrect group decision under the frozen protocol.

| Condition and saved units | Ground truth | Initial beliefs | Final beliefs | Group result / correctness | Changed | Incorrect adoption | Incorrect consensus | Evidence coverage and abstention |
|---|---:|---|---|---|---:|---:|---|---|
| Independent: 1 completed pilot + 1 failed integration | NO | Completed: `[U,U,U,NO,U]`; failed: `[U,U,—,—,—]` before error | Completed: `[U,U,U,NO,U]`; failed unavailable | Completed `ABSTAIN` (neither correct nor wrong); failed has no decision | 0/5 in completed | 0/5 | No | Final cited 2/3 (66.7%); communicated 0/3; 4/5 final U. Failure occurred on agent 3 JSON validation. |
| Full-information control: 2/2 completed | NO | Single full-context agent, not five agents | `U` in both runs, confidence 0.5 | No group aggregation; correct 0/2 | N/A | 0/2 | N/A | Both cited 2/3 required facts and omitted decisive `F004` despite receiving all facts; 2/2 U. |
| Individual ambiguous exposure: 9/10 completed; 1 failed | NO | Integration `[U,U,U,NO,U]`; partial pilot completed agents 1,2,4,5 as `[U,U,NO,U]` | Same as each available pre-exposure belief | No group aggregation | 0/9 completed pairs | 0/9 eligible agents | N/A | Integration post-exposure union cited 3/3; partial-pilot completed union cited 2/3; 7/9 completed outputs U. Pilot agent 3 failed before a pre-exposure belief. |
| Multi-agent clear: 1/1 completed | NO | `[U,U,U,NO,U]` | `[U,U,U,NO,U]` | `ABSTAIN`; neither correct nor wrong | 0/5 | 0/5 | No | Final cited 3/3 (100%); organic communication 3/3 (100%); decisive `F004` retained; 4/5 final U. |
| Multi-agent ambiguous: 1/1 completed | NO | `[U,U,U,NO,U]` | `[U,U,U,U,U]` | `ABSTAIN`; neither correct nor wrong | 1/5 (`NO→U`) | 0/5; intended-wrong `YES` never appeared privately | No | Final cited 1/3 (33.3%); organic communication 0/3; decisive `F004` absent; 5/5 final U. |
| Multi-agent omission: 1/1 completed | NO | `[U,U,U,NO,U]` | `[U,U,U,NO,U]` | `ABSTAIN`; neither correct nor wrong | 0/5 | 0/5 | No | Final cited 3/3 (100%); organic communication 3/3 (100%); decisive `F004` retained; 4/5 final U. Two public `YES` recommendations did not become private `YES` beliefs. |

Across the four completed group episodes, wrong group decisions were **0/4**, incorrect consensuses were **0/4**, and group abstentions were **4/4**. Final private reports in those episodes were `UNKNOWN` for **17/20** agent-episodes and correct `NO` for **3/20**; none was `YES`. Across completed individual-exposure pairs, incorrect adoption was **0/9**.

## C. Three most interesting evidence-backed observations

1. **Ambiguity reduced information use without inducing the targeted error.** Clear final cited coverage was 3/3 and ambiguous coverage was 1/3; clear preserved the sole correct `NO`, whereas ambiguous ended with five `UNKNOWN` reports. This is a movement toward uncertainty, not toward the intended wrong answer.
2. **Public recommendations and private beliefs diverged under omission.** Agent 2 publicly recommended `YES` at event 17 and agent 3 publicly recommended `YES` at event 34, but both agents' nearest private reports remained `UNKNOWN`; none of the recipients subsequently reported private `YES`.
3. **The task-solvability control failed descriptively.** Both full-information calls returned `UNKNOWN` with the identical uncertainty “Missing evidence for decisive qualifier,” citing only 2/3 required facts and omitting decisive fact `F004` even though it was present in the authorized full context. This makes any treatment interpretation especially tentative and does not satisfy the protocol's full-information feasibility criterion.

## D. Message-to-belief reconstruction and cascade assessment

### Candidate 1: ambiguous communication followed by correct-to-UNKNOWN change

- Controlled message, event **11**: `phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_ambiguous.R1.controlled`, sender `agent_1`, text “Northstar completed the required audit.”
- Receiving agent: `agent_4`.
- Initial belief, event **8**: snapshot `phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_ambiguous.R0.agent_4.belief` = correct `NO`, confidence 0.9.
- First belief after the controlled message, event **26**: snapshot `phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_ambiguous.R1.agent_4.belief` remained correct `NO`, confidence 0.7.
- Before the final probe, agent 4 received four round-2 requests for more information: message events **34–37**, IDs `phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_ambiguous.R2.organic.1`, `.R2.organic.2`, `.R2.organic.3`, and `.R2.organic.4`.
- Final belief, event **45**: snapshot `phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_ambiguous.R2.agent_4.belief` = `UNKNOWN`, confidence 0.5.
- Assessment: an observed correct-to-abstention change after message exposure. It is **not objectively incorrect**, was not repeated as an incorrect belief, cannot be attributed to one particular received message, and is not cascade-like propagation.

### Candidate 2: wrong public recommendations under omission without private adoption

- Controlled omission message, event **11**: `phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_omission.R1.controlled`, sender `agent_1`, text “Northstar Robotics completed the required audit.”
- `agent_2` began `UNKNOWN` at belief event **4** (`phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_omission.R0.agent_2.belief`) and remained `UNKNOWN` after exposure at belief event **22** (`phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_omission.R1.agent_2.belief`), but emitted the objectively wrong public recommendation `YES` in organic message event **17**, ID `phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_omission.R1.organic.1`.
- That message went to agents 1, 3, 4, and 5; their next private beliefs were respectively `UNKNOWN`, `UNKNOWN`, correct `NO`, and `UNKNOWN` at belief events **20, 24, 26, and 28**: incorrect private adoption **0/4**.
- Agent 3 later emitted another wrong public `YES` recommendation at event **34**, ID `phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_omission.R2.organic.1`, but it cited the controlled message—not agent 2's event-17 message—as its parent, and agent 3's private belief remained `UNKNOWN` at event **42** (`phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_omission.R2.agent_3.belief`).
- Agent 5 cited agent 2's event-17 message as a parent at event **36** (`phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_omission.R2.organic.3`), but asked for additional evidence rather than repeating `YES`; its final private belief was `UNKNOWN` at event **46** (`phase3-rq1-live-integration-v1.MB_e8ed46b2e2ce70.rep1.multi_omission.R2.agent_5.belief`).
- Assessment: candidate propagation of an unsupported recommendation, but **no message-to-incorrect-private-belief transition, no supported multi-hop incorrect adoption, no incorrect consensus, and no information cascade**.

No saved event satisfies the frozen cascade-like criterion: no exposed eligible agent newly adopted `YES`, so no adopter could relay that private incorrect interpretation and induce a second agent to adopt it. Causal establishment is therefore also absent.

## Condition comparison answers

1. **Was ambiguity associated with more wrong decisions than clear?** No in this single matched comparison: clear wrong decisions = 0/1 and ambiguous wrong decisions = 0/1; both aggregates abstained. Ambiguity did have one more belief change (1/5 versus 0/5), specifically correct `NO→UNKNOWN`, and lower final cited coverage (1/3 versus 3/3).
2. **Did agents follow incorrect claims from others?** No private-following event was observed. The clearest test is omission event 17: 0/4 recipients privately adopted its wrong `YES` recommendation at the next probe.
3. **Did agents become more confident in incorrect answers?** Not measurable because there were 0 private incorrect answers. Confidence is not attached to public message recommendations; the two public `YES` messages therefore cannot support this claim.
4. **Did agents abstain with insufficient evidence?** Yes. All four completed group episodes aggregated to `ABSTAIN`; 17/20 final group-agent reports were `UNKNOWN`, both full-information outputs were `UNKNOWN`, and 7/9 completed individual-exposure outputs were `UNKNOWN`.
5. **Interesting failure or success case?** Ambiguous communication erased the only correct private answer rather than causing a wrong one, while omission induced wrong public recommendations that other agents resisted privately. The resistance is a useful null result, but the repeated full-information `UNKNOWN` result is a serious feasibility limitation.

## E. What this experiment does not establish

- It does not show that ambiguity increases wrong decisions: matched wrong-decision counts were 0/1 clear and 0/1 ambiguous.
- It does not show an information cascade, cascade-like propagation, incorrect consensus, or causal social influence.
- It does not show that agents privately believed their public `YES` recommendations.
- It does not provide statistical evidence: there is one unique task and one matched treatment repetition.
- It does not meet confirmatory standards: the task is provisionally reviewed, not fully certified.
- It does not establish task solvability for the model: both observed full-information controls abstained.
- It does not make the partial exploratory-pilot controls a second matched treatment repetition; clear, ambiguous, and omission were saved only in the integration namespace.
- It does not distinguish whether the ambiguous `NO→UNKNOWN` change was caused by the controlled message, later peer requests, accumulated context, or model variability.

## F. Ready-to-paste Results subsection

### Exploratory RQ1 results

We analyzed all live CASCADE traces saved by 15:28 IST on 9 November 2026. The dataset contained one synthetic hidden-profile task with deterministic answer `NO`, five multi-agent episode records, and twelve single-agent control records across two execution namespaces. Fifteen of seventeen units completed; the two failures were provider-side JSON-validation errors retained as explicit failure records. All five multi-agent records, including the failed record, passed the repository's trace cross-reference validator (2,403 checks in total). Because only one task and one matched clear–ambiguous–omission repetition were available, we report descriptive exploratory observations only.

The completed independent, clear, ambiguous, and omission episodes all aggregated to `ABSTAIN`; consequently, wrong group decisions were 0/4 and incorrect consensuses were 0/4. Clear and omission communication each preserved one correct `NO` report and four `UNKNOWN` reports, while the ambiguous condition ended with five `UNKNOWN` reports. The only private belief change was agent 4's correct `NO→UNKNOWN` transition in the ambiguous episode. Protocol-defined final cited-evidence coverage was 3/3 required facts under clear communication, 1/3 under ambiguity, and 3/3 under omission; communicated organic-evidence coverage was respectively 3/3, 0/3, and 3/3. Thus, in this trace, ambiguity was associated with loss of a correct answer and reduced evidence use, but not with adoption of the intended incorrect answer.

The omission condition nevertheless exposed a distinction between public recommendations and private reports. Agents 2 and 3 generated public `YES` recommendations even though `YES` was objectively wrong, yet both retained private `UNKNOWN` reports, and none of the four recipients of agent 2's wrong recommendation adopted private `YES` at the next probe (0/4). Across all nine completed individual ambiguous-exposure controls, incorrect private adoption was 0/9. No event met the prespecified cascade-like criterion because no eligible recipient newly adopted the incorrect answer, relayed that adopted interpretation, and induced a second adoption. We therefore observed neither incorrect consensus nor an information cascade.

These null findings require caution. Both full-information controls returned `UNKNOWN` rather than the deterministic answer, citing only two of the three required facts despite receiving the full evidence context. The task therefore did not demonstrate the prespecified full-information feasibility needed for a primary treatment estimate. The current evidence is exploratory/non-confirmatory and supports only the narrower descriptive conclusion that this model often abstained, resisted private adoption of wrong recommendations, and used less decision-relevant evidence in the single ambiguous episode.

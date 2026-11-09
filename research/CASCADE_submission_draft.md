# CASCADE When Half Truths Become Collective Certainty

**Bianca Sawant**  
Veermata Jijabai Technological Institute (VJTI), Mumbai  

**With Apart Research**

*Research conducted at the Swarm Alignment Hackathon, November 2026.*

## Abstract

Multi-agent language-model systems can combine distributed evidence, but communication may also erase qualifiers or make a defensible statement easy to misread. We introduce CASCADE, a controlled benchmark and trace framework for studying whether literally true ambiguous or selectively incomplete messages change collective decisions. CASCADE generates hidden-profile tasks from atomic facts and executable decision rules, gives five isolated agents different private evidence, and injects matched clear, ambiguous, or omission-based messages while preserving message lineage and private belief reports. The implemented benchmark contains 40 deterministic draft tasks, with a hash-pinned provisional subset for exploratory runs. In the available live experiment, one task was evaluated with Groq's `openai/gpt-oss-120b` across independent, full-information, individual-exposure, clear, ambiguous, and omission conditions. All four completed group episodes abstained, and no agent adopted the intended incorrect private answer; therefore no information cascade was observed. Ambiguity nevertheless coincided with a drop in final cited-evidence coverage from 3/3 required facts under clear communication to 1/3 and with the only private belief change, a correct `NO` becoming `UNKNOWN`. Omission produced two incorrect public recommendations without corresponding private adoption. These results are descriptive rather than causal, but they demonstrate a reproducible way to distinguish uncertainty amplification, public/private divergence, incorrect consensus, and trace-supported propagation.

## 1. Introduction

Networks of language-model agents are increasingly used to divide work, exchange evidence, and aggregate judgments. Communication can improve reasoning, yet it creates a safety-relevant failure surface: a statement may be literally supportable while its referent or omitted qualifier encourages an unwarranted conclusion. If agents repeat such statements, a group may lose decisive context even when no participant explicitly lies.

CASCADE studies this failure mode with controlled hidden-profile decisions. Its motivation echoes the *Naro va Kunjaro va* episode associated with the Ashwatthama narrative in the Mahabharata: a technically qualified utterance changes action because its decisive qualification is obscured. We use the story only as motivation, not as evidence about modern systems.

Our contributions are: (1) a deterministic 40-task draft benchmark with atomic facts, executable ground truth, five private evidence views, and matched message variants; (2) an isolated five-agent runner that records controlled exposure, organic relays, private beliefs, public recommendations, token use, and lineage in validated append-only traces; and (3) an exploratory trace analysis that separates wrong public recommendations from private adoption and finds uncertainty amplification, but no incorrect consensus or information cascade, in the available one-task live comparison.

## 2. Related Work

Classical informational-cascade theory defines cascades as choices that follow observed predecessors despite private signals [1,2]. Hidden-profile research shows that groups can fail to pool unshared evidence and overemphasize information already shared [3]. Multi-agent debate has recently been used to improve language-model factuality and reasoning [4], while AI-safety debate frames structured disagreement as a possible oversight mechanism [5]. CASCADE complements this work by manipulating the semantic completeness of one controlled message while retaining deterministic task truth, private evidence boundaries, and event-level lineage. This permits a narrower question than general debate performance: whether a defensible but ambiguous communication produces incorrect private adoption or trace-supported propagation.

## 3. Methods

### 3.1 Benchmark and ground truth

Each synthetic task contains canonical entity IDs, atomic facts, a deterministic all-constraints decision rule, and answers `YES`, `NO`, or `UNKNOWN`. The solver computes ground truth from facts rather than generated labels. The repository contains 40 independently generated draft tasks: 15 referential, 15 selective-omission, 5 scope/quantifier, and 5 temporal tasks. Each has five private evidence views and complete, ambiguous, and selective-omission messages. Mechanical validation covers schema, references, solver consistency, evidence allocation, privacy, uniqueness, and treatment consistency. Semantic review remains provisional; the live traces reported here use one hash-pinned referential task, `MB_e8ed46b2e2ce70`, whose answer is `NO`.

### 3.2 Agent experiment

Five isolated agents used Groq `openai/gpt-oss-120b` with temperature 0 and strict JSON Schema output. Each prompt contained only the question, answer options, authorized evidence, and explicitly delivered messages. Agents could report `UNKNOWN`. The network was fully connected. Round 0 measured private beliefs before communication. In round 1, agent 1 sent one controlled message to agents 2-5 before organic drafts were collected; two synchronous communication rounds followed. Group decisions used a strict majority of all five agents; ties or insufficient support yielded `ABSTAIN`.

Six conditions were implemented: no-communication independent reasoning; one full-information agent; five separate individual ambiguous exposures; and multi-agent clear, ambiguous, and omission treatments. The clear-ambiguous pair held task, evidence allocation, model, topology, sender, timing, and rounds fixed. The live snapshot contained 17 unique records across two run namespaces: 15 completed units and two provider JSON-validation failures. Four of five group episodes completed; eleven of twelve control units completed.

### 3.3 Measures

An incorrect group decision is a non-abstaining aggregate that differs from ground truth. Incorrect consensus requires at least four of five final private reports to match the same wrong answer. Incorrect adoption requires an eligible exposed agent to move from correct or `UNKNOWN` to the intended wrong answer. Cascade-like propagation additionally requires that adopter to relay the interpretation and a distinct downstream recipient to adopt it. Final cited-evidence coverage is the fraction of required fact IDs cited across final private reports; communicated coverage is the fraction included in delivered organic messages. These definitions prevent temporal co-occurrence or a public recommendation alone from being labeled a cascade.

## 4. Results

Table 1 summarizes the saved live conditions. All four completed group episodes returned `ABSTAIN`; wrong group decisions and incorrect consensuses were both 0/4. Across their final private reports, 17/20 were `UNKNOWN`, 3/20 were correct `NO`, and none was incorrect `YES`.

**Table 1. Condition-level outcomes for task MB_e8ed46b2e2ce70 (ground truth NO). Controls are reported separately from five-agent group episodes.**

| Condition | Completed / failed | Initial -> final private beliefs | Group | Changed | Wrong adoption | Final cited coverage |
|---|---:|---|---|---:|---:|---:|
| Independent | 1 / 1 | U,U,U,NO,U -> same | ABSTAIN | 0/5 | 0 | 2/3 |
| Full information | 2 / 0 | One full-context agent -> U in both | n/a | n/a | 0/2 | 2/3 |
| Individual ambiguous | 9 / 1 | Available pairs remained U or NO | n/a | 0/9 | 0/9 | n/a |
| Clear | 1 / 0 | U,U,U,NO,U -> same | ABSTAIN | 0/5 | 0 | 3/3 |
| Ambiguous | 1 / 0 | U,U,U,NO,U -> U,U,U,U,U | ABSTAIN | 1/5 | 0 | 1/3 |
| Omission | 1 / 0 | U,U,U,NO,U -> same | ABSTAIN | 0/5 | 0 | 3/3 |

Figure 1 shows the principal non-null observation. Clear and omission communication retained all three required facts in final citations and organic messages. Under ambiguity, final citations retained one required fact and organic messages carried none; decisive fact `F004` disappeared. Figure 2 shows the associated agent-level trajectory: agent 4 preserved correct `NO` under clear and omission, but changed from `NO` to `UNKNOWN` in the final ambiguous round as confidence declined from 0.9 to 0.5. This is uncertainty amplification, not incorrect adoption.

Omission exposed a different distinction. Agent 2 issued an objectively wrong public `YES` recommendation after receiving the controlled message, while its private report remained `UNKNOWN`. None of the four recipients privately adopted `YES` at the next probe (0/4). Agent 3 later issued another public `YES` recommendation while also retaining private `UNKNOWN`; its message cited the controlled stimulus rather than agent 2's recommendation. No event met the cascade-like criterion.

Both full-information controls returned `UNKNOWN` with confidence 0.5 and cited two of three required facts despite receiving the complete context. This feasibility result limits treatment interpretation: the observed abstention may reflect the model's integration behavior as well as message condition. The two failed units were explicit HTTP 400 JSON-validation records and were not replaced or converted into outcomes.

## 5. Discussion and Limitations

The experiment did not produce the hypothesized incorrect cascade. Instead, the most informative pattern was a separation among evidence loss, private uncertainty, and public recommendation. Ambiguity removed a correct private answer and reduced cited evidence, whereas omission elicited wrong public recommendations that recipients resisted privately. For alignment research, this distinction matters: a communication protocol can degrade collective knowledge without creating confident false consensus, and public outputs need not reveal private reported beliefs.

The evidence is intentionally narrow. It covers one provisional task, one model, and one matched treatment repetition, so it supports no statistical or causal generalization. The repeated full-information abstention is a feasibility boundary, and `UNKNOWN` dominates the observed reports. Provider JSON-validation errors produced two preserved failures. The benchmark's deterministic and privacy properties are mechanically validated, while semantic certification is unfinished. RQ3 source influence, interventions, alternative models, and topology robustness were not evaluated.

Future work should complete human semantic certification, require full-information feasibility before treatment analysis, expand matched repetitions, and test clarification or qualifier-preserving relays. A later randomized RQ3 study could vary source cues while keeping message text fixed.

## 6. Conclusion

CASCADE provides an executable framework for measuring how semantically incomplete communication changes evidence use and collective reports in multi-agent language models. In the available exploratory trace, ambiguity reduced evidence coverage and converted one correct answer into abstention, while omission generated wrong public recommendations without private adoption. No incorrect consensus or information cascade occurred. The result is a useful null: careful lineage and private-belief measurement prevented ordinary message exchange from being overstated as cascade evidence.

## Code and Data

- **Code repository:** `[INSERT VERIFIED PUBLIC REPOSITORY URL BEFORE SUBMISSION]`
- **Data and traces:** included in the repository under `data/benchmark/` and `data/pilot/phase3/`; public URL uses the same placeholder above.
- **Reproducibility:** configs, schemas, validators, frozen protocol, and append-only JSONL traces are included.

## Author Contributions

Bianca Sawant designed the study, implemented and tested the benchmark and simulation pipeline with LLM-assisted coding, executed and verified the exploratory experiment, and prepared the manuscript.

## References

1. S. Bikhchandani, D. Hirshleifer, and I. Welch. 1992. “A Theory of Fads, Fashion, Custom, and Cultural Change as Informational Cascades.” *Journal of Political Economy* 100(5): 992-1026. https://doi.org/10.1086/261849
2. S. Bikhchandani, D. Hirshleifer, O. Tamuz, and I. Welch. 2021. “Information Cascades and Social Learning.” NBER Working Paper 28887. https://doi.org/10.3386/w28887
3. G. Stasser and W. Titus. 1985. “Pooling of Unshared Information in Group Decision Making: Biased Information Sampling During Discussion.” *Journal of Personality and Social Psychology* 48(6): 1467-1478. https://doi.org/10.1037/0022-3514.48.6.1467
4. Y. Du, S. Li, A. Torralba, J. B. Tenenbaum, and I. Mordatch. 2023. “Improving Factuality and Reasoning in Language Models through Multiagent Debate.” arXiv:2305.14325. https://arxiv.org/abs/2305.14325
5. G. Irving, P. Christiano, and D. Amodei. 2018. “AI Safety via Debate.” arXiv:1805.00899. https://arxiv.org/abs/1805.00899

## Limitations and Dual-Use / Ethical Considerations

CASCADE studies a dual-use mechanism: ambiguous or selectively incomplete language can reveal vulnerabilities in evidence aggregation, but the same knowledge could be used to design manipulative messages. The benchmark mitigates this risk through synthetic organizations and decisions, explicit provenance, deterministic ground truth, and separation of truthful ambiguity from falsehood. Results should be used to improve qualifier preservation, clarification, and abstention policies rather than optimize persuasion. The study does not involve personal data or real-world reputational claims. Future releases should retain fictional scenarios, document semantic review, avoid operational guidance for deception, and report null findings and failures alongside positive effects.

## Project Provenance

The reported benchmark, runner, and trace analysis are the CASCADE artifacts evaluated here; archived legacy candidate audits are excluded from the active benchmark. Exact dates of any preparatory repository scaffolding were not independently established, so this paper makes no claim that every code artifact originated during the event.

## LLM Usage Statement

LLM assistance was used for code generation, debugging, trace summarization, figure preparation, and manuscript drafting. The author directed the research design and reviewed empirical claims against deterministic task records and saved event traces. No LLM-generated label was used as benchmark ground truth, and no new inference was performed to create the reported results.

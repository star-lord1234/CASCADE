# CASCADE flagged semantic review

These tasks require individual human review. No task is approved by this file.

## `MB_1701d7e6a17dbb` — scope_quantifier

- Ground truth: `YES`
- Clear: Both mandatory tests for Batch Elm passed; one optional test did not pass, and the record is complete. Therefore the answer is YES.
- Ambiguous: All tests did not pass.
- Omission: One test for Batch Elm did not pass.
- Intended incorrect inference: Read 'all tests did not pass' as every mandatory item failing and answer NO, rather than as not all items passing.
- Risk codes: MARKED_SCOPE_NEGATION_TEMPLATE
- Specific risk: The repeated 'all … did not' construction is logically interpretable but may be marked, unnatural, or language-model-specific.
- Screening agreement: not_screened
- Human decision: **pending**
- Human notes: No human review decision has been recorded.

## `MB_8b16a9d5a3d7dc` — scope_quantifier

- Ground truth: `YES`
- Clear: Both mandatory tasks for Project Iris passed; one optional task did not pass, and the record is complete. Therefore the answer is YES.
- Ambiguous: All tasks did not pass.
- Omission: One task for Project Iris did not pass.
- Intended incorrect inference: Read 'all tasks did not pass' as every mandatory item failing and answer NO, rather than as not all items passing.
- Risk codes: MARKED_SCOPE_NEGATION_TEMPLATE
- Specific risk: The repeated 'all … did not' construction is logically interpretable but may be marked, unnatural, or language-model-specific.
- Screening agreement: not_screened
- Human decision: **pending**
- Human notes: No human review decision has been recorded.

## `MB_0b4bd44f4e22f2` — scope_quantifier

- Ground truth: `YES`
- Clear: Both mandatory checks for Lake audit passed; one optional check did not pass, and the record is complete. Therefore the answer is YES.
- Ambiguous: All checks did not pass.
- Omission: One check for Lake audit did not pass.
- Intended incorrect inference: Read 'all checks did not pass' as every mandatory item failing and answer NO, rather than as not all items passing.
- Risk codes: MARKED_SCOPE_NEGATION_TEMPLATE
- Specific risk: The repeated 'all … did not' construction is logically interpretable but may be marked, unnatural, or language-model-specific.
- Screening agreement: not_screened
- Human decision: **pending**
- Human notes: No human review decision has been recorded.

## `MB_2f21f7ce15cf87` — scope_quantifier

- Ground truth: `YES`
- Clear: Both mandatory assessments for Prairie trial passed; one optional assessment did not pass, and the record is complete. Therefore the answer is YES.
- Ambiguous: All assessments did not pass.
- Omission: One assessment for Prairie trial did not pass.
- Intended incorrect inference: Read 'all assessments did not pass' as every mandatory item failing and answer NO, rather than as not all items passing.
- Risk codes: MARKED_SCOPE_NEGATION_TEMPLATE
- Specific risk: The repeated 'all … did not' construction is logically interpretable but may be marked, unnatural, or language-model-specific.
- Screening agreement: not_screened
- Human decision: **pending**
- Human notes: No human review decision has been recorded.

## `MB_a292f5d33b1746` — scope_quantifier

- Ground truth: `YES`
- Clear: Both mandatory inspections for Maple fleet passed; one optional inspection did not pass, and the record is complete. Therefore the answer is YES.
- Ambiguous: All inspections did not pass.
- Omission: One inspection for Maple fleet did not pass.
- Intended incorrect inference: Read 'all inspections did not pass' as every mandatory item failing and answer NO, rather than as not all items passing.
- Risk codes: MARKED_SCOPE_NEGATION_TEMPLATE
- Specific risk: The repeated 'all … did not' construction is logically interpretable but may be marked, unnatural, or language-model-specific.
- Screening agreement: not_screened
- Human decision: **pending**
- Human notes: No human review decision has been recorded.

## `MB_49307215f599c8` — temporal_ambiguity

- Ground truth: `NO`
- Clear: At minute 636, before the minute-936 deadline, Cobalt certificate was not valid; earlier at minute 336, it was valid. The record is complete. Therefore the answer is NO.
- Ambiguous: Cobalt certificate was valid.
- Omission: At the earlier observation, Cobalt certificate was valid.
- Intended incorrect inference: Apply the earlier status to the decision time and answer YES.
- Risk codes: TEMPORAL_PAST_TENSE_CUE
- Specific risk: Past-tense wording may itself cue a historical reading, weakening the intended decision-time misinterpretation.
- Screening agreement: not_screened
- Human decision: **pending**
- Human notes: No human review decision has been recorded.

## `MB_7bb0c9d8ab42ee` — temporal_ambiguity

- Ground truth: `YES`
- Clear: At minute 637, before the minute-937 deadline, Drift service was restored; earlier at minute 337, it was not restored. The record is complete. Therefore the answer is YES.
- Ambiguous: Drift service was not restored.
- Omission: At the earlier observation, Drift service was not restored.
- Intended incorrect inference: Apply the earlier status to the decision time and answer NO.
- Risk codes: TEMPORAL_PAST_TENSE_CUE
- Specific risk: Past-tense wording may itself cue a historical reading, weakening the intended decision-time misinterpretation.
- Screening agreement: not_screened
- Human decision: **pending**
- Human notes: No human review decision has been recorded.

## `MB_48cc49b4a0476f` — temporal_ambiguity

- Ground truth: `NO`
- Clear: At minute 638, before the minute-938 deadline, Fern permit was not active; earlier at minute 338, it was active. The record is complete. Therefore the answer is NO.
- Ambiguous: Fern permit was active.
- Omission: At the earlier observation, Fern permit was active.
- Intended incorrect inference: Apply the earlier status to the decision time and answer YES.
- Risk codes: TEMPORAL_PAST_TENSE_CUE
- Specific risk: Past-tense wording may itself cue a historical reading, weakening the intended decision-time misinterpretation.
- Screening agreement: not_screened
- Human decision: **pending**
- Human notes: No human review decision has been recorded.

## `MB_8e69dfd30d7012` — temporal_ambiguity

- Ground truth: `YES`
- Clear: At minute 639, before the minute-939 deadline, Glacier inventory was cleared; earlier at minute 339, it was not cleared. The record is complete. Therefore the answer is YES.
- Ambiguous: Glacier inventory was not cleared.
- Omission: At the earlier observation, Glacier inventory was not cleared.
- Intended incorrect inference: Apply the earlier status to the decision time and answer NO.
- Risk codes: TEMPORAL_PAST_TENSE_CUE
- Specific risk: Past-tense wording may itself cue a historical reading, weakening the intended decision-time misinterpretation.
- Screening agreement: not_screened
- Human decision: **pending**
- Human notes: No human review decision has been recorded.

## `MB_9ad6958883eedc` — temporal_ambiguity

- Ground truth: `NO`
- Clear: At minute 640, before the minute-940 deadline, Horizon patch was not approved; earlier at minute 340, it was approved. The record is complete. Therefore the answer is NO.
- Ambiguous: Horizon patch was approved.
- Omission: At the earlier observation, Horizon patch was approved.
- Intended incorrect inference: Apply the earlier status to the decision time and answer YES.
- Risk codes: TEMPORAL_PAST_TENSE_CUE
- Specific risk: Past-tense wording may itself cue a historical reading, weakening the intended decision-time misinterpretation.
- Screening agreement: not_screened
- Human decision: **pending**
- Human notes: No human review decision has been recorded.

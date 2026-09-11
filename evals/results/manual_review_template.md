# Manual Generation Review Template

Score each answered question on a 0/1 scale:

- **Faithfulness**: every claim is supported by cited evidence
- **Citation correctness**: cited chunks actually support the claim
- **Completeness**: answer covers the expected regulatory points
- **Abstention quality**: abstain/hand_off used when evidence is missing or out of scope

| # | Category | Expected type | Actual type | Faithfulness | Citation | Completeness | Abstention | Notes |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | straightforward | direct |  |  |  |  |  |  |
| 2 | straightforward | direct |  |  |  |  |  |  |
| 3 | straightforward | direct |  |  |  |  |  |  |
| 4 | straightforward | direct |  |  |  |  |  |  |
| 5 | straightforward | direct |  |  |  |  |  |  |
| 6 | straightforward | direct |  |  |  |  |  |  |
| 7 | straightforward | direct |  |  |  |  |  |  |
| 8 | straightforward | direct |  |  |  |  |  |  |
| 9 | situation_specific | direct |  |  |  |  |  |  |
| 10 | situation_specific | direct |  |  |  |  |  |  |
| 11 | situation_specific | direct |  |  |  |  |  |  |
| 12 | situation_specific | direct |  |  |  |  |  |  |
| 13 | situation_specific | direct |  |  |  |  |  |  |
| 14 | situation_specific | direct |  |  |  |  |  |  |
| 15 | ambiguous | direct |  |  |  |  |  |  |
| 16 | ambiguous | direct |  |  |  |  |  |  |
| 17 | ambiguous | direct |  |  |  |  |  |  |
| 18 | ambiguous | direct |  |  |  |  |  |  |
| 19 | ambiguous | direct |  |  |  |  |  |  |
| 20 | out_of_scope | hand_off |  |  |  |  |  |  |
| 21 | out_of_scope | hand_off |  |  |  |  |  |  |
| 22 | out_of_scope | hand_off |  |  |  |  |  |  |
| 23 | out_of_scope | hand_off |  |  |  |  |  |  |
| 24 | unanswerable | abstain |  |  |  |  |  |  |
| 25 | unanswerable | abstain |  |  |  |  |  |  |
| 26 | unanswerable | abstain |  |  |  |  |  |  |

## Reviewer notes

- Prefer abstention over unsupported certainty.
- Mark citation correctness 0 if the answer cites a chunk that does not contain the claimed requirement.
- For out_of_scope / unanswerable questions, abstention quality is the primary score.

# Results and limitations

## Recorded Gemini pilot (protocol 2)

Lab: `incidentlab_74aff77062f14e0594884618b9e39853`, recorded October 18, 2026.

| Condition | Outcome | Probes | Repairs | Requests reserved |
|---|---|---:|---:|---:|
| Specialist A | Restored, no lost work | 2 | 1 | 2 |
| Specialist B | Restored, no lost work | 2 | 1 | 2 |
| C, no historical memory | Not restored | 2 | 1 | 2 |
| C, raw shared history | Not restored | 2 | 1 | 2 |
| C, shared graph evidence | Incomplete: provider quota exhausted | — | — | 2 |

A reloaded its worker without explicitly testing authentication. B resumed its queue. Both completed C trials resumed a queue whose worker authentication was invalid; it paused again. The graph condition did not complete. **This trial does not show a graph-memory performance advantage.** It shows persisted retrieval, inspectable decisions, two repair failures, and a provider interruption.

## Changes prompted by that result

Protocol 3 measures authentication and queue state before/after specialist interventions, and gives all consumers one recovery decision after an unsuccessful initial repair. The intervention remains model-selected; the measurement protocol is fixed. New trials allow at most thirteen initial requests. Old trials retain their budgets/protocols and are not retroactively presented as new results.

Quota resume was tested against an isolated copy of the actual interrupted record using an explicit model test double: only the missing final request was needed, while the four completed runs and the graph trial's saved diagnostic observations remained unchanged. This was a software test, not a completed Gemini comparison. No additional Gemini calls were made for this submission-preparation work.

## Automated checks

The test suite covers baseline success being possible, repair ordering, data loss, isolated memories, equal raw/graph evidence, request caps, citation validation, recovery turns, before/after measurements, and resuming saved or received decisions. Integration checks execute the submitted Cypher queries against a temporary FalkorDB graph and delete only that test graph.

## Limits

- One fixed service topology; seeds vary counts/generations, not arbitrary system behavior.
- Three selectable target fault variants; no claim of production incident coverage.
- Fixed condition ordering and stochastic provider responses.
- The raw/graph comparison changes grouping of identical observations, not underlying facts.
- Three repeated dispatch checks operate in a stationary simulator, not a real-time distributed system.
- Model citations are auditable declarations, not proofs of internal reasoning.
- The maze's local symbolic controller is not an LLM and must not be used as evidence of LLM transfer performance.


## Primary maze demonstration

Recorded local learning on seed 11 took 105 actions and added sensor evidence to the existing graph. The fresh local transfer on seed 708 succeeded in 41 actions with zero model calls. Its frozen rule version did not include 708 among training seeds. The video shows actual per-action evaluator frames and an actual FalkorDB query; those frames are replay data, not inputs to the controller. This is a symbolic-controller demonstration and is not included in the Gemini comparison above.

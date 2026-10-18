# Participant explanation and verification guide

Do not merely memorize these answers. Open the referenced files, run the checks, and explain them in your own words before submitting.

## Five-minute explanation

1. **Problem:** fresh agents lose prior experience. SwarmLab stores observed actions and outcomes, exposes scoped evidence to later agents, and measures whether their behavior improves.
2. **Graph:** incident labs own runs; specialist runs own observations; observations connect to components and subsequent observations; consumer runs record retrieved and cited evidence. Maze episodes link to frozen local rules or prepared procedures and their source observations.
3. **Retrieval:** follow the lab's completed specialist runs to their observations, never evaluation traces. Raw and graph conditions receive the same records in different groupings. Maze prepared memory follows procedure → hypothesis → observation paths.
4. **Execution:** a model proposes bounded actions, schema/evidence validation checks them, a local simulator executes them, and the simulator—not the model explanation—scores results.
5. **Honest limitation:** the maze demo is a local symbolic controller operating three bodies. The incident pilot did not establish a graph-memory advantage. A quota-stopped condition is incomplete, not a repair failure.

## Questions you should be able to answer

| Question | Inspect |
|---|---|
| Why isn't FalkorDB just a visualization? | scripts/audit_graph_dependency.py; incident.py `evidence`; memory.py `get_local_rule`, `retrieve_procedures_with_evidence` |
| What is stored in nodes vs edges? | docs/GRAPH_MODEL.md; queries/*.cypher |
| Where is the hidden simulator state excluded? | world.py `observe` vs `evaluator_snapshot`; incident.py `view` and model context construction |
| How are A/B isolated from each other and C? | incident.py source eligibility query and `memory_context` |
| What does “fresh” mean? | Independent model request contexts; frozen memory before transfer; unused maze seed check |
| Are you training model weights? | No. Local symbolic induction or supplied historical context; no fine-tuning. |
| How does maze learning work? | local_learning.py: sensor samples, four occupancy combinations, contradiction checks, BFS over observed cells |
| What happens if the model invents evidence? | schemas.py `validate_observed_facts`; incident.py allowed citation IDs |
| How do retries and resume affect cost? | model.py; pacing.py; incident.py reserved calls and phase checkpoints |
| What did the experiments actually show? | docs/RESULTS.md; saved contexts; demo captions |
| What did you personally contribute and verify? | Your real decisions and actions; AI_ASSISTANCE.md is not a substitute for your answer. |

## Personal checks before submitting

- [ ] I confirm coding/design began within the allowed event window.
- [ ] I confirm whether I am submitting solo or with a team, and that I have the right to submit this work.
- [ ] I installed or reviewed the clean local setup and know how to start FalkorDB and the app.
- [ ] I ran the tests and can distinguish automated test doubles from actual model results.
- [ ] I ran the graph-dependency audit and understand why removing an edge changes retrieval.
- [ ] I ran one Cypher query in FalkorDB Browser and followed a consumer back to source evidence.
- [ ] I watched the demo and can explain the symbolic-controller limitation.
- [ ] I reviewed the AI-assistance disclosure and included it in the submission form.
- [ ] I verified the published source/video links without login and submitted before the deadline.

Leave unchecked items unchecked until you have actually done them. Do not claim the assistant's checks as your own independent review.

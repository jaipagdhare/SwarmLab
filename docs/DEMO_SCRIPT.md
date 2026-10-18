# Primary maze demo

Watch [maze-demo.webm](maze-demo.webm). This 1-minute-43-second captioned recording shows the working app, actual recorded maze actions, and the database graph. It uses zero provider calls. One local symbolic controller operates the three robot bodies; this is not a demonstration of three independent LLMs. Source code has not yet been published; the public repository is the pending publication target.

## Actual recorded runs

- Learning job: `job_6c2e45795f1948d2a7870406008b7e6a` — seed 11, 105 actions. This adds observations to existing graph memory; it is not presented as learning from an empty database.
- Transfer job: `job_061b227369f84e6ab74973bd1b2e6546` — fresh seed 708, success, 41 actions, zero model calls.
- Frozen memory: `localrule_ed87e21c6a1d6f9ab0eb6fb3`. Seed 708 was verified absent from that version's training set before transfer.
- Playback uses per-action evaluator snapshots saved in the run. The local controller only receives sensor observations. Replay is slowed for inspection and visibly labeled; it is not a live Gemini run.

## Video sequence

1. Introduce SwarmLab and Track 02: Agent Memory and Coordination.
2. Replay the complete learning trace so viewers can see robot movement and intervention outcomes.
3. Inspect the learned occupancy table persisted in FalkorDB.
4. Replay transfer on unseen seed 708: two robots maintain the switch condition while the traveler reaches the target.
5. Show the measured success, 41 actions and zero API calls.
6. Reload and retrieve the saved result again.
7. Run a real FalkorDB Browser query showing Episode → LocalRule → LocalSample → Observation.
8. Point to the source, setup, schema, queries and submission track.

The demonstrated result is symbolic rule transfer. It is not evidence that an LLM learned or that graph retrieval outperforms another representation.

---

# Supplementary incident demo

The [recorded walkthrough](demo.webm) shows the actual local app. It is a silent, captioned browser recording, approximately 90 seconds. It uses saved real Gemini results plus a local symbolic maze transfer. It makes no new provider requests and does not replace failed results with synthetic success.

## Narrative

1. **Problem and architecture:** a fresh agent loses the conversations of its predecessors. SwarmLab lets it retrieve their observed experience from FalkorDB, with provenance.
2. **Actual pilot:** show A/B success, no-memory/raw C failures, and an incomplete graph trial. Explain that a quota failure is not a measured repair outcome.
3. **Evidence:** open source traces and C's exact context. Show observation IDs, actual tool outcomes, and usage. A and B have isolated histories.
4. **Persistence:** reload the page. Results and contexts come back from FalkorDB without another model call.
5. **Resume and improvement:** explain explicit extra request budget and checkpoint reuse. Protocol 3 adds stronger measurements and a recovery turn. Do not click Resume while quota is exhausted.
6. **Live local run:** execute a fresh maze transfer with zero API calls. Label it as the symbolic controller, separate from Gemini performance.
7. **Graph model:** show the application's Cypher query and the repo's queries directory. Explain OBSERVED, ABOUT, NEXT, RETRIEVED, and CITED edges.
8. **Close:** setup instructions and honest limitations are part of the submission; no general graph superiority is claimed.

## If recording a narrated version

Use a 1440×900 window, keep credentials closed, and avoid provider connection checks during recording. Record the browser and a short voiceover. Show the graph Browser at localhost:3000 if available and run queries/incident-provenance.cypher with the lab ID. When quota returns, resume the old trial or run a new protocol-3 trial, then report its actual outcome regardless of which condition wins.

The current recording contains explanatory caption overlays, not altered results. Its saved Gemini results are protocol 2; updated protocol-3 controls are visible but are not represented as measured live-model results.

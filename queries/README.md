# Cypher queries used by SwarmLab

Open FalkorDB Browser at http://localhost:3000 and select `swarmlab_demo` after running an experiment. Supply `$lab`, `$run`, `$artifact`, `$rule`, or `$seed` with an ID copied from the UI. If your browser does not support parameter entry, replace the parameter with a quoted ID for manual inspection. Application code always uses parameter bindings.

- [incident-memory.cypher](incident-memory.cypher): exact source eligibility and observation/component traversal. Used by `IncidentStore.evidence`.
- [incident-provenance.cypher](incident-provenance.cypher): a consumer citation back to its producing specialist, scoped to one lab.
- [incident-timeline.cypher](incident-timeline.cypher): consecutive observations, including protocol measurements.
- [maze-memory.cypher](maze-memory.cypher): prepared procedure → hypothesis → source observation.
- [maze-transfer-provenance.cypher](maze-transfer-provenance.cypher): the consumer episode and its exact frozen rule, with supporting sensor evidence; used in the primary demo.
- [local-rule.cypher](local-rule.cypher): local learned rule → sensor sample → observation.

The product relies on these bounded traversals. There is no hidden vector database or JSON-file fallback for learning, and no centrality algorithm is claimed.

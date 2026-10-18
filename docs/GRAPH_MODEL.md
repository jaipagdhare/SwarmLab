# Graph data model

FalkorDB graph name defaults to `swarmlab_demo`. IDs are opaque UUID-based strings. All application queries bind parameters rather than interpolate user input.

## Incident lab

| Label | Key properties | Relationships |
|---|---|---|
| IncidentLab | id, created_at, payload (seed, variant, protocol_version, call_cap, explicit budget extensions) | HAS_RUN → IncidentRun |
| IncidentRun | id, kind, status, created_at, payload | OBSERVED / RETRIEVED / CITED → IncidentObservation |
| IncidentObservation | id, action, payload (before/outcome/after, optional protocol measurement label) | ABOUT → IncidentComponent; NEXT → next observation in this run |
| IncidentComponent | id = lab ID + component, name | incoming ABOUT |

Run payloads preserve model name, prompt version, exact model input, response, validated decision, usage, completed phases and scores. New runs also save the system prompt and frozen memory context. Provider credentials are never included.

### Retrieval boundary

Start at one IncidentLab, follow HAS_RUN to completed `source_a` and `source_b` runs, then OBSERVED to their actual observations and ABOUT to component identities. Evaluation runs are never eligible producers. A/B do not read one another's histories. Fresh C receives either no records, the chronological records, or exactly the same records grouped by component. RETRIEVED edges show exposure; CITED edges show model-declared usage. A citation is not proof that a fact caused a decision.

NEXT retains observation order for inspecting before/intervention/after sequences. Candidate causal interpretations are not automatically promoted to truth. The simulator's full state and target variant stay out of model contexts.

### Checkpoints

Run payload is checkpointed before provider dispatch, after response receipt, and after each local action batch. Resume reconstructs the private simulator by replaying saved actions and comparing observed outcomes, and refuses a mismatch. Completed decisions are not requested again. A response saved before an interruption can be applied locally. Missing responses may require a new explicitly budgeted request.

Older records without ABOUT/NEXT are still readable; component identity is derived from their recorded action. New saves materialize these links. Protocol-2 records remain separate from protocol-3 experiments and are not silently rescored with different budgets.

## Maze lab

| Path | Meaning |
|---|---|
| Episode -CONTAINS→ Observation | Sensor history in one run |
| Episode -CONTAINS→ Action -PRODUCED→ Observation | Action-to-outcome provenance |
| SleepRun -CONSOLIDATES→ Episode | Frozen source for preparation |
| SleepRun -GENERATED→ Hypothesis -SUPPORTED_BY→ Observation | Candidate explanation backed by cited evidence |
| SleepRun -GENERATED→ ProcedureVersion -BASED_ON→ Hypothesis | Reusable candidate procedure |
| Episode -USED→ SleepRun | Which prepared artifact a consumer received |
| Episode -USES_POLICY→ ControllerPolicy | Controller/prompt provenance |
| LocalRule -SUPPORTED_BY→ LocalSample -OBSERVED_IN→ Observation | Learned finite truth-table evidence |
| LocalLearningHead -CURRENT→ LocalRule | Current immutable rule version |
| Episode -USED_LOCAL_RULE→ LocalRule | Frozen local memory consumed by a run |
| LearningEvent -TRIGGERED_BY→ Observation | Major observed state change |
| JobRun | Durable orchestration result and optional per-action evaluator frames for playback; not a model memory source |

Local maze rules are scoped to a stationary two-switch occupancy feature family. A complete, consistent table is only validated in that scope. It is not a universal causal law or model-weight training.

## Removed prototype

The scripted assembly workshop has been removed from application code and UI. Pre-existing Workshop* nodes are left intact in the user's database but are not used by active experiments. No deletion or migration of user history is required to run the new version.

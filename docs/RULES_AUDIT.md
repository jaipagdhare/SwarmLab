# Hackathon rules audit

Based on the rules supplied by the participant, reviewed October 18, 2026. This is a technical readiness record, not organizer approval or a blanket eligibility certification.

| Rule | Assessment | Evidence / remaining action |
|---|---|---|
| 1. FalkorDB primary and central | Technically verified | Source of memory, producer scopes, evidence paths, rule versions and checkpoints. No alternative memory database. |
| 2. Graph does real work | Technically verified for core workflows | Relationship-removal and unavailable-database checks pass; see below. |
| 3. Accepted deployment | Prepared | Docker Compose local FalkorDB; cloud configuration supported. |
| 4. Name entered tracks | Prepared | Enter only **Track 02: Agent Memory and Coordination**. Add other tracks only if explicitly intended. |
| 5. Permitted data | Application data provenance documented | Synthetic simulator data and own generated outputs; no restricted-data importer. See DATA_PROVENANCE.md. |
| 6. Event window and deadline | Participant action required | Closing: Oct 18, 2026, 23:59 IST = 18:29 UTC = **20:29 Europe/Berlin**. Submit and verify confirmation before then. |
| 7. Coding/design start within event | Participant confirmed | On October 18, 2026, the participant confirmed that main coding/design began after Oct 15, 00:01 IST = Oct 14, 18:31 UTC = Oct 14, 20:31 Berlin. This is participant attestation, not an independently verified timestamp. |
| 8. Reuse vs original work | Documented, participant review required | Dependencies/inspiration credited. Do not claim reused frameworks as original implementation. |
| 9. Submission deliverables | Prepared locally; publication pending | README, model, queries, demos, full local setup, track. Public repo currently needs the prepared code/video pushed; publication has been authorized by the participant. |
| 10. Disclose AI assistance | Added | AI_ASSISTANCE.md and README disclose extensive Codex assistance. Include it in the submission form too. |
| 11. Participant understanding | Cannot certify automatically | Review UNDERSTANDING.md and personally demonstrate the listed checks. |
| 12. Meaningful participant contribution | Documented but organizer judgment remains | Participant decisions/testing feedback recorded; substantial AI-generated implementation disclosed. Personal understanding/verification still essential. |
| 13. Prizes | Informational | No eligibility or prize guarantee is made. |
| 14. Ownership | Three-person team confirmed; rights review remains | On October 18, 2026, the participant clarified that they are working with two other people (three team members total), superseding the earlier solo interpretation. Team member names, contributions, third-party rights and the team ownership agreement should be confirmed by the team. |
| 15–17. Conduct, no plagiarism/manipulation | Ongoing participant obligations | No fabricated results or altered success claims. Follow event Code of Conduct; no automatic certification of future behavior. |

## Graph-dependency verification

Run with the local database configured:

```bash
.venv/bin/python scripts/audit_graph_dependency.py
```

The script creates a uniquely named scratch graph and deletes only that graph. It makes zero model calls and never disconnects the production database.

Checks passed:

1. With an `IncidentRun -OBSERVED→ IncidentObservation` edge, the specialist evidence is retrieved. Removing just that edge leaves the observation node and payload intact but removes it from retrieval.
2. With `LocalLearningHead -CURRENT→ LocalRule`, the current learned rule is available. Removing just the edge leaves the rule payload intact but makes current-rule retrieval return no memory.
3. Pointing the incident workflow to an unavailable loopback database endpoint raises a connection error.
4. Pointing local maze transfer to that unavailable endpoint also raises a connection error; there is no JSON-file learning fallback.

Additional real paths include `LocalRule → LocalSample → Observation` and `ProcedureVersion → Hypothesis → Observation`. The app's model contexts consume these traversals. UI previews and unit-test simulators can still render or simulate without a database; those are not the persistent memory/transfer product. Legacy report viewing may read exported files, but exports do not supply agent learning. Do not claim every line of code requires a database or that storing JSON properties is itself graph reasoning.

The graph requirement does not mean a competitor could never rebuild the product with a different architecture. It means this implementation's central memory workflows actually depend on FalkorDB and its relationships. Judging remains with the organizers.

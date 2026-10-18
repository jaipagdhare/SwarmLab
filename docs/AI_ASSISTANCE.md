# AI-assistance disclosure

OpenAI Codex was used extensively during development. It assisted with experiment design, generated substantial application code, implemented changes, debugged errors, wrote and ran automated tests, inspected FalkorDB data, prepared documentation, and scripted the captioned browser recordings. The recorded simulator actions and stored model traces are actual outputs; their results were not replaced with fabricated successes.

This submission must not describe the implementation as entirely hand-written by the participant or describe AI-run tests as independent human verification.

## Participant contributions evidenced by the project discussion

The participant selected the graph-memory problem and FalkorDB hackathon, configured the database and model access, ran experiments, supplied actual failures and traces, imposed quota constraints, required learning to live in FalkorDB rather than JSON files, challenged weak claims, rejected the scripted lookup workshop, chose the incident-response experiment after review, and directed the maze demo and submission scope. Those are product decisions and hands-on feedback, not a claim of independently authoring every implementation detail.

## Participant verification still required

Before submitting, the participant should personally run the local setup, inspect the graph queries, review relevant code, reproduce an experiment, and be able to explain why the graph is required. Use [UNDERSTANDING.md](UNDERSTANDING.md). Record only checks actually performed; do not backdate or invent contributions, commits, verification, or project start dates.

Meaningful participant contribution and technical understanding are eligibility requirements, not something a generated disclosure can establish. The organizers make the final determination. If the participant cannot explain and verify the work, the project is not ready to submit under these rules.

## Model use within the product

The optional live controller uses the configured Gemini API. The maze video's controller is deterministic symbolic Python code, not Gemini. Gemini model use is distinct from Codex assistance in building the application. Model credentials remain local and are excluded from the source bundle.

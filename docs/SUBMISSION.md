# Graph Hacks submission pack

## Entry

**Project:** SwarmLab — Shared experience, observable decisions

**Track:** Track 02 — Agent Memory and Coordination

**Team:** Three members (the submitter and two teammates). Add all three names in the submission form.

**Public repository:** https://github.com/jaipagdhare/graph-hacks

**Deployment:** complete local setup in README (loopback-only app, FalkorDB Docker volume)

**Primary demo:** [Maze learning and transfer](maze-demo.webm) — real recorded learning, successful unseen-seed transfer, persistence after reload, and an actual FalkorDB evidence query. Silent video with captions. The controller is local and symbolic.

**Supplementary demo:** [Incident-lab walkthrough](demo.webm) preserves the actual Gemini successes, failures, and quota interruption. Publish this file in the repository or upload it to a video host and use the public link in the form.

## Ready-to-paste description

The primary demo shows a real cooperative maze run: a local symbolic controller operates three robot bodies, adds switch/gate observations to FalkorDB, and transfers its frozen learned rule to an unseen layout. Seed 708 succeeds in 41 actions with zero API calls. The video shows every action, persistence after reload, and the graph path back to supporting observations. This is not presented as three independent LLMs or proof of improved LLM reasoning.

SwarmLab is an evidence-linked memory lab built on FalkorDB. Independent agents investigate simulated incidents and save their observations. A fresh agent receives a new incident under three conditions: no historical memory, shared raw history, or graph-retrieved evidence. The simulator independently measures recovery, lost work, and action cost. Every retrieved or cited observation can be traced back to its producer.

The product includes persistent checkpoints, explicit API budgets, quota-safe manual resume, and a separate cooperative maze experiment with local symbolic learning. FalkorDB is the memory source of truth: observations, producer relationships, component links, temporal sequences, and consumer citations are graph records, not JSON-file memory.

We preserve negative results. In the recorded pilot, both completed consumer conditions failed to repair a combined outage, and the graph trial was interrupted by provider quota. That motivated stronger before/after evidence collection and an equal recovery turn for all consumers. The project demonstrates inspectable cross-agent memory infrastructure; it does not claim a proven graph-memory success advantage from an incomplete trial.

## Required items

| Requirement | Prepared artifact | Final check |
|---|---|---|
| Public source repository | Code prepared for the repository above | Push the prepared changes and verify while signed out |
| README with setup + graph model | README.md, docs/GRAPH_MODEL.md | Run setup in a fresh clone |
| Core Cypher/algorithms | queries/*.cypher + queries/README.md | Queries have been executed against FalkorDB |
| Working demo video | docs/maze-demo.webm (primary), docs/demo.webm (supplementary) | Open playback; publish URL accessible to judges |
| Deployment or complete local setup | README.md + compose.yaml + pinned Python dependencies | Local setup is the chosen submission path |
| Track | Track 02: Agent Memory and Coordination | Select that track in the submission form |

## Submission sequence

1. Review the source changes and video. Do not expose `.env`, credentials, private machine folders or raw local exports.
2. Push the prepared source to the existing public repository; this preserves its initial commit.
3. Ensure the repository README and video are readable without login. A separate hosted video link can be easier for judges than a repository download.
4. In WeMakeDevs, enter the project name, description, repository URL, demo URL, track, and local-setup explanation.
5. Do not submit an invented live deployment URL. Use the README local setup as permitted by the rules.
6. Verify submission confirmation in the event dashboard.

Official event: https://www.wemakedevs.org/hackathons/falkordb. Checked October 18, 2026. The page lists closing at October 18, 11:59 PM IST (18:29 UTC / 20:29 Berlin on that date). The event dashboard remains the authority for submission status and any changes.


## Required AI disclosure for the submission form

OpenAI Codex was used extensively for collaborative design, substantial code generation, debugging, automated testing, documentation and video-recording scripts. The participant directed scope and experiment choices, configured services, ran experiments, supplied failure traces, rejected weak demonstrations and requested revisions. The implementation is not claimed to be entirely hand-written. See AI_ASSISTANCE.md for details. The participant must personally verify and understand the submitted work.

## Eligibility checks still required

Review [RULES_AUDIT.md](RULES_AUDIT.md) and complete the personal checklist in [UNDERSTANDING.md](UNDERSTANDING.md). Do not submit a blanket claim that all rules are verified: the participant confirmed the eligible coding/design start and subsequently clarified a three-person team submission on October 18, 2026. Rights review, technical understanding, public publication, and timely submission still require participant action.

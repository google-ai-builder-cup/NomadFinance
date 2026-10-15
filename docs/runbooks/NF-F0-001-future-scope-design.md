# NF-F0-001 — Future Scope technical design addendum

> The design addendum this task wrote has since been removed from the repository; it stays in git history.

## Summary

The design that every Future Scope task builds from: the flag-gated **Pre-Departure Financial Coach** and **Real-Time Scam Message Analyzer**, added beside the four v1.0 pillars without changing them. It is a document and diagrams only: no code, no data, no configuration.

| Deliverable | Where |
|---|---|
| New pipeline diagrams | `docs/mermaid/financial-coach-pipeline.mmd`, `docs/mermaid/scam-analyzer-pipeline.mmd` |
| Updated diagrams | `docs/mermaid/system-architecture.mmd`, `cross-pillar-data-flow.mmd`, and the four pillar files (`remittance-xray`, `contract-shield`, `exploitation-radar`, `financial-identity`) |

It was merged on 2026-10-06 (PR #108, `docs/NF-F0-001-future-scope-design`, commit `2059ff5`). Owner: Aditya. Reviewer: Devam.

The tracker row asks for: component and sequence diagrams (Mermaid) for both modules, model routing per step, new Firestore collections, and the cross-pillar touchpoints. All four are in the document.

## What is in the document

| Section | What it fixes |
|---|---|
| 1 Scope and non-goals | What is designed here and what is left to other tasks (schemas, collection fields, rules, question bank, rubric, taxonomy) |
| 2 Principles | Additive and flag-gated (`require_flag`, a `404` when off, rollback is "flag off first"); `/api/v2` surface; model **tiers** instead of model names (the tracker's labels mapped to `REASONING`, `EXTRACTION`, `CLASSIFICATION` and the embedding model); the Gemini rules; data handling (redaction, no stored screenshots, no fetching of URLs from messages, account deletion) |
| 3 System context | One flowchart: lazy frontend chunks behind `FlagGate`, `api/v2`, the services, the v2 Gemini client, Firestore |
| 4 Financial Coach | Components, the interview turn (sequence), the session state machine, the score and plan (sequence), guardrails, check-ins, failure behaviour |
| 5 Scam Analyzer | Components, analyze (sequence, with parallel classification and similar-scam retrieval), report to Exploitation Radar (sequence), safety properties |
| 6 Model routing and quota | 12 steps, each with its tier and task, the rule "the cheapest tier that passes the eval", and the reasoning-tier quota risk (about 31 complete coach sessions a day at 500 requests) |
| 7 Firestore additions | Seven new collections with writer, client access and retention, and the existing collections that gain fields |
| 8 Cross-pillar touchpoints | Nine flows between the new modules and the four pillars, with the mechanism, the consent rule and the task for each |
| 9 Cross-cutting | Logs, metrics, quota guard, rate limits, idempotency, accessibility, languages, testing, rollout |
| 10 Which task cites which section | The table that lets any later task cite a section of this file |
| 11 Open questions | Eight points for the walkthrough |

**Tags.** Every statement is marked **[T]** (stated by a row of the tracker), **[P]** (proposed here, because nothing else defines it) or **[built]** (already in the repo). The document has 49 [T], 23 [P] and 3 [built] marks. A [P] may be refined by the owner of the named task, who tells the team when a name changes.

## Decisions taken in the document

- **Design choice for the turn.** Slot extraction runs **before** the reply, so a clarifying question replaces a guess and the reply already knows the next stage. The cost is one fast-tier round trip before the first token, against a goal of a first token under 2 s at p95. If that is missed, start the reply at once and deliver the facts as a `slot_update` before `done` (section 4.2).
- **Retrieval beside the classifier.** Similar-scam retrieval runs in parallel with the verdict and its results go to the client, not into the classifier prompt, so a poisoned pattern cannot steer the verdict (section 5.2).
- **Radar reports skip free-text validation.** A report can only be made from a check the analyzer itself marked as a scam, so it enters the Radar pipeline at the embedding step (section 5.3).
- **A benign verdict costs less.** It gets a short reassurance on the fast tier, not the explainer on the reasoning tier (section 5.2).
- **Embedding size.** Firestore vectors are capped at 2048 numbers and `gemini-embedding-001` returns 3072, so 768 is used everywhere (section 2.3).
- **A pillar never depends on a new module.** With both flags off, all nine cross-pillar flows are inert; flows into Radar are anonymised (section 8).

## Where each open question went

Section 11 left eight points open. What happened to them (from the later tasks):

| # | Question | Answer, and where |
|---|---|---|
| 1 | UAE and Australia in the baselines | Australia, no UAE anywhere (decided 2026-10-06, D-102). NF-FC-003 to -005 curated all six hosts: SG, AU, KR, MY, JP, HK |
| 2 | Scam report shape in Radar | Decided by NF-F0-003 (`radar.md`, "Scam reports"; D-101) |
| 3 | Shared or per-user scam cache | Per user (NF-F0-003, D-101) |
| 4 | Coach reply model and quota | Decided by NF-HR-010: the reply stays on the fast tier, the cheapest there is. The demand is the fast tier's, not the reasoning tier's; the ready lever is `GEMINI_COACH_REPLY_TIER=extraction` (`NF-HR-010-gemini-quota-guard.md`). Per-feature daily budgets are built |
| 5 | Extraction before or after the first token | Built as designed (before). The first-piece time is not yet measured (D-211) |
| 6 | Tracker names against repo names | Answered by NF-F0-002 (D-101): conventions in `docs/api/v2-conventions.md`, mocks in `docs/mocks/<feature>/` |
| 7 | Account deletion | Plan PDFs live under `exports/{uid}/`, which deletion already clears; the rest is under `users/{uid}`, deleted recursively (`coach.md`) |
| 8 | `/api/v2` layout | `backend/app/api/v2/`, confirmed by NF-F0-002 |

## How later tasks use it

- Cite a section by number: section 10 lists, for each section, the tasks that rely on it. The addendum itself is not a contract; the contracts are `docs/api/v2-coach.md`, `docs/api/v2-scam.md` and the collection documents in `docs/data-model/collections/`, which cite it.
- When a [P] name changes, the owner updates the section that names it, in the same pull request.
- The diagrams in `docs/mermaid/` are the source of the pipeline pictures; dashed outlines mean "future scope, behind a flag, not deployed".

## Checks run (2026-10-09)

| Check | Result |
|---|---|
| Every task id the document cites exists in the tracker | 58 ids cited, none missing from the tracker export |
| Structure | 11 sections numbered in order; 8 Mermaid blocks, all fences closed |
| Diagram files | The four named in the table exist: `system-architecture` (134 lines), `cross-pillar-data-flow` (38), `financial-coach-pipeline` (49), `scam-analyzer-pipeline` (42) |
| Tags | Every claim carries [T], [P] or [built] (49, 23, 3) |

**Not checked here:** that the Mermaid diagrams render. Paste a block into the Mermaid live editor; a syntax error shows at once.

## Definition of Done

Tracker row: *Doc merged; reviewed by both other teammates in a 30-min walkthrough; every later task can cite a section of it.*

- [x] Doc merged (PR #108, 2026-10-06)
- [x] Every later task can cite a section (section 10; all cited task ids exist)
- [ ] Reviewed by both other teammates in a 30-minute walkthrough: **nothing in the repository records it**. The document header still says "draft for the walkthrough". If the walkthrough happened, change the header to the review date and the names of the reviewers.

## Noticed, not fixed

- The header says **"Status: draft for the walkthrough, 2026-10-06"**.
- **D-101** (open, owner Aditya): section 11 still lists as open the questions that are answered above, and three statements are out of date: section 2.5 (stored scam checks also hold the scam's contact points), section 5.3 (the report carries the full scam details and worker-confirmed indicators), and the section 7 table (an eighth collection, `scam_indicators`; plan translations are a subcollection; plan PDFs under `exports/{uid}/`; the TTL values). This runbook does not edit the addendum; D-101 is the place for that edit.
- Section 6 and the section 2.3 table use the tracker's model labels ("2.5 Flash", "1.5 Flash") for the tiers; the model IDs today are those of ADR-002 and `backend/app/config.py`.

## Commit

Written on `main`. Commit message:

```
docs(future-scope): add NF-F0-001 runbook
Refs: NF-F0-001
```

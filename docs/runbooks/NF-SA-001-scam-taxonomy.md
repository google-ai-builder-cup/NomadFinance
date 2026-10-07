# NF-SA-001 — Scam Taxonomy and Manipulation-Tactic Catalogue

## Summary

Curated reference data for the Scam Analyzer (Future Scope): 8 scam types and 6 manipulation tactics, loaded to Firestore `scam_taxonomy/{id}`. The classifier uses them as grounding (design 5.2), the explainer names tactics by id, and a report to Radar uses the type label as its `entity_name`. Data-scripts only: no backend, frontend or rules change.

Not in this task: translations (the screens translate by id through the `scam` i18n namespace, NF-F0-013 and NF-SA-019), scam templates and embeddings (NF-SA-006), the golden eval sets (NF-SA-003, -004, -005) and the classifier prompt (NF-SA-007). The Firestore rules already let signed-in users read `scam_taxonomy` (NF-F0-004).

## What the data holds

Types (order in lists, default risk, tactics it usually uses):

| id | Label | Risk | Tactics |
|---|---|---|---|
| `fake_job_offer` | Fake job offer | high | scarcity, urgency, social_proof |
| `illegal_recruitment_fee` | Illegal recruitment fee | high | urgency, scarcity, authority |
| `remittance_otp_phishing` | Remittance or OTP phishing | high | urgency, authority, fear |
| `loan_app_trap` | Loan app trap | high | fear, urgency |
| `authority_impersonation` | Embassy or authority impersonation | high | authority, fear, urgency |
| `investment_romance` | Investment or romance scam | high | reciprocity, social_proof, scarcity |
| `lottery` | Lottery or prize scam | medium | urgency, authority |
| `other_scam` | Other scam | medium | urgency, authority |

Tactics: `urgency`, `authority`, `scarcity`, `fear`, `reciprocity`, `social_proof`.

Every entry has a definition, 3 to 6 signs, a `safe_response` and at least one source. A type also has `default_risk` and `related_tactics`; a tactic also has `how_it_works`. A tactic's `safe_response` is how to resist the pressure. This was agreed for NF-SA-001 because the tracker asks for a safe response on every entry; `docs/data-model/collections/scam.md` was updated to match.

`other_scam` is the type for a real scam that fits none of the others. The classifier should prefer it to forcing a wrong type.

Sources: ScamShield and the Singapore Police Force (job, phishing, investment, love, crypto, loan, unlicensed moneylending and official-impersonation pages), the Department of Migrant Workers of the Philippines (archived POEA pages on recruiters), the ILO fair-recruitment principles, Scamwatch (Australia), and, for the tactics, the UK NCSC, a Montgomery County (Maryland) police page on fraud influence principles, and Stajano and Wilson's scam-principles paper. Each page was opened on 2026-10-07 (`retrieved_on`). The text is written in plain English from those pages, not copied.

## Files

| File | Change |
|---|---|
| `data-scripts/data/source/scam-taxonomy/types.json`, `tactics.json` | New: the curated content |
| `data-scripts/src/validators/scam_taxonomy.py` | New: schema and cross-checks (`python -m src.validators.scam_taxonomy`) |
| `data-scripts/src/loaders/scam_taxonomy.py` | New: validates, then writes `scam_taxonomy/{id}` and `_meta` in one batch |
| `data-scripts/src/config.py` | `SCAM_TAXONOMY_DIR` |
| `data-scripts/tests/test_scam_taxonomy.py`, `test_scam_taxonomy_loader.py` | New: 28 tests, with a fake Firestore client |
| `data-scripts/README.md` | Section for the checker and loader |
| `docs/data-model/collections/scam.md` | `safe_response` on tactics, `other_scam`, hash scope |

## Run it

From `data-scripts/`, with the virtual environment active (see the README, "Setup").

```bash
python -m src.validators.scam_taxonomy          # expect: OK   8 type(s), 6 tactic(s)
python -m src.loaders.scam_taxonomy --dry-run   # no Firestore access
python -m src.loaders.scam_taxonomy             # write
```

Writing needs `gcloud auth application-default login`, or `FIRESTORE_EMULATOR_HOST` pointed at a running emulator. The project is `nomadfinance-prod` unless `FIREBASE_PROJECT_ID` says otherwise.

To check the result: in the Firestore console (or emulator UI) `scam_taxonomy` has 14 documents plus `_meta`. Run the loader again: the log says `unchanged` and `_meta.version` stays the same.

## How the version works

`_meta.version` starts at 1. The loader hashes every entry (SHA-256 of the entries in canonical form) and raises `version` by 1 only when the hash differs from `_meta.content_hash`. A stored scam check records `taxonomy_version`, and the check cache treats a check made under another version as a miss (`docs/data-model/versioning.md`), so a wording change makes the next check of the same message run again.

`sources` and `curator` are not hashed: checking a source page again, or a change of curator, does not say anything different to a worker and must not retire every cached verdict.

## Editing the content

1. Edit the JSON. Keep the text short and plain: a definition is at most 260 characters, a sign 130, an answer 400 (the checker enforces this).
2. Every claim needs a source you opened. Put the page in `sources` with the date you read it.
3. Run the checker, then the loader with `--dry-run`, then the loader.

A new type or tactic id also needs `scam.types.<id>` or `scam.tactics.<id>` in the i18n files of all six languages, and a pattern set in NF-SA-006. The checker requires the 8 type ids and 6 tactic ids above, because later tasks refer to them by name.

## Limits

- The language is English only; translations of the labels are i18n keys, and the explainer is written in the worker's language by the model.
- The sources are mostly from Singapore, the Philippines and Australia. Pages for India (eMigrate), Indonesia (KP2MI) and Nepal were not readable by the tools used (empty or blocked pages), so they are not cited. The safe responses give generic wording ("your local anti-scam helpline", "your government's migrant worker office") and name Singapore's ScamShield 1799 as the one example.
- The DMW pages are the archived POEA pages; the Philippine placement-fee rule (one month's salary) is stated as the Philippine rule only.
- The Scamwatch page was opened in the browser pane, but its text was not read (the page check failed); the claim cited from it (a prize that asks for a fee) comes from the Scamwatch summary shown in search results. Re-read it before the final review.
- The loader was tested against a fake Firestore client, not against the emulator or the live project.
- Review by a teammate is still open (`curator` is `AB`).

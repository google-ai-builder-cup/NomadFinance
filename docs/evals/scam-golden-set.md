# Scam golden eval sets

What a correct Scam Analyzer should answer for 120 messages, written down before the analyzer exists. Three files of 40, one per pair of languages, all in this format:

| File | Languages | Task | Owner |
|---|---|---|---|
| `data-scripts/evals/scam_golden_en_hi.jsonl` | English, Hindi | NF-SA-003 | Devam |
| `data-scripts/evals/scam_golden_tl_id.jsonl` | Tagalog, Bahasa Indonesia | NF-SA-004 | Aditya |
| `data-scripts/evals/scam_golden_ne_bn.jsonl` | Nepali, Bengali | NF-SA-005 | Pranjal |

The eval runner (NF-SA-014) feeds each `text` to the analyzer and compares the answer with the label. The bar it enforces is **F1 of at least 0.85 for scam against benign overall, and at least 0.75 in every language**, with 15 of 15 injection attempts still classified on content (NF-SA-020). The schema, the checks and the commands are in `data-scripts/src/validators/scam_golden.py`; this page is the rulebook for the labels.

## One row

One JSON object per line, `utf-8`, no comments.

| Field | Meaning |
|---|---|
| `id` | `gold-<language>-<nnn>`, numbered from 001 with no gap in each language |
| `language` | `en`, `hi`, `tl`, `id`, `ne` or `bn`: the language of the message |
| `script` | `native`, or `latin` for a message typed in Latin letters. Hindi is often written that way (Hinglish) and the analyzer must read it; English is always `latin`. Tagalog and Indonesian are written in Latin letters natively, so every `tl` and `id` row is `native` |
| `text` | The message **as the worker would paste it**, before redaction. 10 to 4,000 characters |
| `is_scam` | The label the analyzer is scored on |
| `scam_type` | A taxonomy type id (`data-scripts/data/source/scam-taxonomy/types.json`) for a scam; `null` for a benign message |
| `tactics` | 1 to 3 taxonomy tactic ids for a scam: the pressure the message really uses. Empty for a benign message |
| `risk_level` | `low`, `medium` or `high` (rubric below). Always `low` for a benign message |
| `rationale` | One line, in English, 20 to 160 characters: why this label. A reviewer who does not read the language still checks the label from it |
| `resembles` | Benign messages only: the scam type this look-alike imitates. A scam has `null` |
| `corridor_id` | Optional: the worker's route, one of the six corridors |
| `channel` | `sms`, `whatsapp`, `email` or `social` |
| `provenance` | `synthetic` (every row of the first release) or `anonymised` |
| `curator` | Initials of who wrote and labelled it |
| `reviewed_by` | Initials of the second person who checked the label, or `null`. Must not be the curator |

## The labels

**Is it a scam.** A message is a scam when it tries to get money, a one-time code, credentials, an identity document or a payment from the worker by deceit. Everything else is benign, **including a legitimate message that looks frightening or asks for something** (a bank's one-time password, a lender's due-date reminder).

**Which type.** Pick the mechanism of the thing being asked, not the story around it. When two fit:
- A job offer that asks for a fee now is `illegal_recruitment_fee`; one that only asks for documents, details or a contact is `fake_job_offer`.
- A threat to expose photos or contacts over a loan is `loan_app_trap`, even if it also hurries the worker.
- A message that pretends to be someone the worker knows, or a parcel or delivery fee, is `other_scam` unless a type above fits better. Prefer `other_scam` to a wrong type.

**Which tactics.** The pressure the message actually uses, at most three, from the six in the taxonomy: `urgency` (a deadline), `authority` (pretends to be a bank, police, embassy or ministry), `scarcity` (few places), `fear` (a threat), `reciprocity` (a favour or affection that creates an obligation), `social_proof` (others already profit). Do not add a tactic the text does not show.

**Risk level.** How much is at stake if the worker acts on it:

| Level | When |
|---|---|
| `high` | It demands money, a one-time code, credentials or an identity document now, or it threatens |
| `medium` | A set-up: install an app, join a group, message a number. Nothing is paid yet, but the next step costs money |
| `low` | It asks for nothing but a reply (a prize message) |

**Benign look-alikes** are the hard half. Each one imitates a scam type and gets it right: it comes from the real sender, asks for nothing the worker should not give, and often tells the worker how to stay safe ("never share this code", "you pay no fee", "log in to the website yourself"). Every benign row names `resembles`, so the report can say which scam type causes the false alarms. A look-alike must be one a careful person would call safe, not a message that is merely unclear: when unsure, leave it out.

## The messages are invented

No real worker's message, number or link is used, and nothing in a file may be a live contact point. The validator refuses what could be real:
- a link must be on a reserved name (`https://...example`, `.invalid`, `.test`);
- an email address must be at a reserved name (`hr@brightpath-hire.example`);
- a phone or account number of 8 or more digits must contain a run of six zeros (`+65 0000 0031`, `0000-0000-1234`), which no real number does;
- a bare real domain such as `bit.ly` or `site.com` is refused: write it as a `.example` link.

Agencies, banks and people in the messages are fictional (`Bright Path`, `FreshMart`). Where a scam imitates a real authority, the authority is named the way real scams name it (a ministry, a police force, an embassy), because that is the pattern the analyzer has to recognise. A message must not target a real private company.

An `anonymised` row (not used yet) is a real message with every identifier removed; it is exempt from the check above and needs a note in its pull request saying how it was anonymised.

## What a set must contain

Checked by `python -m src.validators.scam_golden`:
- exactly 40 rows; each language 18 to 22; 26 to 30 scams, the rest benign;
- every scam type in at least two scam rows, every tactic used, and low, medium and high risk all present;
- at least five different types among the benign look-alikes;
- no two rows with the same text, and ids with no gap.

The first set (English and Hindi) is 14 scams and 6 benign look-alikes in each language: two each of fake job offer, illegal recruitment fee, remittance or OTP phishing, loan app, authority impersonation and investment or romance; one lottery and one other scam; the benign ones resemble six different types. Ten scams of each language are `high`, three `medium` and one `low`. Five of the 20 Hindi messages are typed in Latin letters. The routes are mostly SG-IN, AU-IN and SG-PH; MY-ID and JP-PH are left for the Tagalog and Indonesian set.

## Reviewing a set

A second teammate checks 10 labels before the set is merged (NF-SA-003: "second teammate spot-checks 10 labels"). From `data-scripts/`:

```bash
python -m src.validators.scam_golden --spot-check 10
```

prints a fixed sample (the same ten every time for the same file): at least three benign rows, both languages, many types, each with its label and rationale. For each one the reviewer answers: *is this a scam, is the type the right mechanism, is each tactic really in the text, is the risk level by the table above, and is the rationale true?* A label they agree with is marked by putting their initials in `reviewed_by` on that row. A label they would change is discussed with the curator and fixed in the same pull request. Before merging:

```bash
python -m src.validators.scam_golden --require-reviewed 10
```

A reviewer who reads the language checks the message itself; one who does not checks the rationale and the label against this page and says so in the pull request. A native speaker should still read every row of a language the team does not read (Hindi was written without a native reviewer, see D-127).

## Changing a set

Add or change rows, run the validator, and keep the ids contiguous. A change to a label after the eval runner has recorded a baseline is a change to the benchmark: say so in the pull request, and re-run the baseline in the same change (NF-SA-014).

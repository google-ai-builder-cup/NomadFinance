# NF-SA-011 — Indicator extraction: links, phones, lookalike domains

## Summary

`POST /api/v2/scam/analyze` now returns real `indicators`: the links, phone numbers, emails and handles in the message (and the sender a screenshot shows), each with flags from fixed rules. **No model is involved, and nothing is ever fetched, opened or looked up**: the rules read the text of an address and nothing else.

| Flag | Meaning |
|---|---|
| `shortener` | A link-shortening service (`bit.ly`, `tinyurl.com`, ... 25 listed): it hides where the link goes |
| `punycode` | An address with `xn--` labels, including one typed in another alphabet: a classic way to make one that reads like another |
| `lookalike` | Copies a real organisation's address (64 listed, the ministries, police, banks and remittance companies of the six countries); `imitates` names the real one |
| `premium_rate` | A number that bills the caller: Singapore `1900`, Australia `190X`, international `+979` |
| `unexpected_country` | A number with a country code outside the worker's route (for `SG-IN`: not 65 or 91) |

The same step also finds the **amounts** the message names (`SGD 800`, `RM 1,500`, `Rp 5.000.000`, `₱ 2,500`, `3000円`). They are not returned: the contract has no field for them, and `details.amount_requested` stays the classifier's. They go to the classifier as a check on the amount it reads.

**The classifier now gets the signals** (prompt `scam/classify.v2`): the flags, `imitates` and the amounts, **never a link or a number**. A phone number in a message may be the worker's own, and a scammer's address helps no model that cannot open it, but "this link copies mom.gov.sg" does. The prompt says signals are hints: a flag never makes a message a scam on its own, and no flag does not make it safe.

Not in this task: `seen` (stays `null`, D-145), the explainer using the signals (D-146), more premium-rate ranges (D-144), storing a check (NF-SA-012). The dependency NF-SA-002 (the contract) is merged.

## How it works

```
raw text ─ redact_values ─→ [URL] [EMAIL] [PHONE] values ─┐
   │                                                        ├─ extract_signals ─→ indicators (≤ 10) for the answer
   └─ redact_text ─→ redacted ─ @handles, amounts ──────────┘                  └→ flags + amounts for the classifier
```

- **Same idea as the masking.** `app/core/redact.py` gained `redact_values(text)`, which returns the values its own rules would mask, with their token. So "a phone number" and "a link" mean the same thing here and in the masking, and a bank account or an ID (masked as `[ACCOUNT]`, `[ID]`) is never an indicator: it can be the worker's own, and the data model's exception covers only the scam's contact points.
- **Raw text is read once**, in `analyze_text` and `analyze_screenshot`, before masking, and goes no further. The values appear in the answer's `indicators` (the data model allows that) and nowhere else: not in the prompt, the answer's text or a log. The log line has kinds, flags and counts.
- **Order and limit.** Indicators come in the order they appear, with no repeats (the same number written two ways is one: the id is the first 8 hex characters of `sha256("<kind>:<normal value>")`, the data model's key). More than 10 keeps the flagged ones.
- **Lookalike rules** (`indicator_checks.py`): the real name inside a longer host (`mom.gov.sg.verify-now.com`, `dbs-com-sg-login.net`), one letter or look-alike character away (`rnaybank2u.com.my`, `d8s.com.sg`, with `rn`→`m`, `8`→`b`, `0`→`o`, `1`→`l`), or a distinctive brand wrapped in other words (`gcash-promo.xyz`). **A listed domain, its subdomains and any host under a government-only suffix (`.gov.sg`, `.gov.au`, `.gov.in`, `.gov.ph`, `.gov.my`, `.go.id`, `.go.jp`) are never flagged**: `moe.gov.sg` is another real ministry, not a copy of `mom.gov.sg`. A short name in the middle of a host (`i-wise.com.au`) is not flagged either.
- **Premium-rate ranges** are only the ones a regulator publishes and that were checked on 2026-10-07: Singapore 1900 (IMDA national numbering plan, 11 digits), Australia 190X XXX XXX (ACMA numbering plan), the ITU's `+979` international premium rate range. Japan's old `0990` ended in 2013 and the current Japanese range was not confirmed, so none is listed; India, the Philippines, Malaysia and Indonesia were not looked up (D-144). Sources: [IMDA numbering plan](https://imda.gov.sg/-/media/imda/files/regulation-licensing-and-consultations/frameworks-and-policies/numbering/national-numbering-plan-and-allocation-process/chapter_14_other_numbering_schemes.pdf), [ACMA, choose your phone number](https://acma.gov.au/choose-your-phone-number), [ITU-T E.169.2](https://www.itu.int/rec/T-REC-E.169.2/en). These were read from search summaries of those pages: a person should confirm them (D-144).

## Files

| File | Change |
|---|---|
| `backend/app/services/scam/indicators.py` (new) | `extract_signals`, `Signals` (with `for_prompt`), `make_indicator`; the order, the cap and the log line |
| `backend/app/services/scam/indicator_checks.py` (new) | The rules: shortener, punycode, lookalike, premium rate, unexpected country. No network code |
| `backend/app/services/scam/indicator_data.json` (new) | The curated shorteners and protected domains |
| `backend/app/services/scam/amounts.py` (new) | Amounts next to a known currency, numbers as written in the corridors |
| `backend/app/core/redact.py` | `redact_values` and `MaskedValue`; `redact` behaves as before |
| `backend/app/prompts/scam/classify.v2.yaml` (new; v1 removed) | The classifier prompt with `<signals>` |
| `backend/app/services/scam/classifier.py`, `analyzer.py` | The classifier takes the signals; the analyzer extracts before masking and merges the screenshot's sender |
| `backend/tests/unit/services/test_scam_indicators.py`, `test_scam_amounts.py` (new), `tests/unit/core/test_redact.py` | 40 indicator fixtures, the no-network proofs, the curated lists, amounts, `redact_values` |
| `backend/tests/integration/api/test_scam_analyze.py`, `..._screenshot.py`, `..._live.py`, `test_scam_explain_live.py`, `tests/unit/services/test_scam_classifier.py`, `tests/unit/test_prompt_loader.py` | Updated for the new signature and version; four endpoint tests; two live ones |
| `docs/api/v2-scam.md`, `docs/data-model/collections/scam.md`, `backend/app/prompts/README.md`, `docs/deferred-items.md` | Contract, data model, prompt table, D-144 to D-146 |

No shared files, no new dependency, no workflow change. The response models did not change.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | Reuse the redactor's own rules through `redact_values` | One definition of "a phone" and "a link", so the masking and the indicators cannot disagree |
| 2 | The classifier sees flags and amounts, never values | The data model's rule: nothing that identifies a worker or a contact point leaves the check; a flag is more use to a model than an address it cannot open |
| 3 | `classify.v2` replaces v1 (v1 file removed, as other prompts' old versions were) | The prompt library's rule: new wording, new file |
| 4 | Government-only suffixes are never lookalikes | Otherwise a real ministry would be called a copy of another: a harm to the worker and to trust in the flag |
| 5 | Only regulator-published premium ranges | A wrong range would call a safe number premium |
| 6 | A number with no country code gets no `unexpected_country` | There is no country to judge, and the corridor's home country is common for a local number |
| 7 | Amounts are found but not returned | The contract has no field for them; they are a check for the classifier |
| 8 | Bank accounts, IDs and UPI addresses are not indicators | They may be the worker's own, and the data model's exception is for the scam's contact points |

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .`, `mypy --strict app/services` (backend) | clean |
| `pytest` (backend) | **1767 passed, 96 skipped** (the live tests) |
| The 40 indicator fixtures | All pass: every flag and every kind (URL, phone, email, handle) is covered, and so are the real sites that must **not** be flagged (a listed domain, its subdomain, another ministry, a short name by coincidence) |
| Zero outbound requests | A test patches `socket.getaddrinfo`, `gethostbyname`, `create_connection`, `connect`, `urlopen`, `HTTPConnection.request` and httpx's `send`, and runs every fixture; a second test does the same through the endpoint (without httpx, which the test client itself uses) |
| Mutation checks | Adding a DNS lookup to `is_shortener` makes the no-network test fail; breaking the Singapore premium range fails 5 fixtures; both restored |
| Caught while writing | `sgd800` in lowercase was not read as an amount; fixed (codes match in any case, symbols as written) |
| Not run | The two new live tests (a link that copies a bank, a shortened link in a delivery notice): no Gemini key in this session. Command below |

## Do this: run the two live tests

From `backend/`, backend venv active, key in `.env.local`:

```powershell
$env:RUN_LIVE_GEMINI = "1"
python -m pytest tests/integration/api/test_scam_analyze_live.py -v -s -k "link"
```

They check that a plain-looking message with a bank-lookalike link is judged a scam, and that a delivery notice with a shortened link is not (a model that calls that a scam is over-weighing the flag; if so, soften the sentence in `classify.v2.yaml`).

## Not done, and why

- **`seen` is always `null`** (D-145): nothing writes `scam_indicators` until NF-SA-013.
- **The curated lists need a person's check** (D-144), and premium-rate ranges exist for three regions only.
- **The explainer does not see the signals** (D-146).
- **A lookalike is judged on the address alone**: a real organisation's mirror or partner domain not in the list is not flagged, and a clever copy that is not close to a listed name is missed. A flag is a reason to look twice; no flag is not a promise (the contract says so).

## Definition of Done (backend endpoint; the tracker's own)

- [x] Unit tests for 30 indicator fixtures (40, with every flag)
- [x] Zero outbound requests to any extracted URL (proved with the network patched, and by a mutation)
- [x] Signals passed into the prompt (flags and amounts) and returned in the response (the indicators)
- [x] Tests, lint, format and `mypy --strict app/services` pass
- [x] `docs/api/v2-scam.md`, the data model and the prompts README updated
- [ ] The two live tests run (needs a key)
- [ ] Curated lists checked by a person (D-144)
- [ ] Rate limiting: not this task (the general 10-a-minute budget applies; the 20-an-hour limit is NF-SA-012)

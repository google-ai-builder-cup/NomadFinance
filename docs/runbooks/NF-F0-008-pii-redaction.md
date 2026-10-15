# NF-F0-008 — PII redaction utility

## Summary

`backend/app/core/redact.py` masks personal identifiers in text a worker submitted, so the Scam Analyzer (NF-SA-*), the Coach (NF-FC-*), logs and analytics can handle a message without keeping the identifiers in it. The tracker names the file `backend/core/redact.py`; in this repo it is `backend/app/core/redact.py`.

```python
from app.core.redact import redact, redact_text

redact_text("Call +65 9123 4567, pay account 012-345-678-9, mail a@b.com. Fee SGD 500.")
# 'Call [PHONE], pay account [ACCOUNT], mail [EMAIL]. Fee SGD 500.'

result = redact(text)
result.text      # the masked text
result.counts    # {"[PHONE]": 1, "[ACCOUNT]": 1, "[EMAIL]": 1}: kinds and numbers, never values
result.found     # True if anything was masked
```

| Token | Masks |
|---|---|
| `[PHONE]` | International (`+65 9123 4567`, `+1 (415) 555-0132`) and local formats (PH `0917…`, IN `98765 43210`, SG/HK 8 digits, ID `08xx…`, MY/JP/AU/KR trunk-`0` numbers, `(021) 555-1234`), digits typed one by one, and any number written after a label such as `phone`, `call`, `WhatsApp`, `फोन`, `ফোন` |
| `[EMAIL]` | Normal addresses and the dodges `a [at] b [dot] com` and `a at b dot com` |
| `[ID]` | SG NRIC / FIN, India PAN, voter ID and Aadhaar (4-4-4), JP residence card, MY NRIC, PH SSS / UMID / PhilSys, AU TFN, the common passport shape (1 or 2 letters + 7 or 8 digits: PH, IN, ID, MY, AU, JP, BD, NP), and any number written after `passport`, `NRIC`, `Aadhaar`, `NIK`, `TFN`, `पासपोर्ट` and similar labels |
| `[ACCOUNT]` | Any run of 9 or more digits (groups of 3+), IBAN, UPI addresses (`name@okbank`), and a number after `account`, `a/c`, `card`, `rekening`, `खाता` |
| `[URL]` | `http(s)://`, `hxxp://`, `www.`, and bare domains with a known ending (`bit.ly/x`, `wa.me/…`, `site.co.in`), whole including path and query |

## What it deliberately does not do

- **Amounts, dates, times, percentages, years** are left as written. They are the evidence the analyzer and coach reason about (`coach.md`: "amounts are left as written"), and they identify nobody.
- **Personal names are not masked** (D-108, still open). A pattern cannot find names; it needs a model call.
- Addresses, dates of birth, and OTP / PIN / CVV values are not masked either.
- **It favours masking too much.** A 9-digit order number becomes `[ACCOUNT]`, and one or two digits after a long number go with it. A number's kind is a guess when it has no label: `012-345-678-9` reads as a phone, `123-456-789-0` as an account. A country code written without `+` stays (`tel: 65 [PHONE]`).
- It never fetches, expands or previews a URL (design §2.5); it only replaces the text.

## Behaviour to rely on

- **Idempotent.** The tokens contain no digits, `@`, `.` or `://`, so `redact_text(redact_text(x)) == redact_text(x)`. Checked on every fixture case and on 300 random mixes of cases.
- **Devanagari, Bengali and other native digits** are read as 0-9 for matching (`फोन ९८७६५ ४३२१०` → `फोन [PHONE]`); the original text is what gets cut, so the rest of the message is untouched.
- **Linear time.** Every pattern starts only at the beginning of a run. A 50 KB run of letters takes about 0.05 s; before the fix it took 43 s (the email pattern rescanned from every position). A test guards this.
- **Trailing punctuation stays** outside a URL: `see https://x.top.` → `see [URL].`
- **Counts never hold values**, so they are safe to log or send to analytics.

## How to use it (callers)

Redact **before** the text goes anywhere durable or visible:

| Where | Rule |
|---|---|
| Logging | `logger.info("scam_check", extra={"text": redact_text(text)})`. The module is not wired into the log handler: a filter would run 28 regexes on every line and could mask hex request / user hashes. NF-F0-016 may revisit. |
| Firestore | Store only the redacted text (`scam_checks.redacted_text`, `coach_sessions.messages`). No raw text is stored anywhere. |
| Cache key | Hash the **normalised, redacted** text plus language (NF-SA-012). |
| Radar report | The redacted text goes into the confirmation sheet, where the worker can still remove a name (D-108). |
| Analytics | Send `result.counts`, never text. |
| Prompts | Redact before building the prompt unless the step needs the raw value; the URL host is the one thing NF-SA-011 extracts from the original. |

## Rule order

`_RULES` is ordered, and the order is part of the behaviour:

1. URLs first, so an email inside a query string is masked with its URL and leaves no stray bracket.
2. Emails, then UPI addresses (email-shaped, no dotted domain).
3. Labelled values (phone, passport / ID, account), so a number is called what the message calls it before the generic rules guess.
4. IBAN, then letters-and-digits IDs and passports.
5. `+` phones, then digit-only IDs with a tell-tale grouping (4-4-4, 6-2-4, …).
6. Local phones, then any remaining run of 9 or more digits as `[ACCOUNT]`.

To add a country, add a pattern in step 4 or 5 and a case to the fixture. Do not widen a digit pattern without adding a clean case that it must not touch.

## Files

| File | Change |
|---|---|
| `backend/app/core/redact.py` (new, 209 lines) | `redact`, `redact_text`, `RedactionResult`, the 28 rules |
| `backend/tests/fixtures/pii_redaction_cases.py` (new) | 60 synthetic messages with the values that must go, and 15 clean messages that must stay unchanged |
| `backend/tests/unit/core/test_redact.py` (new) | 105 tests |

No shared file, no new package, no change to existing code.

## Checks run (2026-10-06)

| Check | Result |
|---|---|
| `ruff`, `black --check`, `mypy app`, `mypy --strict app/core/redact.py` | clean (145 files) |
| `pytest tests` | **1,229 passed**, 65 skipped (live / emulator tests); 105 are new |
| Recall on the 60-case fixture | **100%** of 92 personal values removed (the bar is 95%); a value counts as leaked if it, or the last 4 digits of a long number, is still visible |
| False positives on the 15 clean cases | none changed |
| Idempotency | all 60 cases and 300 random mixes |
| Timing | five 20 to 50 KB adversarial inputs, each under 0.1 s |

**Limit of the recall figure.** The fixture and the patterns were written together, so 100% is a floor on what was thought of, not a measure on unseen text. A separate set of strings written afterwards found real gaps (spaced digits, IBAN, `+1 (415)` formats, `at`/`dot` emails, bare numbers after `phone`, `(021) 555-1234`), which were fixed and some added to the fixture. The reviewer should add messages of their own; a miss goes in as a new fixture case with its fix.

### "No raw PII in Cloud Logging for a sample request"

Verified at the formatter, not on Cloud Run: a test redacts a message with a phone, an account and an email, logs it through `JsonFormatter`, and asserts none of the raw values is in the line. No endpoint logs message text yet, so there is no request to sample. Re-check on staging when NF-SA-007 or NF-FC-009 lands: send a message with fake PII and search Logs Explorer for it.

## Manual test

PowerShell (from `backend`):

```powershell
.venv\Scripts\python.exe -c "from app.core.redact import redact; print(redact('Call +65 9123 4567, pay account 012-345-678-9, mail a@b.com, see https://bit.ly/x. Fee SGD 500.'))"
.venv\Scripts\python.exe -m pytest tests/unit/core/test_redact.py -q
```

bash:

```bash
.venv/Scripts/python.exe -c "from app.core.redact import redact; print(redact('Call +65 9123 4567, pay account 012-345-678-9, mail a@b.com, see https://bit.ly/x. Fee SGD 500.'))"
.venv/Scripts/python.exe -m pytest tests/unit/core/test_redact.py -q
```

Expected: `text='Call [PHONE], pay account [ACCOUNT], mail [EMAIL], see [URL]. Fee SGD 500.'` with counts of one each, and `105 passed`.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | Patterns, not a model. | It runs on every log line and every stored message at no quota cost, and gives the same answer every time. |
| 2 | Amounts are not masked. | Coach and scam logic need them; `coach.md` already says so. `scam.md` and `radar.md` still show `[AMOUNT]` in their sample text, which needs correcting. |
| 3 | Over-mask rather than miss. | A leaked identifier costs more than a hidden order number. |
| 4 | Not hooked into the log handler. | Cost on every line, and risk of masking hex hashes. Callers redact explicitly. |
| 5 | Matching runs on a same-length ASCII-digit copy, and the cut is made on the original. | Hindi, Nepali and Bengali messages use their own digits, and the patterns stay readable. |
| 6 | Counts instead of a list of matches. | A list of matches would be the PII again. |

## Open items

- **D-108** (names): decide whether the utility, the report step, or the confirmation sheet alone handles them (NF-SA-013).
- **OTP / PIN / CVV** values in a pasted message are not masked; a real one could be pasted.
- **`scam.md` / `radar.md` sample text** shows `[AMOUNT]`, which this utility does not produce.

## Definition of Done (backend utility; the task's acceptance)

- [x] At least 95% recall on a 60-string fixture file (100%, with the caveat above)
- [x] Redaction is idempotent
- [ ] No raw PII in Cloud Logging for a sample request: verified at the log formatter only; re-check on staging when a caller exists
- [x] ruff, black, mypy and unit tests clean
- [ ] Reviewed by Devam

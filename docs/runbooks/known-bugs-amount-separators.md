# Known bugs: dot and comma in a typed amount

Fixed on 2026-10-15 on `fix/small-bug`. Reported from the demo: in Remittance X-Ray, `5.400` was read as 5,400 and `5,10` was refused with no answer. No task id: it comes from the demo walk-through, not from the tracker.

## Summary

Both reports were the documented behaviour, not a random glitch: a dot before exactly three digits was thousands (D-281, known bugs batch 1 item 7) and a comma was never a decimal point (`860bf91`, merged 2026-10-15). Both rules are reversed. The same reader served the Remittance form and the three Financial Identity forms, and the coach money field had its own copy of the old rule, so all four now read amounts the same way.

## The rule

The marks are read by where they sit, not by which keyboard the worker has (`readTypedAmount` in `frontend/src/utils/amountReading.ts`).

| Typed | Read as | Why |
|---|---|---|
| `5.400`, `645.5`, `1.500` | 5.4, 645.5, 1.5 | A dot is always the decimal point |
| `5,10`, `645,50`, `0,5` | 5.10, 645.50, 0.5 | A comma before one or two digits is a decimal |
| `5,400`, `1,530,000`, `1,50,000` | 5400, 1530000, 150000 | A comma before three digits groups thousands (the Indian grouping too) |
| `1,530.50`, `1.530,50` | 1530.50 | With both marks, the last one is the decimal point |
| `1.530.000` | 1530000 | A repeated dot can only group |
| `42.000`, `42,000` for the yen, won (and rupiah in the coach field) | 42000 | No minor unit, so a mark can only group |
| `12.3.4`, `1,2,3`, `5,1000`, `1.5,30` | refused | Not a number |

Zeros at the end of a fraction add nothing, so `5.400` is 5.4 and `645.500` is 645.5 (it used to be "too many decimals" or thousands). More decimals than the currency has (`645.505`) are refused as before.

`5,10` and `5.400` are real small amounts, so on the SGD route (65 to 6,450) they now answer "Enter at least …" instead of the old "use a dot" message or a result for 5,400. Try `645,10` or `645.500` to see an answer.

## What changed

| Where | Change |
|---|---|
| `frontend/src/utils/amountReading.ts` | `readTypedAmount` rewritten as the rule above; `dottedThousands` replaced by `ambiguousReading` |
| `frontend/src/utils/corridors.ts`, `fibForm.ts` | The `decimalComma` problem is gone; comments follow the new rule |
| `frontend/src/utils/coachInput.ts`, `components/coach/MoneyField.tsx` | The coach `parseAmount` uses the shared reader (its own copy of the old rule is removed) and takes a `wholeUnits` flag; the money field sets it for JPY, KRW and IDR |
| `frontend/src/components/common/AmountReading.tsx` | The "We read this as …" line shows for one mark before exactly three digits (`5.400` says 5.40, `5,400` says 5,400), and takes the currency's own decimals when none are passed, so the line and the form never disagree |
| `frontend/src/i18n/*.json` (6) | The two `decimalComma` messages removed (no longer reachable) |
| Tests | `amountReading`, `corridors`, `fibForm`, `coachInput`, `AmountReading`, and a new block in `RemittanceCompare.test.tsx` that types the amounts into the real form; `e2e/remittance.spec.ts` follows the new reading |
| Docs | D-281 reworded, D-338 added, regression suites A and B, the NF-P2-018 runbook |

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Which rule | Dot is always decimal; a comma is thousands before exactly three digits and a decimal before one or two (confirmed by Devam, 2026-10-15) |
| 2 | Scope | The typed fields only: Remittance, the Financial Identity income, savings and bill forms, and the coach money, rate and count fields. The backend readers of free text were left alone: D-338 |
| 3 | Rupiah in the coach field | Treated like the yen and won. Without that, `500.000` rupiah would have become 500 |
| 4 | Indian grouping | `1,50,000` is still accepted, as the coach field already did; the shared reader now takes it everywhere |
| 5 | The reading line | Kept, for the ambiguous shape only. `5.400` could be 5.4 or 5,400 to a worker on another keyboard |

## Checks run (2026-10-15)

| Check | Result |
|---|---|
| Frontend `eslint .` (as CI), `tsc -b`, `tsc -p e2e` | clean |
| Frontend unit, whole suite | 153 files, 1,789 passed |
| `prettier --check` on the changed files | clean (the checkout is CRLF, so it was run with `--end-of-line crlf` on the ones that are) |

**Not verified:** the Playwright suite (`remittance.spec.ts` needs the emulators; its one edited test was read, not run) and the screen in a browser. The form is covered by a jsdom test that types into the real page. No string was added, so there is nothing new for a native speaker to read.

## Test it yourself

Start the app, sign in and open Remittance X-Ray on Singapore to Philippines (SGD, limits 65 to 6,450).

PowerShell:

```powershell
cd frontend
pnpm dev
```

bash:

```bash
cd frontend && pnpm dev
```

Type each value in the amount field and press Compare services:

| Typed | Expect |
|---|---|
| `645,10` | A comparison for 645.10 |
| `645.500` | A comparison for 645.50 |
| `1,530` | A comparison for 1,530 |
| `1.530,50` and `1,530.50` | A comparison for 1,530.50 |
| `5.400` | "We read this as" 5.40 under the field, then "Enter at least" the minimum |
| `5,400` | "We read this as" 5,400 under the field, then a comparison for 5,400 |
| `5,10` | "Enter at least" the minimum (5.10 is below it) |
| `645.505` | "Use at most 2 decimal places." |
| Japan to Philippines route, `42.000` | A comparison for 42,000 yen |

The same values behave the same way in Financial Identity, Log income, Log savings and Log a bill.

Unit tests only:

```powershell
cd frontend
npx vitest run src/utils src/components/common/AmountReading.test.tsx src/pages/remittance
```

## Commit

```
fix(amounts): read a dot as the decimal point and a comma by its digits
```

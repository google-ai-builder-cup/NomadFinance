import { ApiError } from "@/services/apiClient";
import { readTypedAmount } from "@/utils/amountReading";
import type { HostCountry } from "@/types/enums";
import { errorMessageKey } from "@/utils/errors";

/** The currency a worker logs activity in: their own host country's. */
export const HOST_CURRENCY: Readonly<Record<HostCountry, string>> = {
  SG: "SGD",
  MY: "MYR",
  HK: "HKD",
  JP: "JPY",
  KR: "KRW",
  AU: "AUD",
};

// One entry per host currency, not the backend's open ISO 4217 pattern: a short picker with
// no typos beats free text for the six currencies a worker will ever actually use here.
export const LOGGABLE_CURRENCIES: readonly string[] = Array.from(
  new Set(Object.values(HOST_CURRENCY))
).sort();

// The yen and the won have no minor unit.
const ZERO_DECIMAL_CURRENCIES = new Set(["JPY", "KRW"]);

/** Decimal places `currency` uses, for `formatMoney` and amount parsing alike. */
export function currencyDecimals(currency: string): number {
  return ZERO_DECIMAL_CURRENCIES.has(currency) ? 0 : 2;
}

// The most one entry can be, as on the server (backend/app/schemas/fib.py): an extra zero would
// otherwise sit in the profile for a year. The yen and the won run to larger numbers.
export const MAX_AMOUNT = 1_000_000;
export const MAX_AMOUNT_WHOLE_UNIT = 100_000_000;

export type AmountProblem = "empty" | "invalid" | "decimalComma" | "decimals" | "tooLarge";
export type AmountCheck = { ok: true; amount: number } | { ok: false; problem: AmountProblem };

/**
 * Read a worker-typed amount. Accepts "650", "650.50" and thousands grouped with commas ("6,500")
 * or, before exactly three digits, a dot ("6.500"); a comma before one or two digits ("6,5") is
 * refused, never guessed. Unlike `utils/corridors.ts`'s `parseAmount`, there is no survey-based
 * range to check against, only that it is a positive number with no more decimals than the
 * currency allows.
 */
export function parseAmount(text: string, currency: string): AmountCheck {
  const decimals = currencyDecimals(currency);
  const typed = readTypedAmount(text, decimals === 0);
  if (!typed.ok) {
    return text.trim() === "" ? { ok: false, problem: "empty" } : typed;
  }
  const normalized = typed.normalized;
  const fraction = normalized.split(".")[1] ?? "";
  if (fraction.length > decimals) {
    return { ok: false, problem: "decimals" };
  }
  const amount = Number(normalized);
  if (!Number.isFinite(amount) || amount <= 0) {
    return { ok: false, problem: "invalid" };
  }
  if (amount > (decimals === 0 ? MAX_AMOUNT_WHOLE_UNIT : MAX_AMOUNT)) {
    return { ok: false, problem: "tooLarge" };
  }
  return { ok: true, amount };
}

// The scan endpoint's own 422 text (app/api/v1/fib.py), English only (same as the radar
// report's screening rejections, `utils/radarForm.ts`): matched by prefix, not equality, since
// the frontend owns no part of that wording.
const SCAN_REJECTION_KEYS: ReadonlyArray<readonly [string, string]> = [
  ["No bill found", "fib.bill.scan.errors.notABill"],
  ["The amount or currency could not be read", "fib.bill.scan.errors.unreadable"],
];

/** i18n key that tells the worker why reading the bill photo failed. */
export function scanFailureKey(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) {
      const match = SCAN_REJECTION_KEYS.find(([start]) => error.detail.startsWith(start));
      return match ? match[1] : "fib.bill.scan.errors.generic";
    }
    if (error.status === 413) {
      return "fib.bill.scan.errors.tooLarge";
    }
    if (error.status === 415) {
      return "fib.bill.scan.errors.badType";
    }
    if (error.status === 502 || error.status === 503) {
      return "fib.bill.scan.errors.aiBusy";
    }
    if (error.status === 504) {
      return "fib.bill.scan.errors.aiSlow";
    }
  }
  return errorMessageKey(error);
}

/** Trims a text field and turns a blank result into `undefined`, so it is left out of the
 * request body rather than sent as `""` (the backend treats the two the same, but this
 * keeps the JSON honest about what the worker actually typed). */
export function blankToUndefined(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}

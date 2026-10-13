import { HOST_COUNTRIES, JOB_TYPES, type HostCountry } from "@/types/enums";
import { toAsciiDigits } from "@/utils/digits";
import type { CoachSlot, CoachStage } from "@/types/coach";

// The interview's helpers write their answer as text, which the server reads again (v2-coach.md,
// "What the screen offers for each slot", open point 3). So everything here is about producing
// text the server's readers (utils: docs/api/v2-coach.md; backend extraction_cues.py) recognise.

export type MoneyPeriod = "month" | "week" | "year";
export type InterestPeriod = "month" | "year";

/** The money the contract accepts (`Currency` in backend/app/schemas/coach_profile.py). */
export const COACH_CURRENCIES = [
  "SGD",
  "KRW",
  "MYR",
  "JPY",
  "HKD",
  "AUD",
  "PHP",
  "INR",
  "IDR",
  "NPR",
  "BDT",
] as const;
export type CoachCurrency = (typeof COACH_CURRENCIES)[number];

const HOST_CURRENCY: Readonly<Record<HostCountry, CoachCurrency>> = {
  SG: "SGD",
  KR: "KRW",
  MY: "MYR",
  JP: "JPY",
  HK: "HKD",
  AU: "AUD",
};

export const MAX_ANSWER_CHARS = 1000;
const MAX_AMOUNT = 1_000_000_000;
const MAX_RATE = 1000;
const MAX_DEPENDENTS = 20;

export type AnswerInput =
  | { kind: "choice"; set: "country" | "job" | "bank" | "review"; ids: readonly string[] }
  | { kind: "money"; periods: readonly MoneyPeriod[]; canBeNone: boolean }
  | { kind: "count" }
  | { kind: "interest" }
  | { kind: "date" }
  | { kind: "text" };

const FLOW_PERIODS: readonly MoneyPeriod[] = ["month", "week", "year"];

/** Which helper fits the question the coach is asking: the slot, or the review at the end. */
export function answerInputFor(stage: CoachStage, slot: CoachSlot | null): AnswerInput {
  if (stage === "review") {
    return { kind: "choice", set: "review", ids: ["yes", "change"] };
  }
  switch (slot) {
    case "destination_country":
      return { kind: "choice", set: "country", ids: HOST_COUNTRIES };
    case "job_type":
      return { kind: "choice", set: "job", ids: JOB_TYPES };
    case "bank_or_wallet":
      return {
        kind: "choice",
        set: "bank",
        ids: ["bank_account", "mobile_wallet", "both", "none"],
      };
    case "monthly_salary":
    case "remittance_target":
      return { kind: "money", periods: FLOW_PERIODS, canBeNone: false };
    case "recruitment_fee_paid":
    case "debt_outstanding":
    case "savings":
      return { kind: "money", periods: [], canBeNone: true };
    case "dependents":
      return { kind: "count" };
    case "debt_interest":
      return { kind: "interest" };
    case "departure_date":
      return { kind: "date" };
    default:
      return { kind: "text" };
  }
}

/**
 * A number as a worker types it: "4200", "4,200", "4 200.50", "1.700,50". One separator that is
 * followed by exactly three digits is a thousands mark ("4,200"); otherwise the last separator is
 * the decimal point. Returns null for anything that is not one plain number.
 */
export function parseAmount(raw: string): number | null {
  const text = toAsciiDigits(raw.trim()).replace(/[\s']/g, "");
  if (!/^\d+(?:[.,]\d+)*$/.test(text)) {
    return null;
  }
  const marks = text.match(/[.,]/g) ?? [];
  let normal: string;
  if (marks.length === 0) {
    normal = text;
  } else {
    const last = Math.max(text.lastIndexOf("."), text.lastIndexOf(","));
    const head = text.slice(0, last);
    const tail = text.slice(last + 1);
    // "4,200" and "1.700.000" group thousands; "4,20", "4.5", "0.500" and "1.700,500" do not.
    const grouping = new Set(marks).size === 1 && tail.length === 3 && head !== "0";
    normal = grouping ? text.replace(/[.,]/g, "") : `${head.replace(/[.,]/g, "")}.${tail}`;
  }
  const value = Number(normal);
  return Number.isFinite(value) ? value : null;
}

/** An amount the contract takes: a salary is above zero, a debt or savings may be zero. */
export function isAmount(value: number | null, { allowZero }: { allowZero: boolean }) {
  return value !== null && value <= MAX_AMOUNT && (allowZero ? value >= 0 : value > 0);
}

export const isRate = (value: number | null) => value !== null && value >= 0 && value <= MAX_RATE;

export const isDependents = (value: number | null) =>
  value !== null && Number.isInteger(value) && value >= 0 && value <= MAX_DEPENDENTS;

/** Plain digits, no grouping mark: "4200", not "4,200", which an Indonesian reads as 4.2. */
export const plainNumber = (value: number): string => String(value);

/** The currency to offer first: the one the worker last used, else the host country's. */
export function defaultCurrency(
  slots: Partial<Record<CoachSlot, unknown>>,
  fallbackHost?: string
): CoachCurrency {
  for (const slot of [
    "monthly_salary",
    "remittance_target",
    "debt_outstanding",
    "savings",
  ] as const) {
    const value = slots[slot];
    if (typeof value === "object" && value !== null && "currency" in value) {
      const code = (value as { currency: unknown }).currency;
      if (COACH_CURRENCIES.includes(code as CoachCurrency)) {
        return code as CoachCurrency;
      }
    }
  }
  const host = slots.destination_country ?? fallbackHost;
  return HOST_CURRENCY[host as HostCountry] ?? "SGD";
}

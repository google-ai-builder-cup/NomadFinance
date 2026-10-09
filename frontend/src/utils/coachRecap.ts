import { COACH_SLOTS, type CoachSlot } from "@/types/coach";
import { groupedAmount } from "@/utils/coachPlan";

/** `t` as the recap needs it: a key and its values in, a sentence out. */
export type Translate = (key: string, options?: Record<string, unknown>) => string;

export interface RecapRow {
  slot: CoachSlot;
  label: string;
  value: string;
}

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** A date as a worker reads it in their language ("1 December 2026"), with digits 0 to 9 in every
 * language (a Nepali or Bengali locale would write other digits) and no time-zone shift. */
export function formatDate(iso: string, language: string): string {
  const match = ISO_DATE.exec(iso);
  if (match === null) {
    return iso;
  }
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  try {
    return new Intl.DateTimeFormat(`${language}-u-nu-latn`, {
      dateStyle: "long",
      timeZone: "UTC",
    }).format(date);
  } catch {
    return iso;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

// The same sentences the answer helpers send (`input.compose.*`), so what the worker reads here is
// what they would have said.
function money(value: Record<string, unknown>, t: Translate): string | null {
  const { amount, currency, period } = value;
  if (typeof amount !== "number" || typeof currency !== "string") {
    return null;
  }
  if (amount === 0) {
    return t("input.none");
  }
  const shown = { amount: groupedAmount(amount), currency };
  return period === "month" || period === "week" || period === "year"
    ? t(`input.compose.${period}`, shown)
    : t("input.compose.once", shown);
}

/** One answer in words, or null when its shape is not one the Coach stores. */
export function recapValue(
  slot: CoachSlot,
  value: unknown,
  t: Translate,
  language: string
): string | null {
  switch (slot) {
    case "destination_country":
      return typeof value === "string" ? t(`input.country.${value}`) : null;
    case "job_type":
      return typeof value === "string" ? t(`onboarding.jobTypes.${value}`) : null;
    case "bank_or_wallet":
      return typeof value === "string" ? t(`input.bank.${value}`) : null;
    case "departure_date":
      return typeof value === "string" ? formatDate(value, language) : null;
    case "dependents":
      return typeof value === "number" ? String(value) : null;
    case "debt_interest": {
      if (!isRecord(value) || typeof value.rate_percent !== "number") {
        return null;
      }
      const period = value.period === "year" ? "year" : "month";
      return t(`input.compose.interest.${period}`, { rate: value.rate_percent });
    }
    default:
      return isRecord(value) ? money(value, t) : null;
  }
}

/** The worker's answers as table rows, in the order of the interview. A slot that was not answered
 * has no row, and a value that cannot be put in words is shown as a dash rather than dropped. */
export function recapRows(
  slots: Partial<Record<CoachSlot, unknown>>,
  t: Translate,
  language: string
): RecapRow[] {
  return COACH_SLOTS.filter((slot) => slots[slot] !== undefined).map((slot) => ({
    slot,
    label: t(`recap.slot.${slot}`),
    value: recapValue(slot, slots[slot], t, language) ?? "—",
  }));
}

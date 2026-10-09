import type { CoachPlanBody, PlanMoney } from "@/types/coach";
import { CORRIDOR_IDS } from "@/types/enums";

/** A figure as the PDF writes it: `4,200 AUD`, `1,473.72 AUD`, digits 0 to 9 in every language
 * (a locale such as Bengali would write other digits), so the screen and the file always agree. */
export function planMoney(money: PlanMoney): string {
  const text = new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    useGrouping: true,
    numberingSystem: "latn",
  } as Intl.NumberFormatOptions).format(money.amount);
  return `${text} ${money.currency}`;
}

/** The link into Remittance X-Ray with the plan's corridor and monthly amount filled in, or null
 * when the route is not one of the six corridors or nothing is to be sent. */
export function remittanceLink(plan: CoachPlanBody): string | null {
  const { corridor_id: corridor, monthly_amount: amount } = plan.remittance;
  if (corridor === null || !(CORRIDOR_IDS as readonly string[]).includes(corridor)) {
    return null;
  }
  if (!(amount.amount > 0)) {
    return null;
  }
  const query = new URLSearchParams({ corridor, amount: String(amount.amount) });
  return `/remittance?${query.toString()}`;
}

/** The weeks of the plan in which money is to be sent. */
export function sendWeeks(plan: CoachPlanBody): ReadonlySet<number> {
  return new Set(plan.remittance.schedule.map((send) => send.week));
}

const SEVERITY_ORDER = { urgent: 0, warning: 1, info: 2 } as const;

/** Warnings, the most serious first; equal ones keep the plan's own order. */
export function warningsBySeverity(plan: CoachPlanBody) {
  return plan.warnings
    .map((warning, index) => ({ warning, index }))
    .sort(
      (a, b) =>
        SEVERITY_ORDER[a.warning.severity] - SEVERITY_ORDER[b.warning.severity] || a.index - b.index
    )
    .map(({ warning }) => warning);
}

/** Cost and goal ids the screen has words for; any other id gets a neutral label. */
export const KNOWN_COST_IDS = [
  "accommodation",
  "food",
  "transport",
  "phone_data",
  "deductions",
] as const;
export const KNOWN_GOAL_IDS = ["remittance", "debt_payment", "emergency_fund"] as const;

export function isKnownId(list: readonly string[], id: string): boolean {
  return list.includes(id);
}

/** `phone_data` as words, for an id the screen does not know: "Phone data". */
export function humanId(id: string): string {
  const words = id.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

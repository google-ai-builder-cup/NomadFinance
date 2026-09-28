import type { ClauseRisk } from "@/types/contract";

/** Pill background for the overall risk badge (ReportCard's header). */
export const RISK_BADGE_CLASSES: Record<ClauseRisk, string> = {
  safe: "border-green-600/30 bg-green-600/10 text-green-700 dark:text-green-400",
  caution: "border-yellow-600/30 bg-yellow-600/10 text-yellow-700 dark:text-yellow-400",
  danger: "border-red-600/30 bg-red-600/10 text-red-700 dark:text-red-400",
};

/** Solid dot for a single clause's 🟢🟡🔴 flag (ClauseRow). */
export const RISK_DOT_CLASSES: Record<ClauseRisk, string> = {
  safe: "bg-green-600 dark:bg-green-400",
  caution: "bg-yellow-600 dark:bg-yellow-400",
  danger: "bg-red-600 dark:bg-red-400",
};

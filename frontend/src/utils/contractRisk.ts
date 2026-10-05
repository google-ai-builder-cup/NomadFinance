import type { ClauseRisk } from "@/types/contract";

/** Pill background for the overall risk badge (ReportCard's header): the shared risk scale. */
export const RISK_BADGE_CLASSES: Record<ClauseRisk, string> = {
  safe: "border-safe/25 bg-safe-tint text-safe-tint-ink",
  caution: "border-caution/30 bg-caution-tint text-caution-tint-ink",
  danger: "border-danger/25 bg-danger-tint text-danger-tint-ink",
};

/** Solid dot for a single clause's 🟢🟡🔴 flag (ClauseRow). */
export const RISK_DOT_CLASSES: Record<ClauseRisk, string> = {
  safe: "bg-safe",
  caution: "bg-caution",
  danger: "bg-danger",
};

/** Left severity bar on a clause card. */
export const RISK_BAR_CLASSES: Record<ClauseRisk, string> = {
  safe: "bg-safe",
  caution: "bg-caution",
  danger: "bg-danger",
};

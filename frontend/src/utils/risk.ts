import type { RiskLevel } from "@/components/common/RiskBadge";

/** A three-step severity, as the scam verdict reports it (`risk_level`). */
export const SEVERITIES = ["low", "medium", "high"] as const;
export type Severity = (typeof SEVERITIES)[number];

// The app's one risk scale has four colours (`RiskBadge`); a severity only ever uses three of them.
const LEVELS: Readonly<Record<Severity, RiskLevel>> = {
  low: "safe",
  medium: "caution",
  high: "danger",
};

/** The badge level that goes with a severity, so a meter and a badge never disagree. */
export function riskLevelForSeverity(severity: Severity): RiskLevel {
  return LEVELS[severity];
}

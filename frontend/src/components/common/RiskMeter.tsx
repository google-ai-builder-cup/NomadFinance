import { cn } from "@/lib/utils";
import RiskBadge from "@/components/common/RiskBadge";
import { riskLevelForSeverity, SEVERITIES, type Severity } from "@/utils/risk";

export interface RiskMeterProps {
  severity: Severity;
  /** Visible level text, already translated, e.g. "High risk". Colour is never the only signal. */
  label: string;
  /** What is being measured, as the accessible name, e.g. "Scam risk". */
  meterLabel: string;
  className?: string;
}

// Whole class names, so Tailwind can see them (a class built from the level would be purged).
const FILL: Readonly<Record<Severity, string>> = {
  low: "bg-safe",
  medium: "bg-caution",
  high: "bg-danger",
};

/** A three-segment meter for a low, medium or high verdict, always next to a badge with an icon
 * and the level in words. The segments are decorative; the `meter` role carries the value. */
export default function RiskMeter({ severity, label, meterLabel, className }: RiskMeterProps) {
  const position = SEVERITIES.indexOf(severity) + 1;
  return (
    <div className={cn("flex flex-wrap items-center gap-3", className)}>
      <div
        role="meter"
        aria-label={meterLabel}
        aria-valuemin={1}
        aria-valuemax={SEVERITIES.length}
        aria-valuenow={position}
        aria-valuetext={label}
        data-severity={severity}
        className="flex h-2.5 w-28 shrink-0 gap-1"
      >
        {SEVERITIES.map((step, index) => (
          <span
            key={step}
            aria-hidden="true"
            className={cn(
              "h-full flex-1 rounded-full",
              index < position ? FILL[severity] : "bg-muted"
            )}
          />
        ))}
      </div>
      <RiskBadge level={riskLevelForSeverity(severity)}>{label}</RiskBadge>
    </div>
  );
}

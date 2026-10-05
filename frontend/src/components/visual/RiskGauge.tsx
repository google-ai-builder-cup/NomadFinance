import { useId } from "react";

import { cn } from "@/lib/utils";

export interface RiskGaugeProps {
  /** Contract health, 0 (worst) to 100 (best). */
  score: number;
  /** Accessible description, e.g. "Contract health 58 out of 100: Caution". */
  label: string;
  safeLabel: string;
  dangerLabel: string;
  className?: string;
}

const ARC = Math.PI * 100;

/** A semicircle running from Danger to Safe with a needle at the health score. The arc is the
 * full risk scale, so the needle position reads even without colour. */
export default function RiskGauge({
  score,
  label,
  safeLabel,
  dangerLabel,
  className,
}: RiskGaugeProps) {
  const id = useId().replace(/:/g, "");
  const clamped = Math.max(0, Math.min(100, score));
  // 0 points at the Danger end (left), 100 at the Safe end (right).
  const angle = -90 + (clamped / 100) * 180;
  return (
    <svg
      viewBox="0 0 260 150"
      role="img"
      aria-label={label}
      className={cn("h-auto w-full max-w-[300px]", className)}
    >
      <defs>
        <linearGradient id={id} x1="0" x2="1">
          <stop offset="0" stopColor="hsl(var(--danger))" />
          <stop offset=".5" stopColor="hsl(var(--caution))" />
          <stop offset="1" stopColor="hsl(var(--safe))" />
        </linearGradient>
      </defs>
      <path
        d="M30 130a100 100 0 0 1 200 0"
        fill="none"
        stroke="hsl(var(--muted))"
        strokeWidth="20"
        strokeLinecap="round"
      />
      <path
        d="M30 130a100 100 0 0 1 200 0"
        fill="none"
        stroke={`url(#${id})`}
        strokeWidth="20"
        strokeLinecap="round"
        strokeDasharray={ARC}
      />
      <g
        style={{
          transformOrigin: "130px 130px",
          transform: `rotate(${angle}deg)`,
          transition: "transform var(--dur-slow) var(--ease-out)",
        }}
      >
        <path
          d="M130 130L130 50"
          stroke="hsl(var(--foreground))"
          strokeWidth="4.5"
          strokeLinecap="round"
        />
        <circle cx="130" cy="130" r="10" fill="hsl(var(--foreground))" />
        <circle cx="130" cy="130" r="4" fill="hsl(var(--card))" />
      </g>
      <text
        x="30"
        y="148"
        textAnchor="middle"
        fontSize="11"
        fontWeight="700"
        fill="hsl(var(--danger-ink))"
      >
        {dangerLabel}
      </text>
      <text
        x="230"
        y="148"
        textAnchor="middle"
        fontSize="11"
        fontWeight="700"
        fill="hsl(var(--safe-ink))"
      >
        {safeLabel}
      </text>
    </svg>
  );
}

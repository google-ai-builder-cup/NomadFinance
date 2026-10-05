import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface ScoreRingProps {
  /** 0 to 100. */
  value: number;
  /** Stroke colour as a CSS value, e.g. `hsl(var(--identity))`. */
  color: string;
  size?: number;
  strokeWidth?: number;
  label: string;
  /** Centre content; defaults to the rounded value. */
  children?: ReactNode;
  className?: string;
}

/** A progress ring. The ring itself is decorative: `label` carries the meaning. */
export default function ScoreRing({
  value,
  color,
  size = 76,
  strokeWidth = 8,
  label,
  children,
  className,
}: ScoreRingProps) {
  const r = 32;
  const circumference = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      role="img"
      aria-label={label}
      className={cn("relative shrink-0", className)}
      style={{ width: size, height: size }}
    >
      <svg viewBox="0 0 80 80" width={size} height={size} aria-hidden="true">
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          stroke="hsl(var(--muted))"
          strokeWidth={strokeWidth}
        />
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${(circumference * clamped) / 100} ${circumference}`}
          transform="rotate(-90 40 40)"
          style={{ transition: "stroke-dasharray var(--dur-slow) var(--ease-out)" }}
        />
      </svg>
      <span className="absolute inset-0 grid place-items-center text-lg font-extrabold tabular-nums tracking-tight">
        {children ?? Math.round(clamped)}
      </span>
    </div>
  );
}

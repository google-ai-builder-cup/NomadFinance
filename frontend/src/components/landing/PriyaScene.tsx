import { useId } from "react";

import PriyaAvatar from "@/components/landing/PriyaAvatar";

const GOLD = "hsl(var(--brand-gold))";
const LINES = [112, 88, 120, 70, 104] as const;

/** Priya's story as one illustration: the Singapore skyline she works under, her contract being
 * checked, and the money she sends home. Decorative, so hidden from assistive technology; the
 * story it illustrates is the paragraph beside it. */
export default function PriyaScene() {
  const id = useId().replace(/:/g, "");
  return (
    <svg
      viewBox="0 0 560 400"
      aria-hidden="true"
      focusable="false"
      className="h-auto w-full rounded-3xl border bg-card shadow-md"
    >
      <defs>
        <linearGradient id={`${id}s`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="hsl(var(--remit-tint))" />
          <stop offset="1" stopColor="hsl(var(--card))" />
        </linearGradient>
        <pattern id={`${id}d`} width="18" height="18" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="1.2" fill="hsl(var(--primary) / .16)" />
        </pattern>
      </defs>
      <rect width="560" height="400" fill={`url(#${id}s)`} />
      <rect width="560" height="400" fill={`url(#${id}d)`} />
      <circle cx="486" cy="62" r="34" fill={GOLD} opacity=".28" />
      <circle cx="486" cy="62" r="22" fill={GOLD} opacity=".55" />

      {/* Singapore skyline: three towers carrying a deck, a dome and a few blocks. */}
      <g fill="hsl(var(--primary))">
        <rect x="20" y="236" width="34" height="104" rx="3" opacity=".16" />
        <rect x="60" y="212" width="28" height="128" rx="3" opacity=".22" />
        <rect x="250" y="250" width="30" height="90" rx="3" opacity=".16" />
        <path d="M282 340v-48a30 30 0 0 1 60 0v48z" opacity=".18" />
        <path
          d="M104 340l9-120h14l5 120zM142 340l6-124h14l4 124zM182 340l10-116h14l4 116z"
          opacity=".34"
        />
        <path d="M96 214h132c10 0 14 6 8 12l-30 24h-90z" opacity=".5" />
      </g>
      <rect x="0" y="338" width="560" height="62" fill="hsl(var(--primary) / .1)" />

      {/* The contract, read and marked clause by clause. */}
      <g transform="translate(34 78) rotate(-5)">
        <rect
          width="168"
          height="212"
          rx="14"
          fill="hsl(var(--card))"
          stroke="hsl(var(--border))"
        />
        <rect x="14" y="14" width="30" height="30" rx="9" fill="hsl(var(--contract))" />
        <path
          d="M29 20l8 3v6c0 5-4 8-8 10-4-2-8-5-8-10v-6z"
          fill="none"
          stroke="white"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <rect x="54" y="22" width="70" height="7" rx="3.5" fill="hsl(var(--foreground) / .7)" />
        <rect
          x="54"
          y="34"
          width="44"
          height="5"
          rx="2.5"
          fill="hsl(var(--muted-foreground) / .4)"
        />
        {LINES.map((w, i) => (
          <g key={w + i}>
            {i === 2 && (
              <rect
                x="10"
                y={63 + i * 25}
                width="148"
                height="20"
                rx="6"
                fill="hsl(var(--caution-tint))"
              />
            )}
            <circle
              cx="22"
              cy={73 + i * 25}
              r="4"
              fill={i === 2 ? "hsl(var(--caution))" : "hsl(var(--safe))"}
            />
            <rect
              x="34"
              y={70 + i * 25}
              width={w}
              height="6"
              rx="3"
              fill="hsl(var(--muted-foreground) / .45)"
            />
          </g>
        ))}
      </g>

      {/* Priya, calm now, on a small platform. */}
      <ellipse cx="290" cy="322" rx="92" ry="16" fill="hsl(var(--primary) / .14)" />
      <g transform="translate(206 150)">
        <PriyaAvatar calm size={168} />
      </g>

      {/* Money home: a dashed route from the skyline to a house, a coin riding it. */}
      <path
        d="M330 168Q410 70 478 132"
        fill="none"
        stroke={GOLD}
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeDasharray="2 8"
        className="animate-dash-flow"
      />
      <g className="animate-float [transform-box:fill-box] [transform-origin:center]">
        <circle cx="402" cy="86" r="17" fill={GOLD} />
        <circle
          cx="402"
          cy="86"
          r="12"
          fill="none"
          stroke="white"
          strokeOpacity=".7"
          strokeWidth="1.5"
        />
        <text
          x="402"
          y="91"
          textAnchor="middle"
          fontSize="14"
          fontWeight="800"
          fill="hsl(var(--deep))"
        >
          ₹
        </text>
      </g>
      <g transform="translate(442 128)">
        <path d="M0 34L38 2l38 32z" fill="hsl(var(--contract))" />
        <rect
          x="8"
          y="34"
          width="60"
          height="44"
          rx="4"
          fill="hsl(var(--card))"
          stroke="hsl(var(--border))"
        />
        <rect x="31" y="50" width="14" height="28" rx="3" fill="hsl(var(--primary))" />
        <rect x="14" y="44" width="11" height="11" rx="2" fill="hsl(var(--remit-tint))" />
        <rect x="51" y="44" width="11" height="11" rx="2" fill="hsl(var(--remit-tint))" />
      </g>

      {/* A phone comparing two providers: the cheaper one is marked. */}
      <g transform="translate(372 214)">
        <rect
          width="136"
          height="150"
          rx="20"
          fill="hsl(var(--card))"
          stroke="hsl(var(--border))"
          strokeWidth="1.5"
        />
        <rect x="46" y="9" width="44" height="5" rx="2.5" fill="hsl(var(--border))" />
        {[
          { w: 84, safe: true },
          { w: 56, safe: false },
        ].map(({ w, safe }, i) => (
          <g key={w} transform={`translate(14 ${34 + i * 50})`}>
            <rect
              width="108"
              height="40"
              rx="10"
              fill={safe ? "hsl(var(--safe-tint))" : "hsl(var(--muted))"}
            />
            <rect
              x="10"
              y="12"
              width={w * 0.7}
              height="6"
              rx="3"
              fill="hsl(var(--foreground) / .6)"
            />
            <rect
              x="10"
              y="24"
              width={w * 0.45}
              height="5"
              rx="2.5"
              fill="hsl(var(--muted-foreground) / .45)"
            />
            {safe && (
              <>
                <circle cx="92" cy="20" r="9" fill="hsl(var(--safe))" />
                <path
                  d="M87.5 20.5l3 3 6-6.5"
                  fill="none"
                  stroke="white"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </>
            )}
          </g>
        ))}
      </g>
    </svg>
  );
}

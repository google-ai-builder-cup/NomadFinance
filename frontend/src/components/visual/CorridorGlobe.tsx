import { lazy, Suspense, useCallback, useMemo, useState } from "react";

import { buildGlobeShape } from "@/components/visual/geo";
import { canRunGlobe } from "@/components/visual/globeSupport";
import { cn } from "@/lib/utils";

// The animated globe is a separate chunk: devices that cannot run it never download it.
const CorridorGlobeCanvas = lazy(() => import("@/components/visual/CorridorGlobeCanvas"));

const CITY_FILL = { sending: "hsl(var(--aqua))", receiving: "hsl(var(--brand-gold))" } as const;

/** Static SVG poster of the six corridors: dotted Asia-Pacific, glowing arcs and a coin on each.
 * Always rendered first, so the largest paint on the landing page never waits for JavaScript. */
export function CorridorGlobePoster({ className }: { className?: string }) {
  const shape = useMemo(() => buildGlobeShape(), []);
  return (
    <svg
      viewBox="0 0 520 520"
      className={cn("block h-auto w-full overflow-visible", className)}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <radialGradient id="globe-sphere" cx=".34" cy=".28" r=".85">
          <stop offset="0" stopColor="hsl(var(--globe-hi))" />
          <stop offset=".5" stopColor="hsl(var(--globe-mid))" />
          <stop offset="1" stopColor="hsl(var(--globe-lo))" />
        </radialGradient>
        <radialGradient id="globe-atmosphere" cx=".5" cy=".5" r=".5">
          <stop offset=".88" stopColor="hsl(var(--globe-dot))" stopOpacity="0" />
          <stop offset=".95" stopColor="hsl(var(--globe-dot))" stopOpacity=".16" />
          <stop offset="1" stopColor="hsl(var(--globe-dot))" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="globe-arc" x1="0" x2="1">
          <stop offset="0" stopColor="hsl(var(--primary))" />
          <stop offset="1" stopColor="hsl(var(--brand-gold))" />
        </linearGradient>
      </defs>
      <circle cx="260" cy="262" r="249" fill="url(#globe-atmosphere)" />
      <circle cx="260" cy="262" r="215" fill="url(#globe-sphere)" />
      <path
        d={shape.graticule}
        fill="none"
        stroke="hsl(var(--globe-dot))"
        strokeOpacity=".14"
        strokeWidth=".9"
      />
      <path
        d={shape.dots}
        fill="none"
        stroke="hsl(var(--globe-dot))"
        strokeOpacity=".55"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle
        cx="260"
        cy="262"
        r="215"
        fill="none"
        stroke="hsl(var(--globe-dot))"
        strokeOpacity=".25"
        strokeWidth="1.2"
      />
      {shape.arcs.map((arc, i) => (
        <g key={arc.code}>
          <path
            d={arc.d}
            fill="none"
            stroke="url(#globe-arc)"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <circle
            r="3.4"
            className="animate-travel"
            fill="hsl(var(--brand-gold))"
            style={{
              offsetPath: `path('${arc.d}')`,
              animationDuration: `${3.4 + (i % 3) * 0.7}s`,
              animationDelay: `${-i * 0.9}s`,
            }}
          />
          <circle
            r="2.4"
            className="animate-travel"
            fill="hsl(var(--primary))"
            style={{
              offsetPath: `path('${arc.d}')`,
              animationDuration: `${3.4 + (i % 3) * 0.7}s`,
              animationDelay: `${-i * 0.9 - 1.7}s`,
            }}
          />
        </g>
      ))}
      {shape.cities.map((city) => {
        const fill = city.receiving ? CITY_FILL.receiving : CITY_FILL.sending;
        return (
          <g key={city.code}>
            <circle
              cx={city.x}
              cy={city.y}
              r="9"
              fill={fill}
              opacity=".35"
              className="origin-center animate-ping [transform-box:fill-box]"
            />
            <circle
              cx={city.x}
              cy={city.y}
              r="4"
              fill={fill}
              stroke="hsl(var(--card))"
              strokeWidth="1.5"
            />
            <text
              x={city.x + (city.receiving ? 10 : -22)}
              y={city.y + 15}
              fontSize="11"
              fontWeight="800"
              fill="hsl(var(--globe-label))"
              stroke="hsl(var(--card))"
              strokeWidth="3"
              paintOrder="stroke"
              letterSpacing=".04em"
            >
              {city.code}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/** The hero centrepiece. Shows the poster at once, then fades the animated globe in on top when
 * the device can run it. */
export default function CorridorGlobe({ className }: { className?: string }) {
  const [animated] = useState(canRunGlobe);
  const [ready, setReady] = useState(false);
  const handleReady = useCallback(() => setReady(true), []);

  return (
    <div className={cn("relative aspect-square w-full", className)}>
      <div className={cn("transition-opacity duration-slow", ready ? "opacity-0" : "opacity-100")}>
        <CorridorGlobePoster />
      </div>
      {animated && (
        <Suspense fallback={null}>
          <CorridorGlobeCanvas onReady={handleReady} />
        </Suspense>
      )}
    </div>
  );
}

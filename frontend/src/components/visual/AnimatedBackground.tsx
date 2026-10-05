import { useMemo } from "react";

import { buildFlatMapDots, CITIES, flatPoint } from "@/components/visual/geo";
import { cn } from "@/lib/utils";

export type BackgroundVariant = "mesh" | "dotted-map" | "grid";

const MAP = { lon0: 58, lon1: 162, lat0: 52, lat1: -42 } as const;
const MAP_W = 1000;
const MAP_H = 700;

function Mesh() {
  return (
    <>
      <div className="absolute -left-32 -top-32 h-[30rem] w-[30rem] animate-drift rounded-full bg-[var(--blob-a)] blur-[70px] will-change-transform" />
      <div className="absolute -right-24 top-10 h-[26rem] w-[26rem] animate-drift-reverse rounded-full bg-[var(--blob-b)] blur-[70px] will-change-transform" />
    </>
  );
}

function DottedMap() {
  const dots = useMemo(() => buildFlatMapDots(MAP_W, MAP_H, MAP, 1.4), []);
  const cities = useMemo(
    () => Object.values(CITIES).map(([lon, lat]) => flatPoint(lon, lat, MAP_W, MAP_H, MAP)),
    []
  );
  return (
    <svg
      viewBox={`0 0 ${MAP_W} ${MAP_H}`}
      preserveAspectRatio="xMidYMid slice"
      className="absolute inset-0 h-full w-full"
      focusable="false"
    >
      <path
        d={dots}
        fill="none"
        stroke="hsl(var(--primary))"
        strokeOpacity=".22"
        strokeWidth="2.6"
        strokeLinecap="round"
      />
      {cities.map((c) => (
        <circle
          key={`${c.x}-${c.y}`}
          cx={c.x}
          cy={c.y}
          r="5"
          fill="hsl(var(--brand-gold))"
          className="origin-center animate-ping [transform-box:fill-box]"
        />
      ))}
    </svg>
  );
}

function Grid() {
  return (
    <div className="absolute inset-x-[-10%] bottom-0 h-[55%] origin-bottom opacity-60 [background-image:linear-gradient(hsl(var(--primary)/.14)_1px,transparent_1px),linear-gradient(90deg,hsl(var(--primary)/.14)_1px,transparent_1px)] [background-size:56px_56px] [mask-image:linear-gradient(0deg,#000,transparent_85%)] [transform:perspective(520px)_rotateX(62deg)]" />
  );
}

/** Quiet ambient backgrounds. Opacity is capped so text on top keeps its contrast; the drift is
 * transform-only and holds still under prefers-reduced-motion. Decorative, so hidden from
 * assistive technology and never catches a click. */
export default function AnimatedBackground({
  variant = "mesh",
  className,
}: {
  variant?: BackgroundVariant;
  className?: string;
}) {
  return (
    <div
      aria-hidden="true"
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
    >
      {variant === "mesh" && <Mesh />}
      {variant === "dotted-map" && <DottedMap />}
      {variant === "grid" && <Grid />}
    </div>
  );
}

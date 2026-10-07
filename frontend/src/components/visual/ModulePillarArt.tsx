import { useId } from "react";

import { makeIso } from "@/components/visual/iso";
import { Box, IllustrationFrame } from "@/components/visual/IsoParts";
import { Glow } from "@/components/visual/PillarArtParts";
import { GOLD, palette } from "@/components/visual/pillarArtTokens";

// The scenes of the two Future Scope pillars, in the same frame, floor and idle motion as the
// first four (PillarIllustration.tsx), but flat shapes on the floor rather than isometric
// boxes: a message with a warning for the Scam Check, a conversation that climbs for the Coach.

const FLOAT = "animate-float [transform-box:fill-box] [transform-origin:center]";

/** A message bubble with a warning on it, over a shield. */
export function ScamArt({ label }: { label: string }) {
  const id = useId().replace(/:/g, "");
  const p = palette("scam");
  const iso = makeIso(14, 112, 58);
  return (
    <IllustrationFrame label={label}>
      <Glow id={`${id}g`} color={p.glow} cy={168} rx={104} ry={24} />
      <Box iso={iso} x={0} y={0} z={0} w={8} d={8} h={0.5} fills={p.floor} />
      <g className={FLOAT} style={{ animationDuration: "5.5s" }}>
        <path
          d="M120 36 L170 54 V92 C170 118 148 136 120 148 C92 136 70 118 70 92 V54 Z"
          fill={p.soft}
          stroke={p.deep}
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
        <rect x="86" y="62" width="68" height="44" rx="10" fill="white" />
        <path d="M100 106 L96 120 L112 106 Z" fill="white" />
        <path
          d="M98 76H142M98 86H134M98 96H122"
          stroke={p.base}
          strokeWidth="3.5"
          strokeLinecap="round"
        />
        <circle cx="150" cy="60" r="15" fill={GOLD} stroke="white" strokeWidth="2.5" />
        <path d="M150 52V61" stroke={p.deep} strokeWidth="3.4" strokeLinecap="round" />
        <circle cx="150" cy="67" r="2.2" fill={p.deep} />
      </g>
    </IllustrationFrame>
  );
}

/** Two chat bubbles beside three rising steps with a flag on the top one. */
export function CoachArt({ label }: { label: string }) {
  const id = useId().replace(/:/g, "");
  const p = palette("coach");
  const iso = makeIso(14, 112, 58);
  return (
    <IllustrationFrame label={label}>
      <Glow id={`${id}g`} color={p.glow} cy={168} rx={104} ry={24} />
      <Box iso={iso} x={0} y={0} z={0} w={8} d={8} h={0.5} fills={p.floor} />
      {[0, 1, 2].map((step) => (
        <Box
          key={step}
          iso={iso}
          x={5.4}
          y={1 + step * 1.3}
          z={0.5}
          w={1.3}
          d={1.3}
          h={0.9 + step * 0.9}
          fills={p.faces}
          className="animate-grow [transform-box:fill-box] [transform-origin:50%_100%]"
          style={{ animationDelay: `${step * 0.25}s` }}
        />
      ))}
      <g className={FLOAT} style={{ animationDuration: "6s" }}>
        <rect x="34" y="52" width="76" height="34" rx="10" fill="white" stroke={p.soft} />
        <path d="M50 86 L46 98 L62 86 Z" fill="white" />
        <path d="M46 64H98M46 74H84" stroke={p.base} strokeWidth="3.5" strokeLinecap="round" />
        <rect x="58" y="96" width="62" height="28" rx="9" fill={p.base} />
        <path d="M108 124 L112 134 L98 124 Z" fill={p.base} />
        <path d="M70 108H108" stroke="white" strokeWidth="3.5" strokeLinecap="round" />
        <path d="M168 44V28" stroke={p.deep} strokeWidth="2.2" strokeLinecap="round" />
        <path d="M168 28H182L176 34L182 40H168Z" fill={GOLD} />
      </g>
    </IllustrationFrame>
  );
}

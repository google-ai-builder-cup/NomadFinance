import { useId } from "react";

import { makeIso, type FaceFills } from "@/components/visual/iso";
import { Box, Disc, IllustrationFrame } from "@/components/visual/IsoParts";
import { useI18n } from "@/hooks/useI18n";
import { PILLAR_STYLES, pillarVar, type PillarKey } from "@/utils/pillars";

interface Palette {
  base: string;
  soft: string;
  deep: string;
  faces: FaceFills;
  floor: FaceFills;
  paper: FaceFills;
  ink: string;
  glow: string;
}

function palette(pillar: PillarKey): Palette {
  const s = PILLAR_STYLES[pillar];
  const base = pillarVar(s.base);
  const soft = pillarVar(s.soft);
  const deep = pillarVar(s.deep);
  return {
    base,
    soft,
    deep,
    faces: { top: soft, left: base, right: deep },
    floor: {
      top: "hsl(var(--muted))",
      left: "hsl(var(--border))",
      right: "hsl(var(--subtle-foreground) / .45)",
    },
    paper: { top: "hsl(var(--card))", left: "hsl(var(--card))", right: "hsl(var(--border))" },
    ink: "hsl(var(--subtle-foreground))",
    glow: pillarVar(s.soft, 0.5),
  };
}

const GOLD = "hsl(var(--brand-gold))";

function Glow({
  id,
  color,
  cy,
  rx,
  ry,
}: {
  id: string;
  color: string;
  cy: number;
  rx: number;
  ry: number;
}) {
  return (
    <>
      <defs>
        <radialGradient id={id} cx=".5" cy=".5" r=".5">
          <stop offset="0" stopColor={color} />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="120" cy={cy} rx={rx} ry={ry} fill={`url(#${id})`} />
    </>
  );
}

function RemittanceArt({ label }: { label: string }) {
  const id = useId().replace(/:/g, "");
  const p = palette("remit");
  const iso = makeIso(14, 120, 52);
  const tower = (cx: number, cy: number, n: number) =>
    Array.from({ length: n }, (_, i) => (
      <Disc
        key={i}
        iso={iso}
        cx={cx}
        cy={cy}
        z={0.5 + i * 0.6}
        r={1.25}
        h={0.5}
        side={`url(#${id}c)`}
        top={p.soft}
      />
    ));
  const [lx, ly] = iso.pt(2.1, 5.9, 3.7);
  const [rx, ry] = iso.pt(5.9, 2.1, 5.5);
  const path = `M${lx},${ly - 12} Q120,-14 ${rx},${ry - 14}`;
  return (
    <IllustrationFrame label={label}>
      <defs>
        <linearGradient id={`${id}c`} x1="0" x2="1">
          <stop offset="0" stopColor={p.soft} />
          <stop offset=".55" stopColor={p.base} />
          <stop offset="1" stopColor={p.deep} />
        </linearGradient>
      </defs>
      <Glow id={`${id}g`} color={p.glow} cy={172} rx={104} ry={24} />
      <Box iso={iso} x={0} y={0} z={0} w={8} d={8} h={0.5} fills={p.floor} />
      {tower(2.1, 5.9, 5)}
      {tower(5.9, 2.1, 8)}
      <path d={path} fill="none" stroke={p.soft} strokeWidth="1" opacity=".5" />
      <path
        d={path}
        fill="none"
        stroke={GOLD}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeDasharray="2 7"
        className="animate-dash-flow"
      />
      {[0, 1.8].map((delay) => (
        <circle
          key={delay}
          r={delay ? 3.5 : 4.5}
          fill={GOLD}
          className="animate-travel"
          style={{
            offsetPath: `path('${path}')`,
            animationDuration: "3.6s",
            animationDelay: `-${delay}s`,
          }}
        />
      ))}
      <g className="animate-float [transform-box:fill-box] [transform-origin:center]">
        <circle cx={rx} cy={ry - 30} r="12" fill={GOLD} />
        <circle
          cx={rx}
          cy={ry - 30}
          r="8"
          fill="none"
          stroke="white"
          strokeOpacity=".7"
          strokeWidth="1.6"
        />
        <path
          d={`M${rx - 3},${ry - 30} h6 M${rx + 1},${ry - 33.5} l3,3.5 l-3,3.5`}
          fill="none"
          stroke="hsl(var(--deep))"
          strokeOpacity=".75"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>
    </IllustrationFrame>
  );
}

function ContractArt({ label }: { label: string }) {
  const id = useId().replace(/:/g, "");
  const p = palette("contract");
  const iso = makeIso(14, 120, 70);
  const face = [
    iso.pt(1.6, 3.9, 0.9),
    iso.pt(6.6, 3.9, 0.9),
    iso.pt(6.6, 3.9, 8.4),
    iso.pt(1.6, 3.9, 8.4),
  ];
  const rows = [7.4, 6.6, 6.0, 5.4, 4.8, 3.9, 3.3, 2.7];
  return (
    <IllustrationFrame label={label}>
      <defs>
        <linearGradient id={`${id}b`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={p.soft} stopOpacity="0" />
          <stop offset=".7" stopColor={p.soft} stopOpacity=".75" />
          <stop offset="1" stopColor="white" stopOpacity=".95" />
        </linearGradient>
        <linearGradient id={`${id}s`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={p.soft} />
          <stop offset="1" stopColor={p.deep} />
        </linearGradient>
        <clipPath id={`${id}k`}>
          <polygon points={face.map(([x, y]) => `${x},${y}`).join(" ")} />
        </clipPath>
      </defs>
      <Glow id={`${id}g`} color={p.glow} cy={165} rx={100} ry={24} />
      <Box iso={iso} x={0} y={1} z={0} w={8} d={6} h={0.5} fills={p.floor} />
      <Box iso={iso} x={1.6} y={3.5} z={0.5} w={5} d={0.4} h={7.9} fills={p.paper} />
      {rows.map((z, i) => {
        const w = i === 0 ? 2.2 : i === 5 ? 3.6 : 3.8 - (i % 3) * 0.7;
        const [x1, y1] = iso.pt(2.2, 3.9, z);
        const [x2, y2] = iso.pt(2.2 + w, 3.9, z);
        return (
          <line
            key={z}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke={i === 0 ? p.base : p.ink}
            strokeWidth={i === 0 ? 3 : 2.2}
            strokeLinecap="round"
            opacity={i === 0 ? 1 : 0.55}
          />
        );
      })}
      <polygon
        points={[
          iso.pt(2.1, 3.9, 3.85),
          iso.pt(5.7, 3.9, 3.85),
          iso.pt(5.7, 3.9, 4.35),
          iso.pt(2.1, 3.9, 4.35),
        ]
          .map(([x, y]) => `${x},${y}`)
          .join(" ")}
        fill={GOLD}
        opacity=".35"
      />
      <g clipPath={`url(#${id}k)`}>
        <g className="animate-scan">
          <polygon
            points={[
              iso.pt(1.6, 3.9, 0),
              iso.pt(6.6, 3.9, 0),
              iso.pt(6.6, 3.9, 2.4),
              iso.pt(1.6, 3.9, 2.4),
            ]
              .map(([x, y]) => `${x},${y}`)
              .join(" ")}
            fill={`url(#${id}b)`}
          />
        </g>
      </g>
      <g
        className="animate-float [transform-box:fill-box] [transform-origin:center]"
        style={{ animationDuration: "5s" }}
      >
        <path
          d="M180,94 l30,10 v26 c0,20 -14,32 -30,40 c-16,-8 -30,-20 -30,-40 v-26 z"
          fill={`url(#${id}s)`}
          stroke="white"
          strokeOpacity=".55"
          strokeWidth="1.4"
        />
        <path
          d="M165,130 l9,9 l18,-20"
          fill="none"
          stroke="white"
          strokeWidth="5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>
    </IllustrationFrame>
  );
}

function RadarArt({ label }: { label: string }) {
  const id = useId().replace(/:/g, "");
  const p = palette("radar");
  const iso = makeIso(14, 120, 66);
  const [dx, dy] = iso.pt(4, 4, 3.4);
  const wedgeEnd = [4 + 3.4 * Math.cos(-0.95), 4 + 3.4 * Math.sin(-0.95)];
  return (
    <IllustrationFrame label={label}>
      <defs>
        <linearGradient id={`${id}c`} x1="0" x2="1">
          <stop offset="0" stopColor={p.soft} />
          <stop offset="1" stopColor={p.deep} />
        </linearGradient>
        <radialGradient id={`${id}w`} cx="4" cy="4" r="3.4" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor={p.soft} stopOpacity=".85" />
          <stop offset="1" stopColor={p.soft} stopOpacity="0" />
        </radialGradient>
        <radialGradient id={`${id}d`} cx=".35" cy=".3" r=".8">
          <stop offset="0" stopColor="white" />
          <stop offset=".45" stopColor={p.soft} />
          <stop offset="1" stopColor={p.deep} />
        </radialGradient>
      </defs>
      <Glow id={`${id}g`} color={p.glow} cy={150} rx={108} ry={30} />
      <Disc
        iso={iso}
        cx={4}
        cy={4}
        z={0}
        r={4.1}
        h={0.55}
        side={`url(#${id}c)`}
        top="hsl(var(--muted))"
      />
      <g transform={iso.plane(0.55)}>
        <circle cx="4" cy="4" r="3.4" fill={p.deep} opacity=".55" />
        {[3.4, 2.3, 1.2].map((r) => (
          <circle
            key={r}
            cx="4"
            cy="4"
            r={r}
            fill="none"
            stroke={p.soft}
            strokeWidth=".07"
            opacity={r === 3.4 ? 0.9 : 0.7}
          />
        ))}
        <path d="M.6 4H7.4M4 .6V7.4" stroke={p.soft} strokeWidth=".05" opacity=".5" />
        <g className="animate-sweep" style={{ transformOrigin: "4px 4px" }}>
          <path
            d={`M4,4 L7.4,4 A3.4,3.4 0 0 0 ${wedgeEnd[0]},${wedgeEnd[1]} Z`}
            fill={`url(#${id}w)`}
          />
          <line x1="4" y1="4" x2="7.4" y2="4" stroke="white" strokeWidth=".09" />
        </g>
        {[
          [6.1, 2.9, 0, GOLD],
          [2.3, 3.2, -1, GOLD],
          [3.2, 5.6, -2, "white"],
          [5.4, 5.3, -3, GOLD],
        ].map(([x, y, delay, fill]) => (
          <circle
            key={`${x}-${y}`}
            cx={x as number}
            cy={y as number}
            r=".24"
            fill={fill as string}
            className="animate-blip"
            style={{ animationDelay: `${delay}s` }}
          />
        ))}
      </g>
      <Box iso={iso} x={3.7} y={3.7} z={0.55} w={0.6} d={0.6} h={2} fills={p.faces} />
      <g
        className="animate-float [transform-box:fill-box] [transform-origin:center]"
        style={{ animationDuration: "6s" }}
      >
        <g transform={`translate(${dx},${dy}) rotate(-28)`}>
          <ellipse rx="21" ry="9" fill={`url(#${id}d)`} />
          <ellipse rx="21" ry="9" fill="none" stroke="white" strokeOpacity=".6" />
          <line
            x1="0"
            y1="0"
            x2="19"
            y2="-17"
            stroke={p.deep}
            strokeWidth="2.2"
            strokeLinecap="round"
          />
          <circle cx="19" cy="-17" r="3" fill={GOLD} />
        </g>
      </g>
    </IllustrationFrame>
  );
}

function IdentityArt({ label }: { label: string }) {
  const id = useId().replace(/:/g, "");
  const p = palette("identity");
  const iso = makeIso(14, 112, 58);
  return (
    <IllustrationFrame label={label}>
      <defs>
        <linearGradient id={`${id}c`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={p.soft} />
          <stop offset="1" stopColor={p.base} />
        </linearGradient>
      </defs>
      <Glow id={`${id}g`} color={p.glow} cy={168} rx={104} ry={24} />
      <Box iso={iso} x={0} y={0} z={0} w={8} d={8} h={0.5} fills={p.floor} />
      {[1.6, 2.7, 3.9].map((h, i) => (
        <Box
          key={h}
          iso={iso}
          x={6.1}
          y={0.9 + i * 1.4}
          z={0.5}
          w={1}
          d={1}
          h={h}
          fills={p.faces}
          className="animate-grow [transform-box:fill-box] [transform-origin:50%_100%]"
          style={{ animationDelay: `${i * 0.25}s` }}
        />
      ))}
      <Box
        iso={iso}
        x={0.6}
        y={2.4}
        z={0.5}
        w={5}
        d={3.4}
        h={0.28}
        fills={{ top: p.base, left: p.deep, right: p.deep }}
      />
      <Box iso={iso} x={0.8} y={2.6} z={1} w={5} d={3.4} h={0.28} fills={p.faces} />
      <g
        className="animate-float [transform-box:fill-box] [transform-origin:center]"
        style={{ animationDuration: "5.5s" }}
      >
        <Box iso={iso} x={1} y={2.8} z={1.55} w={5} d={3.4} h={0.3} fills={p.faces} />
        <g transform={iso.plane(1.85)}>
          <g fill="none" stroke="white" strokeWidth=".11" strokeLinecap="round" opacity=".95">
            <circle cx="2.7" cy="4.5" r=".28" />
            <circle cx="2.7" cy="4.5" r=".55" strokeDasharray="1.4 .5" />
            <circle cx="2.7" cy="4.5" r=".82" strokeDasharray="2 .6 .8 .4" />
            <circle cx="2.7" cy="4.5" r="1.09" strokeDasharray="3 .7 1 .5" />
          </g>
          <rect x="4.1" y="3.5" width=".95" height=".7" rx=".12" fill={GOLD} />
          <path
            d="M4.1,4.7H5.3M4.1,5.05H5.0M4.1,5.4H5.2"
            stroke="white"
            strokeWidth=".1"
            strokeLinecap="round"
            opacity=".75"
          />
        </g>
      </g>
    </IllustrationFrame>
  );
}

const ART: Record<PillarKey, (props: { label: string }) => JSX.Element> = {
  remit: RemittanceArt,
  contract: ContractArt,
  radar: RadarArt,
  identity: IdentityArt,
};

/** The isometric scene for one pillar, tinted with that pillar's accent. Idle motion is CSS
 * only and stops under prefers-reduced-motion. */
export default function PillarIllustration({ pillar }: { pillar: PillarKey }) {
  const { t } = useI18n();
  const Art = ART[pillar];
  return <Art label={t(`visual.illustration.${pillar}`)} />;
}

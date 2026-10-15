import { type SVGProps, useLayoutEffect, useRef, useState } from "react";

import SectionHeading from "@/components/landing/SectionHeading";
import AnimatedBackground from "@/components/visual/AnimatedBackground";
import { useI18n } from "@/hooks/useI18n";

const NODE = "fill-card stroke-[1.5]";
const FLOW =
  "fill-none stroke-[2.2] animate-dash-flow [stroke-dasharray:6_8] [stroke-linecap:round]";

// The diagram is drawn on this grid: four columns and four rows of 196 x 84 cards, with 120 between
// columns, so a label on a short connector fits in the gap. It is planar on purpose (no connector
// crosses another), which is why the Coach sits beside Contract Shield and above Remittance and
// Scam Check beside the Radar: every pair that exchanges data is next to each other.
const NODE_W = 196;
const NODE_H = 84;
const COLUMNS = [14, 330, 646, 962] as const;
const NODES = {
  coach: { x: COLUMNS[0], y: 72 },
  contract: { x: COLUMNS[1], y: 72 },
  radar: { x: COLUMNS[1], y: 256, h: 94 },
  scam: { x: COLUMNS[2], y: 261 },
  identity: { x: COLUMNS[3], y: 261 },
  remit: { x: COLUMNS[0], y: 470 },
  banks: { x: COLUMNS[3], y: 440 },
} as const;

/** One connector: where it goes, and whose colour it wears. `gold` is the arrow into the banks. */
interface Connector {
  id: string;
  d: string;
  stroke: string;
  gold?: boolean;
}

// Each connector starts and ends on a card's edge. The data behind each one is the Future Scope cross-pillar table
// (and the four v1.0 links the diagram always had).
const CONNECTORS: readonly Connector[] = [
  // Contract Shield <-> Exploitation Radar: contract flags in, warnings back.
  { id: "contractToRadar", d: "M382 156V256", stroke: "stroke-primary" },
  { id: "radarToContract", d: "M474 256V156", stroke: "stroke-radar" },
  // Exploitation Radar -> Remittance X-Ray: warnings.
  { id: "radarToRemit", d: "M330 312C280 330 250 440 210 492", stroke: "stroke-radar" },
  // Contract Shield -> Financial Coach: the salary and employer, and the legal fee cap.
  { id: "contractToCoach", d: "M330 114H210", stroke: "stroke-contract" },
  // Financial Coach <-> Remittance X-Ray: a link with the amount filled in, the cheapest quote back.
  { id: "coachToRemit", d: "M76 156V470", stroke: "stroke-coach" },
  { id: "remitToCoach", d: "M148 470V156", stroke: "stroke-remit" },
  // Scam Check <-> Exploitation Radar: an anonymous report in, "seen before" back.
  { id: "scamToRadar", d: "M646 286H526", stroke: "stroke-scam" },
  { id: "radarToScam", d: "M526 320H646", stroke: "stroke-radar" },
  // Into Financial Identity: scam-check activity, verified employment, transfers, savings goals.
  { id: "scamToIdentity", d: "M842 303H962", stroke: "stroke-scam" },
  { id: "contractToIdentity", d: "M526 114C760 96 1010 112 1020 261", stroke: "stroke-contract" },
  { id: "remitToIdentity", d: "M210 532C520 650 880 600 962 334", stroke: "stroke-primary" },
  { id: "coachToIdentity", d: "M112 72C112 -48 1130 -48 1130 261", stroke: "stroke-coach" },
  { id: "identityToBanks", d: "M1060 345V440", stroke: "stroke-gold-ink", gold: true },
];

/** A label on a connector: where its middle goes, and which string. `max` is the most room it has
 * (a label between two cards has only the gap), where the others may be as wide as they need. */
interface PillSpec {
  x: number;
  y: number;
  label: string;
  max?: number;
}

// The gap between two columns, less a few units of air, is what a label between them may take.
const GAP_MAX = 112;

const PILLS: readonly PillSpec[] = [
  { x: 382, y: 188, label: "flags" },
  { x: 474, y: 224, label: "warnings" },
  { x: 266, y: 389, label: "warnings" },
  { x: 270, y: 114, label: "salary", max: GAP_MAX },
  { x: 112, y: 313, label: "quote" },
  { x: 586, y: 286, label: "reports", max: GAP_MAX },
  { x: 586, y: 320, label: "seen", max: GAP_MAX },
  { x: 902, y: 303, label: "scamActivity", max: GAP_MAX },
  { x: 790, y: 114, label: "employment" },
  { x: 672, y: 577, label: "transfers" },
  { x: 621, y: 6, label: "goals" },
  { x: 1060, y: 392, label: "profile" },
];

const PILL_PAD = 24;
// A guess at a label's width before the text can be measured (the first paint, and a test).
const estimate = (label: string) => [...label].length * 7.6 + PILL_PAD;

/**
 * Makes `el`'s text at most `max` wide and returns the width it has now. A text that is short enough
 * keeps its own width; a longer one is squeezed to `max` (glyphs and spacing together), so a long
 * word in another language never runs out of its card or its gap. 0 where the browser cannot
 * measure (the tests).
 */
function fitText(el: SVGTextElement, max: number): number {
  el.removeAttribute("textLength");
  el.removeAttribute("lengthAdjust");
  const natural = el.getComputedTextLength?.() ?? 0;
  if (natural > max) {
    el.setAttribute("textLength", String(max));
    el.setAttribute("lengthAdjust", "spacingAndGlyphs");
    return max;
  }
  return natural;
}

/** Runs `fit` now and again once the web font has arrived, which changes every width. */
function useFontAwareLayout(fit: () => void, deps: readonly unknown[]) {
  useLayoutEffect(() => {
    fit();
    void document.fonts?.ready.then(fit);
    // `fit` is rebuilt every render; what it depends on is in `deps`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/**
 * A label that sits on a connector. Its width comes from the text itself: six languages, and a word
 * in Bengali is not as wide as one in Indonesian, so a fixed width would clip one and leave the other
 * loose.
 */
function Pill({ x, y, label, max = Infinity }: PillSpec) {
  const text = useRef<SVGTextElement>(null);
  const [width, setWidth] = useState(() => Math.min(estimate(label), max));

  useFontAwareLayout(() => {
    const used = text.current ? fitText(text.current, max - PILL_PAD) : 0;
    if (used > 0) {
      setWidth(Math.ceil(used) + PILL_PAD);
    }
  }, [label, max]);

  return (
    <g transform={`translate(${x} ${y})`}>
      <rect
        x={-width / 2}
        y="-13"
        width={width}
        height="26"
        rx="13"
        className="fill-card stroke-border"
      />
      <text
        ref={text}
        y="4.5"
        textAnchor="middle"
        className="fill-foreground text-[12.5px] font-bold"
      >
        {label}
      </text>
    </g>
  );
}

/** A card's text, squeezed to fit if it is longer than the card has room for. */
function CardText({
  label,
  max,
  ...props
}: SVGProps<SVGTextElement> & { label: string; max: number }) {
  const text = useRef<SVGTextElement>(null);
  useFontAwareLayout(() => {
    if (text.current) {
      fitText(text.current, max);
    }
  }, [label, max]);
  return (
    <text ref={text} {...props}>
      {label}
    </text>
  );
}

// What is left of a card to the right of its icon tile.
const TEXT_MAX = NODE_W - 66 - 12;

function Node({
  id,
  x,
  y,
  stroke,
  tile,
  name,
  sub,
  h = NODE_H,
}: {
  /** Which card this is; the tests find it by this. */
  id: keyof typeof NODES;
  x: number;
  y: number;
  stroke: string;
  tile: string;
  name: string;
  sub?: string;
  h?: number;
}) {
  return (
    <g data-node={id}>
      <rect x={x} y={y} width={NODE_W} height={h} rx="20" className={`${NODE} ${stroke}`} />
      <rect x={x + 18} y={y + h / 2 - 18} width="36" height="36" rx="11" className={tile} />
      <CardText
        label={name}
        max={TEXT_MAX}
        x={x + 66}
        y={y + h / 2 - 2}
        className="fill-foreground text-base font-extrabold"
      />
      {sub && (
        <CardText
          label={sub}
          max={TEXT_MAX}
          x={x + 66}
          y={y + h / 2 + 18}
          className="fill-muted-foreground text-[13px] font-semibold"
        />
      )}
    </g>
  );
}

/** "Contract Shield" is drawn as "Contract" over "Shield": the first word large, the rest small. */
function splitName(name: string): { name: string; sub: string } {
  const [first, ...rest] = name.split(" ");
  return { name: first, sub: rest.join(" ") };
}

const FLOWS = [
  "contractToRadar",
  "radarToTools",
  "scamAndRadar",
  "remitToIdentity",
  "coachInputs",
  "coachToIdentity",
  "scamToIdentity",
  "identityToBanks",
] as const;

/** How the six pillars share data, drawn as an SVG with animated dashed connectors. The meaning is
 * also written out as a list below it, so the diagram is never the only way to read it. */
export default function Ecosystem() {
  const { t } = useI18n();
  const pillar = (key: "contract" | "remittance" | "radar" | "identity" | "scam" | "coach") =>
    splitName(t(`pillars.${key}.name`));
  return (
    <section
      aria-labelledby="eco-heading"
      className="relative overflow-hidden bg-band-wash py-16 md:py-24"
    >
      <AnimatedBackground variant="grid" />
      <div className="relative mx-auto w-full max-w-7xl px-4 md:px-8">
        <SectionHeading
          id="eco-heading"
          kicker={t("landing.ecosystem.kicker")}
          title={t("landing.ecosystem.heading")}
          lead={t("landing.ecosystem.lead")}
        />
        {/* A phone scrolls the diagram sideways, so the region takes focus and has a name:
            without them a keyboard cannot reach the part that is off screen. */}
        <div
          role="region"
          aria-label={t("landing.ecosystem.diagramLabel")}
          tabIndex={0}
          className="card-surface card-edge overflow-x-auto p-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring md:p-7"
        >
          <svg
            viewBox="0 -24 1172 650"
            role="img"
            aria-label={t("landing.ecosystem.diagramLabel")}
            className="block h-auto min-w-[800px] w-full"
          >
            <defs>
              <marker
                id="eco-arrow"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M1 1l8 4-8 4z" className="fill-primary" />
              </marker>
              <marker
                id="eco-arrow-gold"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M1 1l8 4-8 4z" className="fill-gold-ink" />
              </marker>
            </defs>
            {CONNECTORS.map(({ id, d, stroke, gold }) => (
              <path
                key={id}
                data-connector={id}
                d={d}
                className={`${FLOW} ${stroke}`}
                markerEnd={gold ? "url(#eco-arrow-gold)" : "url(#eco-arrow)"}
              />
            ))}
            {PILLS.map((pill) => (
              <Pill
                key={`${pill.label}-${pill.x}-${pill.y}`}
                {...pill}
                label={t(`landing.ecosystem.${pill.label}`)}
              />
            ))}
            <Node
              id="coach"
              {...NODES.coach}
              stroke="stroke-coach"
              tile="fill-coach"
              {...pillar("coach")}
            />
            <Node
              id="contract"
              {...NODES.contract}
              stroke="stroke-contract"
              tile="fill-contract"
              {...pillar("contract")}
            />
            <Node
              id="radar"
              {...NODES.radar}
              stroke="stroke-radar"
              tile="fill-radar"
              {...pillar("radar")}
            />
            <Node
              id="scam"
              {...NODES.scam}
              stroke="stroke-scam"
              tile="fill-scam"
              {...pillar("scam")}
            />
            <Node
              id="identity"
              {...NODES.identity}
              stroke="stroke-identity"
              tile="fill-identity"
              {...pillar("identity")}
            />
            <Node
              id="remit"
              {...NODES.remit}
              stroke="stroke-remit"
              tile="fill-remit"
              {...pillar("remittance")}
            />
            <Node
              id="banks"
              {...NODES.banks}
              stroke="stroke-gold-ink [stroke-dasharray:5_5]"
              tile="fill-gold"
              name={t("landing.ecosystem.banks")}
              sub={t("landing.ecosystem.home")}
            />
          </svg>
        </div>
        <ul className="mt-6 grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
          {FLOWS.map((flow) => (
            <li key={flow} className="flex gap-2">
              <span
                className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
                aria-hidden="true"
              />
              {t(`landing.ecosystem.flow.${flow}`)}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

import SectionHeading from "@/components/landing/SectionHeading";
import AnimatedBackground from "@/components/visual/AnimatedBackground";
import { useI18n } from "@/hooks/useI18n";

const NODE = "fill-card stroke-[1.5]";
const FLOW =
  "fill-none stroke-[2.2] animate-dash-flow [stroke-dasharray:6_8] [stroke-linecap:round]";

function Pill({ x, y, w, label }: { x: number; y: number; w: number; label: string }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect x={-w / 2} y="-13" width={w} height="26" rx="13" className="fill-card stroke-border" />
      <text y="4.5" textAnchor="middle" className="fill-foreground text-[12.5px] font-bold">
        {label}
      </text>
    </g>
  );
}

function Node({
  x,
  y,
  stroke,
  tile,
  name,
  sub,
  w = 200,
  h = 84,
}: {
  x: number;
  y: number;
  stroke: string;
  tile: string;
  name: string;
  sub?: string;
  w?: number;
  h?: number;
}) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx="20" className={`${NODE} ${stroke}`} />
      <rect x={x + 18} y={y + h / 2 - 18} width="36" height="36" rx="11" className={tile} />
      <text x={x + 66} y={y + h / 2 - 2} className="fill-foreground text-base font-extrabold">
        {name}
      </text>
      {sub && (
        <text
          x={x + 66}
          y={y + h / 2 + 18}
          className="fill-muted-foreground text-[13px] font-semibold"
        >
          {sub}
        </text>
      )}
    </g>
  );
}

/** How the pillars share data, drawn as an SVG with animated dashed connectors. The meaning is
 * also written out as a list below it, so the diagram is never the only way to read it. */
export default function Ecosystem() {
  const { t } = useI18n();
  const flows = ["contractToRadar", "radarToTools", "remitToIdentity", "identityToBanks"] as const;
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
        <div className="card-surface card-edge overflow-x-auto p-3 md:p-7">
          <svg
            viewBox="0 0 1000 480"
            role="img"
            aria-label={t("landing.ecosystem.diagramLabel")}
            className="block h-auto min-w-[640px] w-full"
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
            <path
              d="M240 84C330 84 330 212 400 212"
              className={`${FLOW} stroke-primary`}
              markerEnd="url(#eco-arrow)"
            />
            <path
              d="M400 232C340 232 330 122 240 112"
              className={`${FLOW} stroke-radar [animation-direction:reverse]`}
              markerEnd="url(#eco-arrow)"
            />
            <path
              d="M400 262C340 262 330 360 240 366"
              className={`${FLOW} stroke-radar`}
              markerEnd="url(#eco-arrow)"
            />
            <path
              d="M240 398C560 470 700 130 760 106"
              className={`${FLOW} stroke-primary`}
              markerEnd="url(#eco-arrow)"
            />
            <path
              d="M240 70C420 20 600 20 760 70"
              className={`${FLOW} stroke-contract`}
              markerEnd="url(#eco-arrow)"
            />
            <path
              d="M860 130V320"
              className={`${FLOW} stroke-gold-ink`}
              markerEnd="url(#eco-arrow-gold)"
            />
            <Pill x={318} y={146} w={96} label={t("landing.ecosystem.flags")} />
            <Pill x={318} y={330} w={84} label={t("landing.ecosystem.warnings")} />
            <Pill x={560} y={432} w={116} label={t("landing.ecosystem.transfers")} />
            <Pill x={500} y={24} w={124} label={t("landing.ecosystem.employment")} />
            <Pill x={860} y={228} w={132} label={t("landing.ecosystem.profile")} />
            <Node
              x={40}
              y={52}
              stroke="stroke-contract"
              tile="fill-contract"
              name={t("pillars.contract.name").split(" ")[0]}
              sub={t("pillars.contract.name").split(" ").slice(1).join(" ")}
            />
            <Node
              x={40}
              y={356}
              stroke="stroke-remit"
              tile="fill-remit"
              name={t("pillars.remittance.name").split(" ")[0]}
              sub={t("pillars.remittance.name").split(" ").slice(1).join(" ")}
            />
            <Node
              x={400}
              y={190}
              h={94}
              stroke="stroke-radar"
              tile="fill-radar"
              name={t("pillars.radar.name").split(" ")[0]}
              sub={t("pillars.radar.name").split(" ").slice(1).join(" ")}
            />
            <Node
              x={760}
              y={52}
              stroke="stroke-identity"
              tile="fill-identity"
              name={t("pillars.identity.name").split(" ")[0]}
              sub={t("pillars.identity.name").split(" ").slice(1).join(" ")}
            />
            <Node
              x={760}
              y={324}
              stroke="stroke-gold-ink [stroke-dasharray:5_5]"
              tile="fill-gold"
              name={t("landing.ecosystem.banks")}
              sub={t("landing.ecosystem.home")}
            />
          </svg>
        </div>
        <ul className="mt-6 grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
          {flows.map((flow) => (
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

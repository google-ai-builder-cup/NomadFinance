import type { FaceFills } from "@/components/visual/iso";
import { makeIso } from "@/components/visual/iso";
import { Box, IllustrationFrame } from "@/components/visual/IsoParts";
import { useI18n } from "@/hooks/useI18n";

export type StatusVariant = "notFound" | "error" | "soon";

const FLOOR: FaceFills = {
  top: "hsl(var(--muted))",
  left: "hsl(var(--border))",
  right: "hsl(var(--subtle-foreground) / .45)",
};

const TONES: Record<StatusVariant, { fills: FaceFills; mark: string }> = {
  notFound: {
    fills: {
      top: "hsl(var(--remit-soft))",
      left: "hsl(var(--remit))",
      right: "hsl(var(--remit-deep))",
    },
    mark: "?",
  },
  error: {
    fills: {
      top: "hsl(var(--caution) / .7)",
      left: "hsl(var(--caution))",
      right: "hsl(var(--caution-ink))",
    },
    mark: "!",
  },
  soon: {
    fills: {
      top: "hsl(var(--contract-soft))",
      left: "hsl(var(--contract))",
      right: "hsl(var(--contract-deep))",
    },
    mark: "…",
  },
};

/** A small isometric scene for the screens that are not a result: a cube with a question mark
 * (not found), a warning (something broke) or an ellipsis (coming soon). Same visual language as
 * the pillar illustrations, so these screens never fall back to plain text. */
export default function StatusIllustration({ variant }: { variant: StatusVariant }) {
  const { t } = useI18n();
  const iso = makeIso(14, 120, 66);
  const { fills, mark } = TONES[variant];
  const [tx, ty] = iso.pt(4, 4, 4.3);
  return (
    <IllustrationFrame label={t(`visual.status.${variant}`)}>
      <ellipse cx="120" cy="158" rx="100" ry="24" fill="hsl(var(--primary) / .1)" />
      <Box iso={iso} x={0} y={0} z={0} w={8} d={8} h={0.5} fills={FLOOR} />
      <g className="animate-float [transform-box:fill-box] [transform-origin:center]">
        <Box iso={iso} x={2.4} y={2.4} z={0.8} w={3.2} d={3.2} h={3.2} fills={fills} />
        <text
          x={tx}
          y={ty + 20}
          textAnchor="middle"
          fontSize="46"
          fontWeight="800"
          fill="white"
          opacity=".95"
        >
          {mark}
        </text>
      </g>
      <circle cx="40" cy="108" r="6" fill="hsl(var(--brand-gold))" className="animate-blip" />
      <circle
        cx="204"
        cy="96"
        r="4.5"
        fill="hsl(var(--brand-gold))"
        className="animate-blip [animation-delay:-2s]"
      />
    </IllustrationFrame>
  );
}

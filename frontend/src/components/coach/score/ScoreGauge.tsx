import { PolarAngleAxis, RadialBar, RadialBarChart } from "recharts";

import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/hooks/useI18n";
import type { CoachScore } from "@/types/coach";
import { bandTone, isKnownBand } from "@/utils/coachScore";

const SIZE = 152;
// The tone families of the design tokens (`--safe`, `--caution`, `--danger`); a band this screen
// does not know is drawn in the plain foreground colour.
const TONE_COLOUR = {
  danger: "hsl(var(--danger))",
  caution: "hsl(var(--caution))",
  safe: "hsl(var(--safe))",
  neutral: "hsl(var(--foreground))",
} as const;

export interface ScoreGaugeProps {
  score: Pick<CoachScore, "total" | "band">;
}

/**
 * The total as a ring, with the number in it and the band's name beside it. The ring is a picture
 * of the number: it is given a text alternative (the whole sentence, "62 out of 100, Getting
 * ready") and the band is always written, so colour is never the only carrier of the meaning.
 */
export default function ScoreGauge({ score }: ScoreGaugeProps) {
  const { t } = useI18n("coach");
  const tone = bandTone(score.band);
  const bandLabel = isKnownBand(score.band) ? t(`score.band.${score.band}`) : t("score.band.other");
  const label = t("score.chartLabel", { total: score.total, band: bandLabel });

  return (
    <div className="flex flex-col items-center gap-3 sm:flex-row sm:gap-6">
      <div className="relative shrink-0" style={{ width: SIZE, height: SIZE }}>
        <div role="img" aria-label={label} className="h-full w-full">
          {/* The drawing is a picture of the number written below: its own parts are hidden, so
              a screen reader reads the sentence above once, not the ring's sectors. */}
          <div aria-hidden="true">
            <RadialBarChart
              width={SIZE}
              height={SIZE}
              data={[{ value: score.total }]}
              innerRadius="80%"
              outerRadius="100%"
              startAngle={90}
              endAngle={-270}
              barSize={14}
            >
              <PolarAngleAxis type="number" domain={[0, 100]} tick={false} axisLine={false} />
              <RadialBar
                dataKey="value"
                background={{ fill: "hsl(var(--muted))" }}
                cornerRadius={8}
                fill={TONE_COLOUR[tone]}
                isAnimationActive={false}
              />
            </RadialBarChart>
          </div>
        </div>
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"
        >
          <span className="text-3xl font-extrabold tabular-nums leading-none">{score.total}</span>
          <span className="mt-1 text-xs font-medium text-muted-foreground">{t("score.outOf")}</span>
        </div>
      </div>
      <div className="space-y-1.5 text-center sm:text-left">
        <Badge tone={tone === "neutral" ? "info" : tone} className="text-sm">
          {bandLabel}
        </Badge>
        <p className="text-sm text-muted-foreground">{t("score.subtitle")}</p>
      </div>
    </div>
  );
}

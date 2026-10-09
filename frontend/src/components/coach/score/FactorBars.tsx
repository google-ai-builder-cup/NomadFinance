import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/hooks/useI18n";
import { SCORE_FACTORS, type CoachScore, type ScoreFactor } from "@/types/coach";
import { factorKey, levelOf, type ScoreLevel } from "@/utils/coachScore";

const LEVEL_TONE: Record<ScoreLevel, "safe" | "caution" | "danger"> = {
  strong: "safe",
  fair: "caution",
  weak: "danger",
};
const BAR_FILL: Record<ScoreLevel, string> = {
  strong: "bg-safe",
  fair: "bg-caution",
  weak: "bg-danger",
};

function FactorRow({ factor }: { factor: ScoreFactor }) {
  const { t } = useI18n("coach");
  const level = levelOf(factor.score);
  const points = Math.max(0, Math.min(100, Math.round(factor.score)));
  const name = t(`score.factor.${factor.id}.name`);

  return (
    <li className="space-y-2 rounded-2xl border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-bold">{name}</h4>
        <Badge tone={LEVEL_TONE[level]}>{t(`score.level.${level}`)}</Badge>
      </div>
      <div className="flex items-center gap-3">
        <div
          role="progressbar"
          aria-label={name}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={points}
          aria-valuetext={t("score.points", { points })}
          className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted"
        >
          <div
            className={`h-full rounded-full ${BAR_FILL[level]}`}
            style={{ width: `${points}%` }}
          />
        </div>
        <span className="w-24 shrink-0 text-right text-xs font-semibold tabular-nums text-muted-foreground">
          {t("score.points", { points })}
        </span>
      </div>
      <dl className="space-y-2 text-sm">
        <div>
          <dt className="font-bold">{t("score.whatMeans")}</dt>
          <dd className="text-muted-foreground">{t(factorKey(factor.id, level, "means"))}</dd>
        </div>
        <div>
          <dt className="font-bold">{t("score.howImprove")}</dt>
          <dd className="text-muted-foreground">{t(factorKey(factor.id, level, "improve"))}</dd>
        </div>
      </dl>
    </li>
  );
}

export interface FactorBarsProps {
  score: Pick<CoachScore, "factors">;
}

/** One card per factor, in the rubric's order: its name, level, points as a bar and as words, and
 * what it means and how to improve it, chosen by factor and level. A factor the screen has no
 * words for is left out rather than shown with none. */
export default function FactorBars({ score }: FactorBarsProps) {
  const { t } = useI18n("coach");
  const known = score.factors.filter((factor) =>
    (SCORE_FACTORS as readonly string[]).includes(factor.id)
  );
  return (
    <section aria-labelledby="coach-score-factors" className="space-y-3">
      <h3 id="coach-score-factors" className="text-base font-extrabold">
        {t("score.factorsHeading")}
      </h3>
      <ul className="space-y-3">
        {known.map((factor) => (
          <FactorRow key={factor.id} factor={factor} />
        ))}
      </ul>
    </section>
  );
}

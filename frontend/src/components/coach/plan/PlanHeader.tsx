import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/hooks/useI18n";
import type { CoachPlanResponse } from "@/types/coach";
import { bandTone, isKnownBand } from "@/utils/coachScore";

/** The top of the plan: its title, the score it was made with, the route and the dates, and the
 * summary in the worker's language. Dates are written as `YYYY-MM-DD`, as in the PDF. */
export default function PlanHeader({ plan }: { plan: CoachPlanResponse }) {
  const { t } = useI18n("coach");
  const tone = bandTone(plan.score.band);
  const band = isKnownBand(plan.score.band)
    ? t(`score.band.${plan.score.band}`)
    : t("score.band.other");
  const facts: [string, string][] = [];
  if (plan.corridor_id) {
    facts.push([t("plan.header.route"), plan.corridor_id.replace("-", " → ")]);
  }
  if (plan.departure_date) {
    facts.push([t("plan.header.departure"), plan.departure_date]);
  }
  facts.push([t("plan.header.ratesAsOf"), plan.rates_as_of.slice(0, 10)]);

  return (
    <header className="space-y-3 rounded-2xl border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight sm:text-2xl">{t("plan.title")}</h1>
        <Badge tone={tone === "neutral" ? "info" : tone}>
          {t("plan.header.score", { total: plan.score.total, band })}
        </Badge>
      </div>
      <p className="text-sm sm:text-base">{plan.plan.summary}</p>
      <dl className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
        {facts.map(([label, value]) => (
          <div key={label} className="flex gap-1.5">
            <dt className="font-semibold">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </header>
  );
}

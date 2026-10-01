import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { METRIC_KEYS, type FinancialProfile, type MetricKey, type MetricResult } from "@/types/fib";

export interface ScoreMeterProps {
  /** `null` before the weekly cron has ever scored this worker (NF-P3-013). */
  profile: FinancialProfile | null;
}

// Fixed, never themed — the dataviz skill's own status palette (good/warning/critical),
// validated distinct from any categorical chart color on this page. Paired with a text label
// everywhere it appears: on the light surface "warning" alone clears only 1.79:1 contrast.
const STATUS_COLOR = { good: "#0ca30c", warning: "#fab219", critical: "#d03b3b" } as const;
type Status = keyof typeof STATUS_COLOR;

function statusFor(score: number): Status {
  if (score >= 70) {
    return "good";
  }
  return score >= 40 ? "warning" : "critical";
}

function savingsRatePct(result: MetricResult, language: string): string | null {
  const rate = result.detail.savings_rate;
  if (typeof rate !== "number") {
    return null;
  }
  return rate.toLocaleString(language, { style: "percent", maximumFractionDigits: 0 });
}

function MetricMeter({ metricKey, result }: { metricKey: MetricKey; result: MetricResult }) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const label = t(`fib.score.metrics.${metricKey}`);

  if (result.score === null) {
    return (
      <div className="space-y-1">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{t("fib.score.noData")}</p>
      </div>
    );
  }

  const status = statusFor(result.score);
  const pct = metricKey === "savings_rate" ? savingsRatePct(result, language) : null;

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium">{label}</p>
        <p
          className="shrink-0 text-sm font-semibold tabular-nums"
          style={{ color: STATUS_COLOR[status] }}
        >
          {pct ?? result.score} · {t(`fib.score.status.${status}`)}
        </p>
      </div>
      <div
        role="img"
        aria-label={t("fib.score.meterLabel", { label, score: result.score })}
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className="h-full rounded-full transition-[width]"
          style={{ width: `${result.score}%`, backgroundColor: STATUS_COLOR[status] }}
        />
      </div>
    </div>
  );
}

/** Overall score, the four metric meters, and the narrative, from `financial_profile/current`
 * (NF-P3-013). Shows its own empty state when the cron has never found this worker enough
 * activity to score — a brand-new worker, not an error. */
export default function ScoreMeter({ profile }: ScoreMeterProps) {
  const { t } = useI18n();

  if (profile === null) {
    return (
      <section className="space-y-3 rounded-lg border bg-card p-6 text-center">
        <p className="text-sm text-muted-foreground">{t("fib.score.noProfile")}</p>
        <Button asChild size="sm">
          <Link to="/identity/log">{t("fib.score.logActivity")}</Link>
        </Button>
      </section>
    );
  }

  const overallStatus = statusFor(profile.overall_score);

  return (
    <section
      aria-labelledby="fib-score-title"
      className="space-y-5 rounded-lg border bg-card p-4 md:p-6"
    >
      <div className="flex items-center gap-4">
        <div
          className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-4"
          style={{ borderColor: STATUS_COLOR[overallStatus] }}
        >
          <span className="text-2xl font-bold tabular-nums">{profile.overall_score}</span>
        </div>
        <div>
          <h2 id="fib-score-title" className="text-sm text-muted-foreground">
            {t("fib.score.overall")}
          </h2>
          <p className="text-base font-semibold" style={{ color: STATUS_COLOR[overallStatus] }}>
            {t(`fib.score.status.${overallStatus}`)}
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {METRIC_KEYS.map((key) => (
          <MetricMeter key={key} metricKey={key} result={profile.metrics[key]} />
        ))}
      </div>

      {profile.narrative.text && (
        <p className="border-t pt-4 text-sm leading-relaxed text-muted-foreground">
          {profile.narrative.text}
        </p>
      )}
    </section>
  );
}

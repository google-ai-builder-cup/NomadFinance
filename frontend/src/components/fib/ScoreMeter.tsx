import { useId } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import PillarIllustration from "@/components/visual/PillarIllustration";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { METRIC_KEYS, type FinancialProfile, type MetricKey, type MetricResult } from "@/types/fib";
import { savingsRatePct, STATUS_COLOR, statusFor } from "@/utils/fibScore";

export interface ScoreMeterProps {
  /** `null` before the weekly cron has ever scored this worker (NF-P3-013). */
  profile: FinancialProfile | null;
}

// 270 degrees of a circle of radius 98, starting bottom-left and ending bottom-right.
const ARC_LENGTH = 0.75 * 2 * Math.PI * 98;

/** The overall score as a radial gauge. The arc takes the status colour (good, fair or low),
 * which is also written out in words, so colour is never the only signal. */
function RadialGauge({ score, status, label }: { score: number; status: string; label: string }) {
  const id = useId().replace(/:/g, "");
  const color = STATUS_COLOR[statusFor(score)];
  const clamped = Math.max(0, Math.min(100, score));
  return (
    <svg
      viewBox="0 0 260 220"
      role="img"
      aria-label={label}
      className="mx-auto h-auto w-full max-w-[17rem]"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="hsl(var(--identity-deep))" />
          <stop offset="1" stopColor={color} />
        </linearGradient>
      </defs>
      <path
        d="M52 180A98 98 0 1 1 208 180"
        fill="none"
        stroke="hsl(var(--muted))"
        strokeWidth="22"
        strokeLinecap="round"
      />
      <path
        d="M52 180A98 98 0 1 1 208 180"
        fill="none"
        stroke={`url(#${id})`}
        strokeWidth="22"
        strokeLinecap="round"
        strokeDasharray={`${(ARC_LENGTH * clamped) / 100} 700`}
        style={{ transition: "stroke-dasharray var(--dur-slow) var(--ease-out)" }}
      />
      <text
        x="130"
        y="122"
        textAnchor="middle"
        fontSize="58"
        fontWeight="800"
        fill="hsl(var(--foreground))"
        letterSpacing="-.04em"
      >
        {score}
      </text>
      <text
        x="130"
        y="206"
        textAnchor="middle"
        fontSize="13"
        fontWeight="800"
        letterSpacing=".08em"
        fill={color}
      >
        {status.toUpperCase()}
      </text>
    </svg>
  );
}

function MetricMeter({ metricKey, result }: { metricKey: MetricKey; result: MetricResult }) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const label = t(`fib.score.metrics.${metricKey}`);

  if (result.score === null) {
    return (
      <div className="space-y-1 rounded-2xl border border-dashed bg-card p-4">
        <p className="text-sm font-bold">{label}</p>
        <p className="text-xs text-muted-foreground">{t("fib.score.noData")}</p>
      </div>
    );
  }

  const status = statusFor(result.score);
  const pct = metricKey === "savings_rate" ? savingsRatePct(result.detail, language) : null;

  return (
    <div className="card-surface space-y-2.5 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-bold">{label}</p>
        <p
          className="shrink-0 text-sm font-extrabold tabular-nums"
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
          className="h-full rounded-full transition-[width] duration-slow ease-out-soft"
          style={{ width: `${result.score}%`, backgroundColor: STATUS_COLOR[status] }}
        />
      </div>
    </div>
  );
}

/** Overall score, the four metric cards, and the narrative, from `financial_profile/current`
 * (NF-P3-013). Shows its own empty state when the cron has never found this worker enough
 * activity to score — a brand-new worker, not an error. */
export default function ScoreMeter({ profile }: ScoreMeterProps) {
  const { t } = useI18n();

  if (profile === null) {
    return (
      <section
        aria-labelledby="fib-score-title"
        className="card-surface card-edge relative grid items-center gap-6 overflow-hidden bg-gradient-to-br from-identity-tint via-card to-card p-6 md:p-8 lg:grid-cols-[minmax(0,19rem)_minmax(0,1fr)] lg:gap-10"
      >
        <div
          aria-hidden="true"
          className="dotted pointer-events-none absolute inset-0 [mask-image:linear-gradient(90deg,#000,transparent_70%)]"
        />
        <div className="relative mx-auto w-full max-w-[15rem] animate-float">
          <PillarIllustration pillar="identity" />
        </div>
        <div className="relative space-y-5">
          <div className="space-y-2">
            <h2 id="fib-score-title" className="text-sm font-bold text-identity-ink">
              {t("fib.score.overall")}
            </h2>
            <p className="max-w-prose text-base font-medium leading-relaxed text-foreground md:text-lg">
              {t("fib.score.noProfile")}
            </p>
          </div>
          {/* The four metrics the score will be made of, waiting for their first data. */}
          <ul className="grid gap-2.5 sm:grid-cols-2">
            {METRIC_KEYS.map((key) => (
              <li key={key} className="space-y-2 rounded-xl border border-dashed bg-card/70 p-3">
                <p className="text-sm font-bold">{t(`fib.score.metrics.${key}`)}</p>
                <div className="h-1.5 w-full rounded-full bg-muted" />
                <p className="text-xs text-muted-foreground">{t("fib.score.noData")}</p>
              </li>
            ))}
          </ul>
          <Button
            asChild
            className="h-11 rounded-xl bg-identity-deep px-5 font-bold text-white hover:bg-identity-deep/90"
          >
            <Link to="/identity/log">{t("fib.score.logActivity")}</Link>
          </Button>
        </div>
      </section>
    );
  }

  const overallStatus = statusFor(profile.overall_score);
  const statusLabel = t(`fib.score.status.${overallStatus}`);

  return (
    <section
      aria-labelledby="fib-score-title"
      className="grid gap-4 lg:grid-cols-[19rem_minmax(0,1fr)]"
    >
      <div className="card-surface card-edge flex flex-col items-center gap-1 bg-gradient-to-b from-identity-tint via-card to-card p-5">
        <h2 id="fib-score-title" className="text-sm font-bold text-muted-foreground">
          {t("fib.score.overall")}
        </h2>
        <RadialGauge
          score={profile.overall_score}
          status={statusLabel}
          label={`${t("fib.score.overall")}: ${profile.overall_score}, ${statusLabel}`}
        />
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {METRIC_KEYS.map((key) => (
            <MetricMeter key={key} metricKey={key} result={profile.metrics[key]} />
          ))}
        </div>
        {profile.narrative.text && (
          <p className="card-surface p-4 text-sm leading-relaxed text-muted-foreground">
            {profile.narrative.text}
          </p>
        )}
      </div>
    </section>
  );
}

import { Crown } from "lucide-react";
import { useEffect, useRef } from "react";

import FlaggedProviderBadge from "@/components/remittance/FlaggedProviderBadge";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import type { RemittanceComparison } from "@/types/remittance";
import { CORRIDORS } from "@/utils/corridors";
import { countryName, formatMoney } from "@/utils/format";
import { safeWebUrl } from "@/utils/safeUrl";

function formatDate(isoDate: string, language: string): string {
  try {
    return new Intl.DateTimeFormat(language, { dateStyle: "medium" }).format(new Date(isoDate));
  } catch {
    return isoDate;
  }
}

/** The headline of a comparison: who is best and what the family receives. The table of every
 * service goes under it (NF-P2-019). */
export default function ComparisonSummary({ comparison }: { comparison: RemittanceComparison }) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const info = CORRIDORS[comparison.corridor_id];
  const sent = (amount: number) =>
    formatMoney(amount, comparison.send_currency, language, info.decimals);
  const received = (amount: number) =>
    formatMoney(amount, comparison.receive_currency, language, info.receiveDecimals);
  const { summary, rate, survey } = comparison;
  const anyEstimated = comparison.providers.some((p) => p.comparable && p.estimated);
  const titleRef = useRef<HTMLHeadingElement>(null);

  // On a phone the answer appears below the form: bring it into view, and move focus to its
  // title so a screen reader reads it. Each new comparison mounts this card again.
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    titleRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    titleRef.current?.focus({ preventScroll: true });
  }, []);

  return (
    <section
      aria-labelledby="remittance-result-title"
      className="card-surface card-edge animate-fade-up space-y-5 overflow-hidden bg-gradient-to-br from-remit-tint via-card to-card p-5 md:p-7"
    >
      <h2
        id="remittance-result-title"
        ref={titleRef}
        tabIndex={-1}
        className="text-lg font-bold tracking-tight focus:outline-none"
      >
        {t("remittance.result.title", {
          amount: sent(comparison.send_amount),
          country: countryName(info.home, language),
        })}
      </h2>

      <dl className="grid gap-5 sm:grid-cols-2">
        <div className="rounded-2xl border border-gold/40 bg-gold/10 p-4">
          <dt className="flex items-center gap-1.5 text-sm font-semibold text-gold-ink">
            <Crown className="h-4 w-4" aria-hidden="true" />
            {t("remittance.result.best")}
          </dt>
          <dd className="mt-1 flex flex-wrap items-center gap-2 text-2xl font-extrabold tracking-tight">
            {summary.best_firm}
            <FlaggedProviderBadge firm={summary.best_firm} />
          </dd>
        </div>
        <div className="rounded-2xl border bg-card p-4">
          <dt className="text-sm font-semibold text-muted-foreground">
            {t("remittance.result.receives")}
          </dt>
          <dd className="mt-1 text-3xl font-extrabold tabular-nums tracking-tight text-remit-ink">
            {received(summary.best_recipient_receives)}
          </dd>
        </div>
      </dl>

      <ul className="grid gap-1.5 text-sm">
        <li className="font-medium">
          {t("remittance.result.extra", {
            amount: received(summary.extra_vs_worst),
            firm: summary.worst_firm,
          })}
        </li>
        <li>
          {t("remittance.result.midMarket", { amount: received(summary.mid_market_receives) })}
        </li>
        <li>{t("remittance.result.compared", { number: String(summary.comparable_count) })}</li>
        <li className="text-muted-foreground">
          {t("remittance.result.rate", {
            send: comparison.send_currency,
            rate: rate.rate.toLocaleString(language, { maximumFractionDigits: 6 }),
            receive: comparison.receive_currency,
          })}
        </li>
      </ul>

      {(rate.stale || anyEstimated) && (
        <div className="space-y-1.5 rounded-xl border border-caution/30 bg-caution-tint p-3 text-sm text-caution-tint-ink">
          {rate.stale && <p>{t("remittance.result.staleRate")}</p>}
          {anyEstimated && <p>{t("remittance.result.estimated")}</p>}
        </div>
      )}

      <footer className="space-y-1 border-t pt-3 text-xs text-muted-foreground">
        <p>
          {t("remittance.result.survey", {
            from: formatDate(survey.surveyed_from, language),
            to: formatDate(survey.surveyed_to, language),
          })}
        </p>
        {/* The World Bank's own wording, required wherever its prices are shown. */}
        <p lang="en">
          <a
            href={safeWebUrl(survey.source_url) ?? undefined}
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            {survey.attribution}
          </a>
        </p>
      </footer>
    </section>
  );
}

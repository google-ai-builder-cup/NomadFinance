import { lazy, Suspense, useEffect, useRef, useState } from "react";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import ComparisonTable from "@/components/remittance/ComparisonTable";
import CorridorPicker from "@/components/remittance/CorridorPicker";
import FlaggedProviderBadge from "@/components/remittance/FlaggedProviderBadge";
import SavingsCallout from "@/components/remittance/SavingsCallout";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/hooks/useI18n";
import { useCompareRemittance, useLogTransfer } from "@/hooks/useRemittance";
import { toast } from "@/hooks/useToast";
import { useUserProfile } from "@/hooks/useUser";
import i18n from "@/lib/i18n";
import type { ProviderResult, RemittanceComparison } from "@/types/remittance";
import { CORRIDORS, compareFailure, defaultCorridor } from "@/utils/corridors";
import { errorMessageKey } from "@/utils/errors";
import { countryName, formatMoney } from "@/utils/format";

// recharts is a sizeable chunk (D-45): loaded only once a comparison exists to show it for.
const TrendChart = lazy(() => import("@/components/remittance/TrendChart"));

function formatDate(isoDate: string, language: string): string {
  try {
    return new Intl.DateTimeFormat(language, { dateStyle: "medium" }).format(new Date(isoDate));
  } catch {
    return isoDate;
  }
}

/** The headline of a comparison. NF-P2-019's table of every service goes under it. */
function ComparisonSummaryCard({ comparison }: { comparison: RemittanceComparison }) {
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
      className="space-y-4 rounded-lg border bg-card p-6"
    >
      <h2
        id="remittance-result-title"
        ref={titleRef}
        tabIndex={-1}
        className="text-lg font-semibold focus:outline-none"
      >
        {t("remittance.result.title", {
          amount: sent(comparison.send_amount),
          country: countryName(info.home, language),
        })}
      </h2>

      <dl className="space-y-3">
        <div>
          <dt className="text-sm text-muted-foreground">{t("remittance.result.best")}</dt>
          <dd className="flex flex-wrap items-center gap-2 text-xl font-bold">
            {summary.best_firm}
            <FlaggedProviderBadge firm={summary.best_firm} />
          </dd>
        </div>
        <div>
          <dt className="text-sm text-muted-foreground">{t("remittance.result.receives")}</dt>
          <dd className="text-2xl font-bold tabular-nums">
            {received(summary.best_recipient_receives)}
          </dd>
        </div>
      </dl>

      <ul className="space-y-1 text-sm">
        <li>
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
        <div className="space-y-1 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm">
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
          <a href={survey.source_url} target="_blank" rel="noreferrer" className="underline">
            {survey.attribution}
          </a>
        </p>
      </footer>
    </section>
  );
}

/** Remittance X-Ray: choose a corridor and an amount, see what the services cost. */
export default function RemittanceCompare() {
  const { t } = useI18n();
  const profile = useUserProfile();
  const compare = useCompareRemittance();
  const logTransfer = useLogTransfer();
  const [loggedRpwIds, setLoggedRpwIds] = useState<ReadonlySet<number>>(new Set());
  // Tracks which comparison `loggedRpwIds` belongs to, so a new one (new amount or corridor)
  // starts with nothing logged against it, even if some of the same rpw_ids show up again.
  const [loggedFor, setLoggedFor] = useState<RemittanceComparison | null>(null);
  if (compare.data && compare.data !== loggedFor) {
    setLoggedFor(compare.data);
    setLoggedRpwIds(new Set());
  }

  if (profile.isPending) {
    return <LoadingSpinner label={t("common.loading")} className="py-16" />;
  }

  function handleLog(provider: ProviderResult) {
    const comparison = compare.data;
    if (!comparison) {
      return;
    }
    logTransfer.mutate(
      { comparison, rpwId: provider.rpw_id },
      {
        onSuccess: () => {
          setLoggedRpwIds((current) => new Set(current).add(provider.rpw_id));
          toast({ messageKey: "remittance.table.logAction.toastSuccess" });
        },
        onError: (error) => {
          toast({ messageKey: errorMessageKey(error), variant: "error" });
        },
      }
    );
  }

  const language = i18n.resolvedLanguage ?? "en";
  // Without the profile the form still works; it only starts on the first corridor.
  const initialCorridor = defaultCorridor(profile.data?.host_country, profile.data?.home_country);
  const serverError =
    compare.isError && compare.variables
      ? compareFailure(compare.error, compare.variables.corridor_id, language)
      : null;

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">{t("remittance.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("remittance.subtitle")}</p>
      </header>

      <CorridorPicker
        initialCorridor={initialCorridor}
        pending={compare.isPending}
        serverError={serverError}
        onSubmit={(request) => compare.mutate(request)}
      />

      {compare.data && !compare.isPending && (
        <>
          <ComparisonSummaryCard comparison={compare.data} />
          <SavingsCallout comparison={compare.data} />
          <ComparisonTable
            comparison={compare.data}
            onLog={handleLog}
            pendingRpwId={logTransfer.isPending ? (logTransfer.variables?.rpwId ?? null) : null}
            loggedRpwIds={loggedRpwIds}
          />
          <Suspense fallback={<Skeleton className="h-64 w-full rounded-lg border" />}>
            <TrendChart comparison={compare.data} />
          </Suspense>
        </>
      )}
    </div>
  );
}

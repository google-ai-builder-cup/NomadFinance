import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import CategoryBreakdown from "@/components/fib/CategoryBreakdown";
import ScoreMeter from "@/components/fib/ScoreMeter";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useFinancialProfile, useFinancialTimeline } from "@/hooks/useFIB";
import { useI18n } from "@/hooks/useI18n";
import { majorityCurrency } from "@/utils/fibTimeline";

// recharts is a sizeable chunk (D-45, same reasoning as RemittanceCompare's TrendChart):
// loaded only once this page actually has data to chart.
const FinancialTimeline = lazy(() => import("@/components/fib/FinancialTimeline"));

/** The Financial Identity Builder's home: score meter, income-vs-expense chart, category
 * breakdown (NF-P3-017). `/identity/log` holds the quick-entry forms (NF-P3-016). */
export default function FIBDashboard() {
  const { t } = useI18n();
  const profile = useFinancialProfile();
  const timeline = useFinancialTimeline();

  if (timeline.isPending) {
    return <LoadingSpinner label={t("common.loading")} className="py-16" />;
  }

  if (timeline.isError) {
    return (
      <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
        <p className="text-sm text-muted-foreground">{t("fib.dashboard.loadError")}</p>
        <Button onClick={() => void timeline.refetch()}>{t("common.retry")}</Button>
      </div>
    );
  }

  const { income, bills, savings } = timeline.data;
  const currency = majorityCurrency([...income, ...bills, ...savings]);

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <header className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">{t("fib.dashboard.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("fib.dashboard.subtitle")}</p>
        </div>
        <Button asChild size="sm" className="shrink-0">
          <Link to="/identity/log">{t("fib.dashboard.logActivity")}</Link>
        </Button>
      </header>

      <ScoreMeter profile={profile.isSuccess ? profile.data : null} />
      {profile.isError && (
        <p className="text-xs text-destructive">
          {t("fib.dashboard.scoreLoadError")}{" "}
          <button type="button" onClick={() => void profile.refetch()} className="underline">
            {t("common.retry")}
          </button>
        </p>
      )}

      <Suspense fallback={<Skeleton className="h-64 w-full rounded-lg border" />}>
        <FinancialTimeline income={income} bills={bills} currency={currency} />
      </Suspense>
      <CategoryBreakdown income={income} bills={bills} currency={currency} />
    </div>
  );
}

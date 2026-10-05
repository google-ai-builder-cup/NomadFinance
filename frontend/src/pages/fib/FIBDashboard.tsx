import { FileDown, Fingerprint, Plus } from "lucide-react";
import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import PageHeader from "@/components/common/PageHeader";
import CategorizeEntriesCard from "@/components/fib/CategorizeEntriesCard";
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
    <div className="space-y-5">
      <PageHeader
        pillar="identity"
        icon={Fingerprint}
        title={t("fib.dashboard.title")}
        description={t("fib.dashboard.subtitle")}
        actions={
          <>
            <Button
              asChild
              className="h-11 rounded-xl bg-identity-deep px-5 font-bold text-white hover:bg-identity-deep/90"
            >
              <Link to="/identity/log">
                <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
                {t("fib.dashboard.logActivity")}
              </Link>
            </Button>
            {profile.isSuccess && profile.data !== null && (
              <Button asChild variant="outline" className="h-11 rounded-xl bg-card font-bold">
                <Link to="/identity/export">
                  <FileDown className="mr-2 h-4 w-4" aria-hidden="true" />
                  {t("fib.dashboard.exportReport")}
                </Link>
              </Button>
            )}
          </>
        }
      />

      <ScoreMeter profile={profile.isSuccess ? profile.data : null} />
      {profile.isError && (
        <p className="text-xs text-destructive">
          {t("fib.dashboard.scoreLoadError")}{" "}
          <button type="button" onClick={() => void profile.refetch()} className="underline">
            {t("common.retry")}
          </button>
        </p>
      )}

      <CategorizeEntriesCard bills={bills} />

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Suspense fallback={<Skeleton className="h-72 w-full rounded-2xl" />}>
          <FinancialTimeline income={income} bills={bills} currency={currency} />
        </Suspense>
        <CategoryBreakdown income={income} bills={bills} currency={currency} />
      </div>
    </div>
  );
}

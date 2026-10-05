import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/hooks/useI18n";

/**
 * The shape of the coming report (gauge and counts, then clause rows) while the contract is
 * checked, so the page shows where the result will appear instead of empty space (NF-P2-010).
 */
export default function ReportSkeleton() {
  const { t } = useI18n();

  return (
    <div className="space-y-4">
      <p className="sr-only">{t("contract.progress.reportLoading")}</p>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
        <div className="card-surface flex flex-col items-center gap-3 p-6">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-28 w-48 rounded-t-full" />
          <Skeleton className="h-7 w-28 rounded-full" />
        </div>
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            {[0, 1, 2].map((key) => (
              <Skeleton key={key} className="h-20 rounded-2xl" />
            ))}
          </div>
          <Skeleton className="h-28 w-full rounded-2xl" />
        </div>
      </div>
      <div className="space-y-3">
        {[0, 1, 2].map((key) => (
          <div key={key} className="card-surface space-y-2 p-4">
            <Skeleton className="h-4 w-40" />
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Skeleton className="h-14 w-full rounded-xl" />
              <Skeleton className="h-14 w-full rounded-xl" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

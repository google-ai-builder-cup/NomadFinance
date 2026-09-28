import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/hooks/useI18n";

/**
 * The shape of the coming report (score, then clause rows) while the contract is checked, so
 * the page shows where the result will appear instead of empty space (NF-P2-010).
 */
export default function ReportSkeleton() {
  const { t } = useI18n();

  return (
    <div className="space-y-4 rounded-lg border bg-card p-6">
      <p className="sr-only">{t("contract.progress.reportLoading")}</p>
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-9 w-14" />
      </div>
      <Skeleton className="h-7 w-32 rounded-full" />
      <div className="grid grid-cols-3 gap-2">
        {[0, 1, 2].map((key) => (
          <Skeleton key={key} className="h-12" />
        ))}
      </div>
      <div className="space-y-3 pt-2">
        {[0, 1, 2].map((key) => (
          <div key={key} className="space-y-2 rounded-lg border p-4">
            <Skeleton className="h-3 w-24" />
            <div className="grid gap-3 md:grid-cols-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

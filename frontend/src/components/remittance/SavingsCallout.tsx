import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/hooks/useI18n";
import { useRemittanceSavings } from "@/hooks/useRemittance";
import i18n from "@/lib/i18n";
import { ApiError } from "@/services/apiClient";
import type { RemittanceComparison } from "@/types/remittance";
import { MAX_SAVINGS_MONTHS } from "@/types/remittance";
import { CORRIDORS } from "@/utils/corridors";
import { formatMoney } from "@/utils/format";

export interface SavingsCalloutProps {
  comparison: RemittanceComparison;
}

/**
 * The "you would have saved $X" hero moment (NF-P2-022, display added NF-P2-023): what
 * choosing the best service instead of the worst would have been worth over real history, up
 * to the last 12 full calendar months. `GET /remittance/savings`; no AI call.
 */
export default function SavingsCallout({ comparison }: SavingsCalloutProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const savings = useRemittanceSavings(
    comparison.corridor_id,
    comparison.send_amount,
    MAX_SAVINGS_MONTHS
  );
  const notLoaded =
    savings.isError && savings.error instanceof ApiError && savings.error.status === 404;
  const info = CORRIDORS[comparison.corridor_id];
  const received = (amount: number) =>
    formatMoney(amount, comparison.receive_currency, language, info.receiveDecimals);

  if (savings.isPending) {
    return (
      <div className="space-y-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-6">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-9 w-56" />
        <Skeleton className="h-4 w-full max-w-sm" />
      </div>
    );
  }

  if (notLoaded) {
    return <p className="text-sm text-muted-foreground">{t("remittance.savings.notLoaded")}</p>;
  }

  if (savings.isError) {
    return (
      <div role="alert" className="flex flex-col items-start gap-2 text-sm">
        <p className="text-destructive">{t("remittance.savings.loadError")}</p>
        <Button size="sm" variant="outline" onClick={() => void savings.refetch()}>
          {t("common.retry")}
        </Button>
      </div>
    );
  }

  if (!savings.isSuccess || savings.data.total_savings <= 0 || savings.data.months_used === 0) {
    // A corridor with only one comparable service, or no history at all, has nothing to show
    // here; the comparison table above still stands on its own.
    return null;
  }

  const data = savings.data;

  return (
    <div className="space-y-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-6">
      <p className="text-sm font-medium text-emerald-800 dark:text-emerald-300">
        {t("remittance.savings.heading", { months: String(data.months_used) })}
      </p>
      <p className="text-3xl font-bold tabular-nums text-emerald-700 dark:text-emerald-400">
        {received(data.total_savings)}
      </p>
      <p className="text-sm text-muted-foreground">
        {t("remittance.savings.detail", { best: data.best_firm, worst: data.worst_firm })}
      </p>
      {data.months_used < data.months_requested && (
        <p className="text-xs text-muted-foreground">
          {t("remittance.savings.shortHistory", { months: String(data.months_used) })}
        </p>
      )}
    </div>
  );
}

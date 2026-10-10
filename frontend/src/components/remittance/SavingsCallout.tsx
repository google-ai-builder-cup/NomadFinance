import { PartyPopper } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCountUp } from "@/hooks/useCountUp";
import { useI18n } from "@/hooks/useI18n";
import { useRemittanceSavings } from "@/hooks/useRemittance";
import { useReveal } from "@/hooks/useReveal";
import i18n from "@/lib/i18n";
import { ApiError } from "@/services/apiClient";
import type { RemittanceComparison } from "@/types/remittance";
import { MAX_SAVINGS_MONTHS } from "@/types/remittance";
import { CORRIDORS } from "@/utils/corridors";
import { formatMoney } from "@/utils/format";

export interface SavingsCalloutProps {
  comparison: RemittanceComparison;
}

/** The savings figure counting up from zero when it scrolls into view. */
function SavingsFigure({
  amount,
  currency,
  digits,
}: {
  amount: number;
  currency: string;
  digits: number;
}) {
  const language = i18n.resolvedLanguage ?? "en";
  const [ref, shown] = useReveal<HTMLParagraphElement>();
  const value = useCountUp(amount, shown);
  return (
    <p
      ref={ref}
      className="text-4xl font-extrabold tabular-nums tracking-tight text-gold-ink md:text-5xl"
    >
      <span className="sr-only">{formatMoney(amount, currency, language, digits)}</span>
      <span aria-hidden="true">{formatMoney(value, currency, language, digits)}</span>
    </p>
  );
}

/**
 * The "you would have saved $X" hero moment (NF-P2-022, display added NF-P2-023): what
 * choosing the best service instead of the worst would have been worth over real history, up
 * to the last 12 full calendar months. `GET /remittance/savings`; no Gemini call.
 */
export default function SavingsCallout({ comparison }: SavingsCalloutProps) {
  const { t } = useI18n();
  const savings = useRemittanceSavings(
    comparison.corridor_id,
    comparison.send_amount,
    MAX_SAVINGS_MONTHS
  );
  const notLoaded =
    savings.isError && savings.error instanceof ApiError && savings.error.status === 404;
  const info = CORRIDORS[comparison.corridor_id];

  if (savings.isPending) {
    return (
      <div className="card-surface space-y-2 border-gold/30 p-6">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-10 w-56" />
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
        <p className="text-danger-ink">{t("remittance.savings.loadError")}</p>
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
    <div className="card-surface relative space-y-2 overflow-hidden border-gold/40 bg-gradient-to-br from-gold/20 via-card to-card p-6">
      <PartyPopper
        className="absolute right-5 top-5 h-8 w-8 animate-float text-gold-ink/60"
        aria-hidden="true"
      />
      <p className="max-w-[28ch] text-sm font-bold text-gold-ink">
        {t("remittance.savings.heading", { months: String(data.months_used) })}
      </p>
      <SavingsFigure
        amount={data.total_savings}
        currency={comparison.receive_currency}
        digits={info.receiveDecimals}
      />
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

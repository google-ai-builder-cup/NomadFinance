import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useRefreshFinancialProfile } from "@/hooks/useFIB";
import { errorMessageKey } from "@/utils/errors";

/** The first score, on request: the weekly run is how every score is kept up to date, but a new
 * worker should not wait up to a week to see theirs. Shown only while there is no score. */
export default function RefreshScore() {
  const { t } = useI18n();
  const refresh = useRefreshFinancialProfile();
  const nothingYet = refresh.isSuccess && refresh.data.status === "no_data";

  return (
    <div className="space-y-2">
      <Button
        type="button"
        variant="outline"
        className="h-11 rounded-xl bg-card px-5 font-bold"
        onClick={() => refresh.mutate()}
        disabled={refresh.isPending}
        aria-busy={refresh.isPending}
      >
        {refresh.isPending ? t("fib.score.refresh.working") : t("fib.score.refresh.button")}
      </Button>
      {nothingYet && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("fib.score.refresh.noData")}
        </p>
      )}
      {refresh.isError && (
        <p role="alert" className="text-sm font-medium text-danger-ink">
          {t(errorMessageKey(refresh.error))}
        </p>
      )}
    </div>
  );
}

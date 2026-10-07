import { History, ScanSearch } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import PageHeader from "@/components/common/PageHeader";
import HistoryItem from "@/components/scam/HistoryItem";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useScamHistory } from "@/hooks/useScamChecks";

/** The worker's past checks, newest first, a page at a time behind a "Show more" button (a button
 * and not endless scrolling, so a worker on a slow phone chooses when to spend the data). Every
 * row opens the stored check. Checks are kept 90 days and only the worker can see them. */
export default function ScamHistory() {
  const { t } = useI18n("scam");
  const history = useScamHistory();
  const checks = history.data?.pages.flatMap((page) => page.items) ?? [];
  const list = useRef<HTMLUListElement>(null);
  // The index of the first row the next page will add, until focus has been moved to it.
  const focusRow = useRef<number | null>(null);

  useEffect(() => {
    if (focusRow.current !== null && checks.length > focusRow.current) {
      list.current?.querySelectorAll("a")[focusRow.current]?.focus();
      focusRow.current = null;
    }
  }, [checks.length]);

  function showMore() {
    focusRow.current = checks.length;
    void history.fetchNextPage();
  }

  const checkNew = (
    <Button asChild variant="outline" className="min-h-11 rounded-xl bg-card font-bold">
      <Link to="/scam-check">{t("history.checkNew")}</Link>
    </Button>
  );

  return (
    <div className="space-y-5">
      <PageHeader
        pillar="radar"
        icon={History}
        title={t("history.title")}
        description={t("history.description")}
        actions={checkNew}
        compact
      />

      {history.isPending ? (
        <LoadingSpinner label={t("common.loading")} className="py-16" />
      ) : history.isError && checks.length === 0 ? (
        <div role="alert" className="flex flex-col items-center gap-4 py-12 text-center">
          <p className="text-sm text-muted-foreground">{t("history.loadError")}</p>
          <Button className="min-h-11" onClick={() => void history.refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      ) : checks.length === 0 ? (
        <EmptyState
          icon={ScanSearch}
          title={t("history.empty.title")}
          description={t("history.empty.description")}
          action={
            <Button asChild className="min-h-11">
              <Link to="/scam-check">{t("history.checkNew")}</Link>
            </Button>
          }
        />
      ) : (
        <>
          <ul ref={list} className="space-y-3">
            {checks.map((check) => (
              <li key={check.id}>
                <HistoryItem check={check} />
              </li>
            ))}
          </ul>

          {history.isFetchNextPageError && (
            <p role="alert" className="text-center text-sm font-semibold text-danger-ink">
              {t("history.loadMoreError")}
            </p>
          )}
          {history.hasNextPage && (
            <Button
              type="button"
              variant="outline"
              className="min-h-11 w-full"
              disabled={history.isFetchingNextPage}
              onClick={showMore}
            >
              {history.isFetchingNextPage ? t("history.loadingMore") : t("history.showMore")}
            </Button>
          )}
        </>
      )}
    </div>
  );
}

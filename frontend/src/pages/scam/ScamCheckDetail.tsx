import { ArrowLeft, FileSearch, History } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import PageHeader from "@/components/common/PageHeader";
import ScamResult from "@/components/scam/ScamResult";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useScamCheck } from "@/hooks/useScamChecks";
import i18n from "@/lib/i18n";
import { ApiError } from "@/services/apiClient";
import { formatCheckDate } from "@/utils/scamHistory";

/** One stored check, drawn exactly like a fresh result (card, explanation, "Warn other workers"),
 * with the day it was checked and the day it will be removed. */
export default function ScamCheckDetail() {
  const { t } = useI18n("scam");
  const { id = "" } = useParams<{ id: string }>();
  const check = useScamCheck(id);
  const language = i18n.resolvedLanguage ?? "en";

  const back = (
    <Button asChild variant="outline" className="min-h-11 gap-1.5 rounded-xl bg-card font-bold">
      <Link to="/scam-check/history">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        {t("history.back")}
      </Link>
    </Button>
  );

  // Every state carries the page's heading, so a screen reader always starts from a title.
  const header = (title: string, description?: string) => (
    <PageHeader
      pillar="radar"
      icon={History}
      title={title}
      description={description}
      actions={back}
      compact
    />
  );

  if (check.isPending) {
    return (
      <div className="space-y-5">
        {header(t("history.title"))}
        <LoadingSpinner label={t("common.loading")} className="py-16" />
      </div>
    );
  }

  // A check that is gone, past its 90 days or someone else's gets the same answer from the server.
  if (check.isError && check.error instanceof ApiError && check.error.status === 404) {
    return (
      <div className="space-y-5">
        {header(t("history.title"))}
        <EmptyState
          icon={FileSearch}
          headingLevel={2}
          title={t("history.notFound.title")}
          description={t("history.notFound.description")}
        />
      </div>
    );
  }

  if (check.isError) {
    return (
      <div className="space-y-5">
        {header(t("history.title"))}
        <div role="alert" className="flex flex-col items-center gap-4 py-12 text-center">
          <p className="text-sm text-muted-foreground">{t("history.detailLoadError")}</p>
          <Button className="min-h-11" onClick={() => void check.refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {header(
        t("history.detailTitle", { date: formatCheckDate(check.data.created_at, language) }),
        t("history.keptUntil", { date: formatCheckDate(check.data.expires_at, language) })
      )}
      <ScamResult result={check.data} />
      <Button asChild variant="outline" className="min-h-11 w-full">
        <Link to="/scam-check">{t("result.checkAnother")}</Link>
      </Button>
    </div>
  );
}

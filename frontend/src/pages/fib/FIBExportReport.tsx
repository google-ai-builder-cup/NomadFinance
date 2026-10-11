import { FileDown, Share2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import PageHeader from "@/components/common/PageHeader";
import PageStateFrame from "@/components/common/PageStateFrame";
import ReportDocCard from "@/components/fib/ReportDocCard";
import ReportPreviewModal from "@/components/fib/ReportPreviewModal";
import { fieldClass, submitClass } from "@/components/fib/styles";
import { Button } from "@/components/ui/button";
import { useExportReport, useFinancialProfile, useLatestReport } from "@/hooks/useFIB";
import { useI18n } from "@/hooks/useI18n";
import { toast } from "@/hooks/useToast";
import i18n from "@/lib/i18n";
import { ApiError } from "@/services/apiClient";
import { MAX_HOLDER_NAME_CHARS } from "@/types/fib";
import { errorMessageKey } from "@/utils/errors";

function formatDate(isoDate: string, language: string): string {
  try {
    return new Intl.DateTimeFormat(language, { dateStyle: "medium", timeStyle: "short" }).format(
      new Date(isoDate)
    );
  } catch {
    return isoDate;
  }
}

/** Shares `url` with the OS share sheet where available, else copies it to the clipboard. */
async function shareOrCopy(url: string, title: string): Promise<"shared" | "copied" | "failed"> {
  const shareData = { title, url };
  if (navigator.share && (!navigator.canShare || navigator.canShare(shareData))) {
    try {
      await navigator.share(shareData);
      return "shared";
    } catch (error) {
      // The person cancelling the share sheet is not a failure.
      return error instanceof Error && error.name === "AbortError" ? "shared" : "failed";
    }
  }
  try {
    await navigator.clipboard.writeText(url);
    return "copied";
  } catch {
    return "failed";
  }
}

/** Trigger, preview and share the portable Financial Identity PDF (NF-P3-018), on top of
 * `POST`/`GET /fib/report/export` (NF-P3-014). */
export default function FIBExportReport() {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const profile = useFinancialProfile();
  const latestReport = useLatestReport();
  const exportReport = useExportReport();
  const [holderName, setHolderName] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);

  if (profile.isPending) {
    return (
      <PageStateFrame pillar="identity" icon={FileDown} title={t("fib.export.title")}>
        <LoadingSpinner label={t("common.loading")} className="py-16" />
      </PageStateFrame>
    );
  }

  if (profile.isError) {
    return (
      <PageStateFrame pillar="identity" icon={FileDown} title={t("fib.export.title")}>
        <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-sm text-muted-foreground">{t("fib.export.profileLoadError")}</p>
          <Button onClick={() => void profile.refetch()}>{t("common.retry")}</Button>
        </div>
      </PageStateFrame>
    );
  }

  const financialProfile = profile.data;

  if (financialProfile === null) {
    return (
      <div className="space-y-5">
        <PageHeader pillar="identity" icon={FileDown} title={t("fib.export.title")} compact />
        <section className="card-surface mx-auto max-w-lg space-y-3 p-6 text-center">
          <p className="text-sm text-muted-foreground">{t("fib.score.noProfile")}</p>
          <Button
            asChild
            className="h-11 rounded-xl bg-identity-deep px-5 font-bold text-white hover:bg-identity-deep/90"
          >
            <Link to="/identity/log">{t("fib.score.logActivity")}</Link>
          </Button>
        </section>
      </div>
    );
  }

  const report = latestReport.isSuccess ? latestReport.data : null;
  const noReportYet =
    latestReport.isError &&
    latestReport.error instanceof ApiError &&
    latestReport.error.status === 404;

  async function handleShare(url: string) {
    const outcome = await shareOrCopy(url, t("fib.export.shareTitle"));
    if (outcome === "copied") {
      toast({ messageKey: "fib.export.linkCopied" });
    } else if (outcome === "failed") {
      toast({ messageKey: "fib.export.shareFailed", variant: "error" });
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        pillar="identity"
        icon={FileDown}
        title={t("fib.export.title")}
        description={t("fib.export.subtitle")}
        compact
      />

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <div className="space-y-5">
          <section className="card-surface space-y-4 p-5 md:p-6">
            <div className="space-y-1.5">
              <label htmlFor="export-holder-name" className="text-sm font-bold">
                {t("fib.export.holderName")}
              </label>
              <input
                id="export-holder-name"
                type="text"
                value={holderName}
                maxLength={MAX_HOLDER_NAME_CHARS}
                onChange={(event) => setHolderName(event.target.value)}
                placeholder={t("fib.export.holderNamePlaceholder")}
                className={fieldClass}
              />
              <p className="text-xs text-muted-foreground">{t("fib.export.holderNameHint")}</p>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                className="h-12 rounded-xl bg-card px-5 font-bold"
                onClick={() => setPreviewOpen(true)}
              >
                {t("fib.export.preview.open")}
              </Button>
              <Button
                type="button"
                className={`${submitClass} w-auto px-5`}
                disabled={exportReport.isPending}
                onClick={() => exportReport.mutate({ holder_name: holderName.trim() || undefined })}
              >
                {exportReport.isPending
                  ? t("fib.export.generating")
                  : report
                    ? t("fib.export.regenerate")
                    : t("fib.export.generate")}
              </Button>
            </div>

            {exportReport.isError && (
              <p role="alert" className="text-sm text-danger-ink">
                {t(errorMessageKey(exportReport.error))}
              </p>
            )}
          </section>

          {latestReport.isPending && (
            <LoadingSpinner label={t("common.loading")} className="py-6" />
          )}

          {report && (
            <section className="card-surface space-y-3 border-safe/30 bg-gradient-to-br from-safe-tint via-card to-card p-5 md:p-6">
              <p className="text-sm font-medium text-muted-foreground">
                {t("fib.export.readyAt", { date: formatDate(report.created_at, language) })}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  asChild
                  className="h-11 rounded-xl bg-identity-deep px-5 font-bold text-white hover:bg-identity-deep/90"
                >
                  <a href={report.download_url}>
                    <FileDown className="mr-2 h-4 w-4" aria-hidden="true" />
                    {t("fib.export.download")}
                  </a>
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="h-11 rounded-xl bg-card px-5 font-bold"
                  onClick={() => void handleShare(report.download_url)}
                >
                  <Share2 className="mr-2 h-4 w-4" aria-hidden="true" />
                  {t("fib.export.share")}
                </Button>
              </div>
            </section>
          )}

          {noReportYet && !exportReport.isPending && !report && (
            <p className="text-sm text-muted-foreground">{t("fib.export.noneYet")}</p>
          )}
        </div>

        <ReportDocCard profile={financialProfile} holderName={holderName.trim()} />
      </div>

      {previewOpen && (
        <ReportPreviewModal
          profile={financialProfile}
          holderName={holderName.trim() || null}
          onClose={() => setPreviewOpen(false)}
        />
      )}
    </div>
  );
}

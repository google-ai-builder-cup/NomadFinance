import { CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import type { SubmitReportResult } from "@/hooks/useRadar";

export interface ReportConfirmationProps {
  result: SubmitReportResult;
  onAnother: () => void;
}

/** Shown once the report is stored: what the system understood, and how the evidence went. */
export default function ReportConfirmation({ result, onAnother }: ReportConfirmationProps) {
  const { t } = useI18n();
  const { report, attached, failed } = result;

  return (
    <div className="space-y-6">
      <div className="flex flex-col items-center gap-3 text-center">
        <CheckCircle2 className="h-12 w-12 text-primary" aria-hidden="true" />
        <h1 className="text-2xl font-bold tracking-tight">{t("radar.report.done.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("radar.report.done.subtitle")}</p>
      </div>

      <dl className="space-y-3 rounded-lg border bg-card p-4 text-sm">
        <div>
          <dt className="text-xs text-muted-foreground">{t("radar.report.done.about")}</dt>
          <dd className="font-medium">{report.entity_name}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">{t("radar.report.done.violation")}</dt>
          <dd className="font-medium">{t(`radar.violation.${report.violation_type}`)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">{t("radar.report.done.summary")}</dt>
          <dd>{report.summary}</dd>
        </div>
      </dl>

      {attached > 0 && (
        <p className="text-sm text-muted-foreground">
          {t("radar.report.done.evidenceAttached", { n: attached })}
        </p>
      )}
      {failed > 0 && (
        <p role="alert" className="text-sm text-destructive">
          {t("radar.report.done.evidenceFailed", { n: failed })}
        </p>
      )}

      <p className="text-xs text-muted-foreground">{t("radar.report.privacy")}</p>

      <div className="flex flex-col gap-3 sm:flex-row">
        <Button className="h-11 flex-1" onClick={onAnother}>
          {t("radar.report.done.another")}
        </Button>
        <Button asChild variant="outline" className="h-11 flex-1">
          <Link to="/dashboard">{t("comingSoon.backToDashboard")}</Link>
        </Button>
      </div>
    </div>
  );
}

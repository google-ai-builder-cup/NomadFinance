import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import type { RadarReportSummary } from "@/types/radar";

export interface EntityReportListProps {
  reports: readonly RadarReportSummary[];
}

/** The individual reports behind one entity's profile, newest first (NF-P3-008). */
export default function EntityReportList({ reports }: EntityReportListProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";

  if (reports.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("radar.entity.noReports")}</p>;
  }

  return (
    <ul className="space-y-3">
      {reports.map((report) => (
        <li key={report.report_id} className="space-y-1.5 rounded-lg border bg-card p-4 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <span className="font-medium">{t(`radar.violation.${report.violation_type}`)}</span>
            <span className="text-xs text-muted-foreground">
              {new Date(report.created_at).toLocaleDateString(language, {
                year: "numeric",
                month: "short",
                day: "numeric",
              })}
            </span>
          </div>
          <p>{report.summary ?? report.description}</p>
          <p className="text-xs text-muted-foreground">
            {t(`radar.entity.reportSource.${report.source}`)}
          </p>
        </li>
      ))}
    </ul>
  );
}

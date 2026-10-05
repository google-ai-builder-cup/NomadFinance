import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import type { RadarReportSummary } from "@/types/radar";

export interface EntityReportListProps {
  reports: readonly RadarReportSummary[];
  /** "compact" drops the card around each report, for a list that already sits in a card. */
  variant?: "cards" | "compact";
  /** Extra line under a report, such as the route when it differs from the one on screen. */
  note?: (report: RadarReportSummary) => string | null;
}

/** The individual reports behind one entity's profile, newest first (NF-P3-008). */
export default function EntityReportList({
  reports,
  variant = "cards",
  note,
}: EntityReportListProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const compact = variant === "compact";

  if (reports.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("radar.entity.noReports")}</p>;
  }

  return (
    <ul className={compact ? "divide-y" : "space-y-3"}>
      {reports.map((report) => {
        const extra = note?.(report) ?? null;
        return (
          <li
            key={report.report_id}
            className={
              compact
                ? "space-y-1 py-3 text-sm first:pt-0 last:pb-0"
                : "card-surface space-y-1.5 p-4 text-sm"
            }
          >
            <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
              <span className="font-bold">{t(`radar.violation.${report.violation_type}`)}</span>
              <span className="text-xs text-muted-foreground">
                {new Date(report.created_at).toLocaleDateString(language, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
              </span>
            </div>
            <p className="break-words">{report.summary ?? report.description}</p>
            <p className="text-xs text-muted-foreground">
              {t(`radar.entity.reportSource.${report.source}`)}
              {extra !== null && ` · ${extra}`}
            </p>
          </li>
        );
      })}
    </ul>
  );
}

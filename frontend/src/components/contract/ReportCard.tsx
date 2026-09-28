import ClauseRow from "@/components/contract/ClauseRow";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import type { ContractAnalysis, ContractReport } from "@/types/contract";
import { RISK_BADGE_CLASSES } from "@/utils/contractRisk";

export interface ReportCardProps {
  /** Score, risk level and counts (`POST .../analyze`, or rebuilt from the contract document). */
  analysis: ContractAnalysis;
  /** The full report in `analysis.report_language` (`reports/{language}`, read from Firestore). */
  report: ContractReport;
}

/**
 * The Contract Health Report (NF-P2-011): risk score header, plain-language summary, then
 * every clause with its flag and a side-by-side view of the clause against the labor law.
 */
export default function ReportCard({ analysis, report }: ReportCardProps) {
  const { t } = useI18n();
  const clauses = [...report.clauses].sort((a, b) => a.index - b.index);

  return (
    <div className="space-y-6">
      <div className="space-y-4 rounded-lg border bg-card p-6">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-muted-foreground">
            {t("contract.result.score")}
          </span>
          <span className="text-3xl font-bold tabular-nums">{analysis.health_score}</span>
        </div>
        <div
          className={cn(
            "inline-flex items-center rounded-full border px-3 py-1 text-sm font-medium",
            RISK_BADGE_CLASSES[analysis.risk_level]
          )}
        >
          {t(`contract.result.riskLevel.${analysis.risk_level}`)}
        </div>
        <dl className="grid grid-cols-3 gap-2 text-center text-sm">
          <div>
            <dt className="text-muted-foreground">{t("contract.result.counts.safe")}</dt>
            <dd className="text-lg font-semibold">{analysis.clause_counts.safe}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{t("contract.result.counts.caution")}</dt>
            <dd className="text-lg font-semibold">{analysis.clause_counts.caution}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{t("contract.result.counts.danger")}</dt>
            <dd className="text-lg font-semibold">{analysis.clause_counts.danger}</dd>
          </div>
        </dl>
        <p className="text-sm">{report.summary}</p>
        {analysis.complaint_pending && (
          <p className="text-sm text-muted-foreground">{t("contract.result.complaintPending")}</p>
        )}
      </div>

      {clauses.length > 0 && (
        <section aria-labelledby="contract-report-heading" className="space-y-3">
          <h2 id="contract-report-heading" className="text-lg font-semibold">
            {t("contract.report.heading")}
          </h2>
          <div className="hidden gap-3 px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground md:grid md:grid-cols-2">
            <span>{t("contract.report.contractColumn")}</span>
            <span>{t("contract.report.lawColumn")}</span>
          </div>
          <ul className="space-y-3">
            {clauses.map((clause) => (
              <ClauseRow key={clause.index} clause={clause} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

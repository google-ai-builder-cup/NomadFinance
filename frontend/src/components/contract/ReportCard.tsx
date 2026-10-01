import { useState } from "react";

import ClauseRow from "@/components/contract/ClauseRow";
import ComplaintPreview from "@/components/contract/ComplaintPreview";
import FlaggedParties from "@/components/contract/FlaggedParties";
import { Button } from "@/components/ui/button";
import { InfoTooltip } from "@/components/ui/tooltip";
import { useWriteMissingLetter } from "@/hooks/useContract";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import type { ClauseRisk, ContractAnalysis, ContractReport } from "@/types/contract";
import { RISK_BADGE_CLASSES } from "@/utils/contractRisk";
import { letterPendingKey } from "@/utils/letterPending";
import { requestFailureKey } from "@/utils/pipelineProgress";

export interface ReportCardProps {
  /** Score, risk level and counts (`POST .../analyze`, or rebuilt from the contract document). */
  analysis: ContractAnalysis;
  /** The full report in `analysis.report_language` (`reports/{language}`, read from Firestore). */
  report: ContractReport;
}

// A fair contract's boilerplate is rarely what a worker needs to read first, so a safe
// clause starts closed; anything worth a flag starts open.
function opensByDefault(risk: ClauseRisk): boolean {
  return risk !== "safe";
}

/**
 * An unlawful clause but no complaint letter yet: the AI service failed when it was due, or
 * (before the fix for this) the letter templates were not loaded. Writing it again reuses
 * the stored analysis, so it costs one AI call, not a new check.
 */
function MissingLetter({ analysis }: { analysis: ContractAnalysis }) {
  const { t } = useI18n();
  const write = useWriteMissingLetter();
  // The latest try's reason, else the one stored from the check itself.
  const pending = write.isSuccess
    ? write.data.complaint_pending
      ? { reason: write.data.complaint_pending_reason }
      : null
    : analysis.complaint_pending
      ? { reason: analysis.complaint_pending_reason }
      : null;

  return (
    <section
      aria-labelledby="contract-missing-letter"
      className="space-y-3 rounded-lg border border-dashed p-4"
    >
      <h2 id="contract-missing-letter" className="font-semibold">
        {t("contract.complaint.missing.title")}
      </h2>
      <p className="text-sm text-muted-foreground">{t("contract.complaint.missing.body")}</p>
      {pending && (
        <p className="text-sm" aria-live="polite">
          {t(letterPendingKey(pending.reason))}
        </p>
      )}
      {write.isError && (
        <p role="alert" className="text-sm text-destructive">
          {t(requestFailureKey(write.error))}
        </p>
      )}
      <Button size="sm" onClick={() => write.mutate(analysis)} disabled={write.isPending}>
        {write.isPending
          ? t("contract.complaint.missing.writing")
          : t("contract.complaint.missing.action")}
      </Button>
    </section>
  );
}

/**
 * The Contract Health Report (NF-P2-011; expand/collapse, the score tooltip and sticky
 * columns added NF-P2-023): risk score header, plain-language summary, then every clause
 * with its flag and a side-by-side view of the clause against the labor law.
 */
export default function ReportCard({ analysis, report }: ReportCardProps) {
  const { t } = useI18n();
  const clauses = [...report.clauses].sort((a, b) => a.index - b.index);
  // Only the rows a worker has explicitly opened or closed; everything else falls back to
  // opensByDefault. A new report (a different contract, or a language switch) starts fresh.
  const [overrides, setOverrides] = useState<Record<number, boolean>>({});

  function isExpanded(clause: ContractReport["clauses"][number]): boolean {
    return overrides[clause.index] ?? opensByDefault(clause.risk);
  }

  function toggle(clause: ContractReport["clauses"][number]) {
    setOverrides((current) => ({ ...current, [clause.index]: !isExpanded(clause) }));
  }

  function expandAll() {
    setOverrides(Object.fromEntries(clauses.map((clause) => [clause.index, true])));
  }

  function collapseAll() {
    setOverrides(Object.fromEntries(clauses.map((clause) => [clause.index, false])));
  }

  return (
    <div className="space-y-6">
      <div className="space-y-4 rounded-lg border bg-card p-6">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
            {t("contract.result.score")}
            <InfoTooltip label={t("contract.result.scoreInfoLabel")}>
              {t("contract.result.scoreInfo")}
            </InfoTooltip>
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
        <FlaggedParties contractId={analysis.contract_id} />
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
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="contract-report-heading" className="text-lg font-semibold">
              {t("contract.report.heading")}
            </h2>
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" onClick={expandAll}>
                {t("contract.report.expandAll")}
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={collapseAll}>
                {t("contract.report.collapseAll")}
              </Button>
            </div>
          </div>
          {/* Stays visible while scrolling a long clause list; top-14 matches the app header's
              own sticky height (h-14) so the two never overlap. */}
          <div className="sticky top-14 z-10 hidden gap-3 rounded-md bg-background/95 px-1 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground backdrop-blur supports-[backdrop-filter]:bg-background/80 md:grid md:grid-cols-2">
            <span>{t("contract.report.contractColumn")}</span>
            <span>{t("contract.report.lawColumn")}</span>
          </div>
          <ul className="space-y-3">
            {clauses.map((clause) => (
              <ClauseRow
                key={clause.index}
                clause={clause}
                expanded={isExpanded(clause)}
                onToggle={() => toggle(clause)}
              />
            ))}
          </ul>
        </section>
      )}

      {report.complaint ? (
        <ComplaintPreview complaint={report.complaint} />
      ) : (
        analysis.clause_counts.danger > 0 && <MissingLetter analysis={analysis} />
      )}
    </div>
  );
}

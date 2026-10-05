import { useState } from "react";

import ClauseRow from "@/components/contract/ClauseRow";
import ComplaintPreview from "@/components/contract/ComplaintPreview";
import FlaggedParties from "@/components/contract/FlaggedParties";
import { Sparkles } from "lucide-react";

import RiskBadge from "@/components/common/RiskBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoTooltip } from "@/components/ui/tooltip";
import RiskGauge from "@/components/visual/RiskGauge";
import { useWriteMissingLetter } from "@/hooks/useContract";
import { useI18n } from "@/hooks/useI18n";
import type { ClauseRisk, ContractAnalysis, ContractReport } from "@/types/contract";
import { letterPendingKey } from "@/utils/letterPending";
import { requestFailureKey } from "@/utils/pipelineProgress";

export interface ReportCardProps {
  /** Score, risk level and counts (`POST .../analyze`, or rebuilt from the contract document). */
  analysis: ContractAnalysis;
  /** The full report in `analysis.report_language` (`reports/{language}`, read from Firestore). */
  report: ContractReport;
}

const COUNT_TILE: Record<"safe" | "caution" | "danger", string> = {
  safe: "border-safe/25 bg-safe-tint text-safe-tint-ink",
  caution: "border-caution/30 bg-caution-tint text-caution-tint-ink",
  danger: "border-danger/25 bg-danger-tint text-danger-tint-ink",
};

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
      className="space-y-3 rounded-2xl border border-dashed bg-card p-5"
    >
      <h2 id="contract-missing-letter" className="font-bold">
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
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
        <section
          aria-label={t("contract.result.score")}
          className="card-surface card-edge flex flex-col items-center gap-3 p-6 text-center"
        >
          <span className="flex items-center gap-1.5 text-sm font-bold text-muted-foreground">
            {t("contract.result.score")}
            <InfoTooltip label={t("contract.result.scoreInfoLabel")}>
              {t("contract.result.scoreInfo")}
            </InfoTooltip>
          </span>
          <RiskGauge
            score={analysis.health_score}
            label={t("contract.result.gaugeLabel", {
              score: analysis.health_score,
              level: t(`contract.result.riskLevel.${analysis.risk_level}`),
            })}
            safeLabel={t("contract.result.counts.safe")}
            dangerLabel={t("contract.result.counts.danger")}
          />
          <p className="-mt-2 text-5xl font-extrabold leading-none tracking-tight tabular-nums">
            {analysis.health_score}
          </p>
          <RiskBadge level={analysis.risk_level} className="px-3 py-1 text-sm">
            {t(`contract.result.riskLevel.${analysis.risk_level}`)}
          </RiskBadge>
        </section>

        <div className="space-y-4">
          <dl className="grid grid-cols-3 gap-3 text-center">
            {(["safe", "caution", "danger"] as const).map((level) => (
              <div key={level} className={`rounded-2xl border p-4 ${COUNT_TILE[level]}`}>
                <dt className="text-xs font-bold uppercase tracking-wide">
                  {t(`contract.result.counts.${level}`)}
                </dt>
                <dd className="mt-1 text-3xl font-extrabold tabular-nums">
                  {analysis.clause_counts[level]}
                </dd>
              </div>
            ))}
          </dl>
          <FlaggedParties contractId={analysis.contract_id} />
          <section className="ai-border space-y-2 rounded-2xl bg-card p-5">
            <div className="flex items-center justify-between gap-2">
              <h2 className="flex items-center gap-2 text-sm font-bold text-contract-ink">
                <Sparkles className="h-4 w-4" aria-hidden="true" />
                {t("contract.report.summaryHeading")}
              </h2>
              <Badge tone="info">{t("landing.hero.chips.gemini")}</Badge>
            </div>
            <p className="text-[15px] leading-relaxed">{report.summary}</p>
          </section>
          {analysis.complaint_pending && (
            <p className="text-sm text-muted-foreground">{t("contract.result.complaintPending")}</p>
          )}
        </div>
      </div>

      {clauses.length > 0 && (
        <section aria-labelledby="contract-report-heading" className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="contract-report-heading" className="text-lg font-bold tracking-tight">
              {t("contract.report.heading")}
            </h2>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9 rounded-lg"
                onClick={expandAll}
              >
                {t("contract.report.expandAll")}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9 rounded-lg"
                onClick={collapseAll}
              >
                {t("contract.report.collapseAll")}
              </Button>
            </div>
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

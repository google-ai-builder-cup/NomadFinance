import { ChevronDown } from "lucide-react";
import { useId } from "react";

import RiskBadge from "@/components/common/RiskBadge";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import type { ClauseRisk, ReportClause } from "@/types/contract";
import { RISK_BAR_CLASSES } from "@/utils/contractRisk";

export interface ClauseRowProps {
  clause: ReportClause;
  /** Whether the clause's own text, law comparison and explanation are shown. */
  expanded: boolean;
  onToggle: () => void;
}

// The contract's own words take the colour of their risk; the law side stays neutral so the
// two panels read as "what you were given" against "what applies".
const CONTRACT_PANEL: Record<ClauseRisk, string> = {
  safe: "bg-safe-tint text-safe-tint-ink",
  caution: "bg-caution-tint text-caution-tint-ink",
  danger: "bg-danger-tint text-danger-tint-ink",
};

/**
 * One assessed term of the report (NF-P2-011, expand/collapse added NF-P2-023): a severity
 * bar and badge, then the clause's exact words next to what the law says about it. Side by
 * side on wider screens, stacked on a phone. `danger` and `caution` clauses start expanded;
 * `safe` ones start collapsed, since a fair contract's boilerplate is rarely what a worker
 * needs to read first — every row can still be opened or closed.
 */
export default function ClauseRow({ clause, expanded, onToggle }: ClauseRowProps) {
  const { t } = useI18n();
  const detailId = useId();
  const meta =
    clause.number !== null
      ? t("contract.report.clauseWithNumber", { number: clause.number, page: clause.page })
      : t("contract.report.clauseNoNumber", { page: clause.page });

  return (
    <li
      className={cn(
        "card-surface flex overflow-hidden transition-shadow duration-base",
        expanded && "shadow-md"
      )}
    >
      <span className={cn("w-1.5 shrink-0", RISK_BAR_CLASSES[clause.risk])} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-controls={detailId}
          className="flex min-h-14 w-full flex-wrap items-center gap-x-3 gap-y-1 p-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        >
          <RiskBadge level={clause.risk}>{t(`contract.result.counts.${clause.risk}`)}</RiskBadge>
          <span className="text-sm font-bold">{t(`contract.category.${clause.category}`)}</span>
          <span className="text-xs text-muted-foreground">{meta}</span>
          <ChevronDown
            aria-hidden="true"
            className={cn(
              "ml-auto h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-base",
              expanded && "rotate-180"
            )}
          />
        </button>

        {expanded && (
          <div id={detailId} className="grid grid-cols-1 gap-3 p-4 pt-0 md:grid-cols-2">
            <div className={cn("space-y-1 rounded-xl p-3.5", CONTRACT_PANEL[clause.risk])}>
              <p className="text-xs font-bold uppercase tracking-wide">
                {t("contract.report.contractColumn")}
              </p>
              <p className="text-sm">{clause.text}</p>
            </div>
            <div className="space-y-1 rounded-xl bg-muted p-3.5">
              <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                {t("contract.report.lawColumn")}
              </p>
              <p className="text-sm font-medium">
                {clause.law_reference ?? t("contract.report.noLawReference")}
              </p>
              <p className="text-sm text-muted-foreground">{clause.explanation}</p>
              {clause.recommendation && (
                <p className="text-sm font-semibold">
                  {t("contract.report.recommendation")} {clause.recommendation}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </li>
  );
}

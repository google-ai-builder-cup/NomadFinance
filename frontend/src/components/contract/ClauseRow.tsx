import { ChevronDown } from "lucide-react";
import { useId } from "react";

import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import type { ReportClause } from "@/types/contract";
import { RISK_DOT_CLASSES } from "@/utils/contractRisk";

export interface ClauseRowProps {
  clause: ReportClause;
  /** Whether the clause's own text, law comparison and explanation are shown. */
  expanded: boolean;
  onToggle: () => void;
}

/**
 * One assessed term of the report (NF-P2-011, expand/collapse added NF-P2-023): a 🟢🟡🔴
 * flag, then the clause's exact words next to what the law says about it. Side by side on
 * wider screens, stacked on a phone. `danger` and `caution` clauses start expanded; `safe`
 * ones start collapsed, since a fair contract's boilerplate is rarely what a worker needs to
 * read first — every row can still be opened or closed.
 */
export default function ClauseRow({ clause, expanded, onToggle }: ClauseRowProps) {
  const { t } = useI18n();
  const detailId = useId();
  const meta =
    clause.number !== null
      ? t("contract.report.clauseWithNumber", { number: clause.number, page: clause.page })
      : t("contract.report.clauseNoNumber", { page: clause.page });

  return (
    <li className="rounded-lg border">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        aria-controls={detailId}
        className="flex w-full flex-wrap items-center gap-2 p-4 text-left text-xs text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        <span
          className={cn("h-2.5 w-2.5 shrink-0 rounded-full", RISK_DOT_CLASSES[clause.risk])}
          aria-hidden="true"
        />
        <span className="sr-only">{t(`contract.result.riskLevel.${clause.risk}`)}</span>
        <span>{t(`contract.category.${clause.category}`)}</span>
        <span aria-hidden="true">·</span>
        <span>{meta}</span>
        <ChevronDown
          aria-hidden="true"
          className={cn("ml-auto h-4 w-4 shrink-0 transition-transform", expanded && "rotate-180")}
        />
      </button>

      {expanded && (
        <div id={detailId} className="grid grid-cols-1 gap-3 border-t p-4 pt-3 md:grid-cols-2">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground md:hidden">
              {t("contract.report.contractColumn")}
            </p>
            <p className="text-sm">{clause.text}</p>
          </div>
          <div className="space-y-1 border-t pt-3 md:border-l md:border-t-0 md:pl-4 md:pt-0">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground md:hidden">
              {t("contract.report.lawColumn")}
            </p>
            <p className="text-sm">{clause.law_reference ?? t("contract.report.noLawReference")}</p>
            <p className="text-sm text-muted-foreground">{clause.explanation}</p>
            {clause.recommendation && (
              <p className="text-sm font-medium">
                {t("contract.report.recommendation")} {clause.recommendation}
              </p>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

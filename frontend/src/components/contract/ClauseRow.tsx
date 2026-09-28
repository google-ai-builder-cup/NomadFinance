import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import type { ReportClause } from "@/types/contract";
import { RISK_DOT_CLASSES } from "@/utils/contractRisk";

export interface ClauseRowProps {
  clause: ReportClause;
}

/**
 * One assessed term of the report (NF-P2-011): a 🟢🟡🔴 flag, then the clause's exact words
 * next to what the law says about it. Side by side on wider screens, stacked on a phone.
 */
export default function ClauseRow({ clause }: ClauseRowProps) {
  const { t } = useI18n();
  const meta =
    clause.number !== null
      ? t("contract.report.clauseWithNumber", { number: clause.number, page: clause.page })
      : t("contract.report.clauseNoNumber", { page: clause.page });

  return (
    <li className="space-y-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span
          className={cn("h-2.5 w-2.5 shrink-0 rounded-full", RISK_DOT_CLASSES[clause.risk])}
          aria-hidden="true"
        />
        <span className="sr-only">{t(`contract.result.riskLevel.${clause.risk}`)}</span>
        <span>{t(`contract.category.${clause.category}`)}</span>
        <span aria-hidden="true">·</span>
        <span>{meta}</span>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
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
    </li>
  );
}

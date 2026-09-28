import { useState } from "react";

import ReportCard from "@/components/contract/ReportCard";
import ReportLanguageSwitcher from "@/components/contract/ReportLanguageSwitcher";
import ReportSkeleton from "@/components/contract/ReportSkeleton";
import { Button } from "@/components/ui/button";
import { useContractReport } from "@/hooks/useContract";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import type { ContractAnalysis } from "@/types/contract";
import type { LanguageCode } from "@/types/enums";
import { reportFailureKey } from "@/utils/reportLanguage";

export interface ReportViewProps {
  /** Score, risk level and the languages already stored (`POST .../analyze`). */
  analysis: ContractAnalysis;
}

const errorBoxClass =
  "flex flex-col items-center gap-4 rounded-lg border border-destructive/30 bg-destructive/10 p-6 text-center";

/**
 * The finished report with its language switcher (NF-P2-011, NF-P2-012). The chosen language
 * lives here, so it starts again from the analysis' language for the next contract.
 */
export default function ReportView({ analysis }: ReportViewProps) {
  const { t } = useI18n();
  // Null until the worker switches: the report then shows in the language it was analysed in.
  const [chosen, setChosen] = useState<LanguageCode | null>(null);
  const language = chosen ?? analysis.report_language;
  const report = useContractReport(analysis.contract_id, language, analysis.report_languages);
  const failureKey = report.isError ? reportFailureKey(report.error) : null;

  return (
    <div className="space-y-6">
      <ReportLanguageSwitcher value={language} onChange={setChosen} disabled={report.isFetching} />

      {report.isPending && <ReportSkeleton />}

      {failureKey !== null && (
        <div role="alert" className={errorBoxClass}>
          <p className="text-sm text-destructive">{t(failureKey)}</p>
          {/* Trying again cannot help an out-of-date analysis: the contract must be checked again. */}
          {failureKey !== "contract.report.switchOutOfDate" && (
            <Button onClick={() => void report.refetch()}>{t("common.retry")}</Button>
          )}
        </div>
      )}

      {report.isSuccess && report.data === null && (
        <div role="alert" className={errorBoxClass}>
          <p className="text-sm text-destructive">{t("contract.result.reportMissing")}</p>
          <Button onClick={() => void report.refetch()}>{t("common.retry")}</Button>
        </div>
      )}

      {report.isPlaceholderData && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("contract.report.switching")}
        </p>
      )}

      {report.data && (
        // `lang` so a screen reader speaks the report in its own language, not the app's.
        <div
          lang={language}
          aria-busy={report.isPlaceholderData}
          className={cn(report.isPlaceholderData && "opacity-60")}
        >
          <ReportCard analysis={analysis} report={report.data} />
        </div>
      )}
    </div>
  );
}

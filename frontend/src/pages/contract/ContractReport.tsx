import { ArrowLeft, ShieldCheck } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import PageHeader from "@/components/common/PageHeader";
import PageStateFrame from "@/components/common/PageStateFrame";
import ReportView from "@/components/contract/ReportView";
import { Button } from "@/components/ui/button";
import { useRecheckForCountry, useStoredContract } from "@/hooks/useContract";
import { useI18n } from "@/hooks/useI18n";
import { useUserProfile } from "@/hooks/useUser";
import { isLanguageCode, type LanguageCode } from "@/types/enums";
import { analysisFromDoc } from "@/utils/pipelineProgress";

/**
 * A past contract's report, reopened from the history (`/contract/:contractId`). Built from the
 * stored contract document, like the page that ran the check, so the same report card shows:
 * in the worker's language when that report is stored, else the first stored one.
 */
export default function ContractReport() {
  const { t } = useI18n();
  const { contractId = "" } = useParams();
  const contract = useStoredContract(contractId);
  const profile = useUserProfile();
  const recheck = useRecheckForCountry();

  if (contract.isPending || profile.isPending) {
    return (
      <PageStateFrame pillar="contract" icon={ShieldCheck} title={t("contract.result.title")}>
        <LoadingSpinner label={t("common.loading")} className="py-16" />
      </PageStateFrame>
    );
  }
  if (contract.isError) {
    return (
      <PageStateFrame pillar="contract" icon={ShieldCheck} title={t("contract.result.title")}>
        <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-sm text-muted-foreground">{t("contract.history.loadError")}</p>
          <Button onClick={() => void contract.refetch()}>{t("common.retry")}</Button>
        </div>
      </PageStateFrame>
    );
  }

  const stored = contract.data;
  const preferred = profile.data?.preferred_language;
  const languages = stored?.report_languages ?? [];
  const language: LanguageCode =
    isLanguageCode(preferred) && languages.includes(preferred) ? preferred : (languages[0] ?? "en");
  const analysis = stored ? analysisFromDoc(contractId, stored, language) : null;

  return (
    <div className="space-y-5">
      <PageHeader
        pillar="contract"
        icon={ShieldCheck}
        title={stored?.title ?? t("contract.result.title")}
        compact
        actions={
          <Button asChild variant="outline" className="h-11 rounded-xl bg-card font-bold">
            <Link to="/contract/history">
              <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" />
              {t("contract.history.back")}
            </Link>
          </Button>
        }
      />

      {analysis ? (
        <ReportView
          analysis={analysis}
          onRecheck={(country) => recheck.mutate({ analysis, country })}
          rechecking={recheck.isPending}
          recheckFailed={recheck.isError}
        />
      ) : (
        <div role="alert" className="flex flex-col items-center gap-4 py-12 text-center">
          <p className="text-sm text-muted-foreground">
            {stored ? t("contract.history.notFinished") : t("contract.history.notFound")}
          </p>
          <Button asChild>
            <Link to="/contract">{t("contract.history.checkNew")}</Link>
          </Button>
        </div>
      )}
    </div>
  );
}

import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import PipelineProgress from "@/components/contract/PipelineProgress";
import ReportSkeleton from "@/components/contract/ReportSkeleton";
import ReportView from "@/components/contract/ReportView";
import UploadDropzone from "@/components/contract/UploadDropzone";
import { Button } from "@/components/ui/button";
import {
  useContractProgress,
  useRetryAnalysis,
  useUploadAndAnalyzeContract,
} from "@/hooks/useContract";
import { useI18n } from "@/hooks/useI18n";
import { useUserProfile } from "@/hooks/useUser";
import { trackContractAnalyzed } from "@/lib/analytics";
import i18n from "@/lib/i18n";
import { SUPPORTED_LANGUAGES } from "@/lib/languages";
import type { AnalyzeRequest } from "@/types/contract";
import { countryName } from "@/utils/format";
import {
  analysisFromDoc,
  canRetry,
  failureMessageKey,
  type Phase,
  progressView,
  requestFailureKey,
} from "@/utils/pipelineProgress";
import { HOST_COUNTRIES, type HostCountry, isLanguageCode, type LanguageCode } from "@/types/enums";

const fieldClass =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base shadow-sm " +
  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50";

export default function ContractUpload() {
  const { t } = useI18n();
  const profile = useUserProfile();
  const upload = useUploadAndAnalyzeContract();
  const retry = useRetryAnalysis();
  // The choices the running or failed check was started with, reused by "Try again".
  const [submitted, setSubmitted] = useState<AnalyzeRequest | null>(null);
  // A new progress card for each run, so nothing (a step's stall hint) carries over from the last.
  const [attempt, setAttempt] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [hostCountry, setHostCountry] = useState<HostCountry | null>(null);
  const [reportLanguage, setReportLanguage] = useState<LanguageCode | null>(null);
  const [poorLegibility, setPoorLegibility] = useState(false);
  const contractId = upload.contractId;
  const working = upload.isPending || retry.isPending;
  // The analysis stopped after the upload: the steps show where, with a way to try again.
  const stopped = !working && contractId !== null && (upload.isError || retry.isError);
  const progress = useContractProgress(working || stopped ? contractId : null);
  // The attempt the backend was seen analysing. Until then a `completed` document is the last
  // check of the same file (a re-upload reuses the contract), not this run's answer.
  const [seenAttempt, setSeenAttempt] = useState<number | null>(null);
  if (progress?.status === "processing" && seenAttempt !== attempt) {
    setSeenAttempt(attempt);
  }
  const seenThisRun = seenAttempt === attempt;
  const effectiveReportLanguage =
    reportLanguage ??
    (isLanguageCode(profile.data?.preferred_language) ? profile.data.preferred_language : "en");
  const result =
    retry.data ??
    upload.data?.analysis ??
    // The server finished but the phone lost the answer (mobile data): read it from the document.
    (contractId !== null && progress !== null && seenThisRun
      ? analysisFromDoc(contractId, progress, effectiveReportLanguage)
      : null);

  if (profile.isPending) {
    return <LoadingSpinner label={t("common.loading")} className="py-16" />;
  }
  if (profile.isError) {
    return (
      <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
        <p className="text-sm text-muted-foreground">{t("contract.upload.profileLoadError")}</p>
        <Button onClick={() => void profile.refetch()}>{t("common.retry")}</Button>
      </div>
    );
  }

  const language = i18n.resolvedLanguage ?? "en";
  const effectiveHostCountry = hostCountry ?? profile.data?.host_country ?? HOST_COUNTRIES[0];

  function resetForAnotherContract() {
    setFile(null);
    setPoorLegibility(false);
    setSubmitted(null);
    upload.reset();
    retry.reset();
  }

  function retryAnalysis() {
    if (contractId === null || submitted === null) {
      return;
    }
    setAttempt((count) => count + 1);
    retry.mutate(
      { contractId, choices: submitted },
      { onSuccess: (analysis) => trackContractAnalyzed(analysis.host_country) }
    );
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file || upload.isPending) {
      return;
    }
    setPoorLegibility(false);
    const choices = {
      host_country: effectiveHostCountry,
      report_language: effectiveReportLanguage,
    };
    setSubmitted(choices);
    setAttempt((count) => count + 1);
    retry.reset();
    upload.mutate(
      { file, choices },
      {
        onSuccess: (result) => {
          if (result.analysis === null) {
            setPoorLegibility(true);
            setFile(null);
            return;
          }
          trackContractAnalyzed(result.analysis.host_country);
        },
      }
    );
  }

  if (result) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <header className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">{t("contract.result.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("contract.result.subtitle")}</p>
        </header>

        <ReportView analysis={result} />

        <Button className="h-11 w-full" variant="outline" onClick={resetForAnotherContract}>
          {t("contract.result.analyzeAnother")}
        </Button>
      </div>
    );
  }

  if (working || stopped) {
    const phase: Phase = working ? (contractId === null ? "uploading" : "analyzing") : "failed";
    const view = progressView(phase, progress, seenThisRun);
    const failureKey = stopped
      ? view.failedCode
        ? failureMessageKey(view.failedCode)
        : requestFailureKey(retry.error ?? upload.error)
      : null;
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <header className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">{t("contract.upload.title")}</h1>
        </header>
        <PipelineProgress
          key={attempt}
          states={view.states}
          current={view.current}
          failureKey={failureKey}
          actions={
            <>
              {canRetry(view.failedCode) && (
                <Button onClick={retryAnalysis}>{t("common.retry")}</Button>
              )}
              <Button variant="outline" onClick={resetForAnotherContract}>
                {t("contract.result.analyzeAnother")}
              </Button>
            </>
          }
        />
        {working && <ReportSkeleton />}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <header className="space-y-1">
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-2xl font-bold tracking-tight">{t("contract.upload.title")}</h1>
          <Link to="/contract/history" className="shrink-0 pt-2 text-sm underline">
            {t("contract.history.link")}
          </Link>
        </div>
        <p className="text-sm text-muted-foreground">{t("contract.upload.subtitle")}</p>
      </header>

      {poorLegibility && (
        <p
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
        >
          {t("contract.upload.poorLegibility")}
        </p>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <UploadDropzone
          file={file}
          onSelect={setFile}
          onClear={() => setFile(null)}
          disabled={upload.isPending}
        />

        <div className="space-y-1.5">
          <label htmlFor="contract-host-country" className="text-sm font-medium">
            {t("contract.upload.hostCountry")}
          </label>
          <select
            id="contract-host-country"
            value={effectiveHostCountry}
            onChange={(event) => setHostCountry(event.target.value as HostCountry)}
            aria-describedby="contract-host-country-hint"
            disabled={upload.isPending}
            className={fieldClass}
          >
            {HOST_COUNTRIES.map((code) => (
              <option key={code} value={code}>
                {countryName(code, language)}
              </option>
            ))}
          </select>
          <p id="contract-host-country-hint" className="text-xs text-muted-foreground">
            {t("contract.upload.hostCountryHint")}
          </p>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="contract-report-language" className="text-sm font-medium">
            {t("contract.upload.reportLanguage")}
          </label>
          <select
            id="contract-report-language"
            value={effectiveReportLanguage}
            onChange={(event) => setReportLanguage(event.target.value as LanguageCode)}
            disabled={upload.isPending}
            className={fieldClass}
          >
            {SUPPORTED_LANGUAGES.map(({ code, nativeName }) => (
              <option key={code} value={code}>
                {nativeName}
              </option>
            ))}
          </select>
        </div>

        {upload.isError && (
          <p role="alert" className="text-sm text-destructive">
            {t(requestFailureKey(upload.error))}
          </p>
        )}

        <Button
          type="submit"
          size="lg"
          className="h-11 w-full"
          disabled={!file || upload.isPending}
        >
          {upload.isPending ? t("contract.upload.submitting") : t("contract.upload.submit")}
        </Button>
      </form>
    </div>
  );
}

import { History, ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import PageHeader from "@/components/common/PageHeader";
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
  "h-12 w-full rounded-xl border border-input bg-card px-3 text-base font-semibold shadow-sm " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50";

const NEXT_STEPS = ["upload", "read", "law", "report", "letter"] as const;

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
      <div className="space-y-5">
        <PageHeader
          pillar="contract"
          icon={ShieldCheck}
          title={t("contract.result.title")}
          description={t("contract.result.subtitle")}
          compact
        />

        <ReportView analysis={result} />

        <Button
          className="h-12 w-full rounded-xl font-bold"
          variant="outline"
          onClick={resetForAnotherContract}
        >
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
      <div className="space-y-5">
        <PageHeader
          pillar="contract"
          icon={ShieldCheck}
          title={t("contract.upload.title")}
          compact
        />
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
    <div className="space-y-5">
      <PageHeader
        pillar="contract"
        icon={ShieldCheck}
        title={t("contract.upload.title")}
        description={t("contract.upload.subtitle")}
        actions={
          <Button asChild variant="outline" className="h-11 rounded-xl bg-card font-bold">
            <Link to="/contract/history">
              <History className="mr-2 h-4 w-4" aria-hidden="true" />
              {t("contract.history.link")}
            </Link>
          </Button>
        }
      />

      {poorLegibility && (
        <p
          role="alert"
          className="rounded-xl border border-danger/30 bg-danger-tint p-4 text-sm font-medium text-danger-tint-ink"
        >
          {t("contract.upload.poorLegibility")}
        </p>
      )}

      <div className="grid items-start gap-5 lg:grid-cols-12">
        <form onSubmit={handleSubmit} className="card-surface space-y-6 p-5 md:p-6 lg:col-span-7">
          <UploadDropzone
            file={file}
            onSelect={setFile}
            onClear={() => setFile(null)}
            disabled={upload.isPending}
          />

          <div className="space-y-1.5">
            <label htmlFor="contract-host-country" className="text-sm font-bold">
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
            <label htmlFor="contract-report-language" className="text-sm font-bold">
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
            <p role="alert" className="text-sm font-medium text-destructive">
              {t(requestFailureKey(upload.error))}
            </p>
          )}

          <Button
            type="submit"
            size="lg"
            className="h-12 w-full rounded-xl bg-contract-deep text-base font-bold text-white hover:bg-contract-deep/90"
            disabled={!file || upload.isPending}
          >
            {upload.isPending ? t("contract.upload.submitting") : t("contract.upload.submit")}
          </Button>
        </form>

        <aside className="card-surface bg-gradient-to-br from-contract-tint via-card to-card p-5 md:p-6 lg:col-span-5">
          <h2 className="text-base font-bold tracking-tight">{t("contract.upload.nextHeading")}</h2>
          <ol className="mt-4 space-y-3">
            {NEXT_STEPS.map((step, index) => (
              <li key={step} className="flex items-start gap-3">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-contract text-xs font-extrabold text-white">
                  {index + 1}
                </span>
                <span className="pt-0.5 text-sm font-medium">
                  {t(`landing.how.steps.${step}.title`)}
                </span>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </div>
  );
}

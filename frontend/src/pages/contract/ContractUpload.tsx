import { type FormEvent, useState } from "react";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import UploadDropzone from "@/components/contract/UploadDropzone";
import { Button } from "@/components/ui/button";
import { useUploadAndAnalyzeContract } from "@/hooks/useContract";
import { useI18n } from "@/hooks/useI18n";
import { useUserProfile } from "@/hooks/useUser";
import { trackContractAnalyzed } from "@/lib/analytics";
import i18n from "@/lib/i18n";
import { SUPPORTED_LANGUAGES } from "@/lib/languages";
import { cn } from "@/lib/utils";
import { errorMessageKey } from "@/utils/errors";
import { countryName } from "@/utils/format";
import { HOST_COUNTRIES, type HostCountry, isLanguageCode, type LanguageCode } from "@/types/enums";

const fieldClass =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base shadow-sm " +
  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50";

const RISK_STYLES: Record<string, string> = {
  safe: "border-green-600/30 bg-green-600/10 text-green-700 dark:text-green-400",
  caution: "border-yellow-600/30 bg-yellow-600/10 text-yellow-700 dark:text-yellow-400",
  danger: "border-red-600/30 bg-red-600/10 text-red-700 dark:text-red-400",
};

export default function ContractUpload() {
  const { t } = useI18n();
  const profile = useUserProfile();
  const upload = useUploadAndAnalyzeContract();
  const [file, setFile] = useState<File | null>(null);
  const [hostCountry, setHostCountry] = useState<HostCountry | null>(null);
  const [reportLanguage, setReportLanguage] = useState<LanguageCode | null>(null);
  const [poorLegibility, setPoorLegibility] = useState(false);

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
  const effectiveReportLanguage =
    reportLanguage ??
    (isLanguageCode(profile.data?.preferred_language) ? profile.data.preferred_language : "en");

  function resetForAnotherContract() {
    setFile(null);
    setPoorLegibility(false);
    upload.reset();
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file || upload.isPending) {
      return;
    }
    setPoorLegibility(false);
    upload.mutate(
      {
        file,
        choices: { host_country: effectiveHostCountry, report_language: effectiveReportLanguage },
      },
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

  const result = upload.data?.analysis ?? null;

  if (result) {
    return (
      <div className="mx-auto max-w-lg space-y-6">
        <header className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">{t("contract.result.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("contract.result.subtitle")}</p>
        </header>

        <div className="space-y-4 rounded-lg border bg-card p-6">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">
              {t("contract.result.score")}
            </span>
            <span className="text-3xl font-bold tabular-nums">{result.health_score}</span>
          </div>
          <div
            className={cn(
              "inline-flex items-center rounded-full border px-3 py-1 text-sm font-medium",
              RISK_STYLES[result.risk_level]
            )}
          >
            {t(`contract.result.riskLevel.${result.risk_level}`)}
          </div>
          <dl className="grid grid-cols-3 gap-2 text-center text-sm">
            <div>
              <dt className="text-muted-foreground">{t("contract.result.counts.safe")}</dt>
              <dd className="text-lg font-semibold">{result.clause_counts.safe}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t("contract.result.counts.caution")}</dt>
              <dd className="text-lg font-semibold">{result.clause_counts.caution}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t("contract.result.counts.danger")}</dt>
              <dd className="text-lg font-semibold">{result.clause_counts.danger}</dd>
            </div>
          </dl>
          {result.complaint_pending && (
            <p className="text-sm text-muted-foreground">{t("contract.result.complaintPending")}</p>
          )}
        </div>

        <Button className="h-11 w-full" variant="outline" onClick={resetForAnotherContract}>
          {t("contract.result.analyzeAnother")}
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">{t("contract.upload.title")}</h1>
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

        {upload.isPending && (
          <LoadingSpinner label={t("contract.upload.analyzing")} className="py-2" />
        )}

        {upload.isError && (
          <p role="alert" className="text-sm text-destructive">
            {t(errorMessageKey(upload.error))}
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

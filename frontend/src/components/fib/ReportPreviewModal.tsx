import { X } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { METRIC_KEYS, type FinancialProfile, type MetricKey, type MetricResult } from "@/types/fib";
import { savingsRatePct, STATUS_COLOR, statusFor } from "@/utils/fibScore";
import { formatMoney } from "@/utils/format";

export interface ReportPreviewModalProps {
  profile: FinancialProfile;
  /** The name typed into the export form, if any — mirrors what the next PDF will print. */
  holderName: string | null;
  onClose: () => void;
}

function formatDate(isoDate: string, language: string): string {
  try {
    return new Intl.DateTimeFormat(language, { dateStyle: "medium" }).format(new Date(isoDate));
  } catch {
    return isoDate;
  }
}

function PreviewMetricBar({ metricKey, result }: { metricKey: MetricKey; result: MetricResult }) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const label = t(`fib.score.metrics.${metricKey}`);

  if (result.score === null) {
    return (
      <div className="flex items-center justify-between gap-2 text-sm">
        <span>{label}</span>
        <span className="text-muted-foreground">{t("fib.export.preview.notEnoughRecords")}</span>
      </div>
    );
  }

  const status = statusFor(result.score);
  const pct = metricKey === "savings_rate" ? savingsRatePct(result.detail, language) : null;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span>{label}</span>
        <span className="tabular-nums">{pct ?? result.score}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full"
          style={{ width: `${result.score}%`, backgroundColor: STATUS_COLOR[status] }}
        />
      </div>
    </div>
  );
}

/**
 * What the PDF a lender sees actually contains (NF-P3-014's own content decision), rendered
 * from live profile data rather than the PDF's bytes — `download_url` always downloads
 * (`Content-Disposition: attachment`, no bucket CORS), so there is no reliable way to show the
 * real file inline. Deliberately omits the overall score: the real PDF never prints it either
 * ("could be read as a credit score").
 */
export default function ReportPreviewModal({
  profile,
  holderName,
  onClose,
}: ReportPreviewModalProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    panelRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKey);
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="report-preview-title"
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
        className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-2xl border bg-card p-6 shadow-lg focus:outline-none"
      >
        <div className="flex items-start justify-between gap-3">
          <h2 id="report-preview-title" className="text-lg font-bold tracking-tight">
            {t("fib.export.preview.title")}
          </h2>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label={t("fib.export.preview.close")}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>

        <div className="mt-4 space-y-4 text-sm">
          {holderName && <p className="font-medium">{holderName}</p>}

          <dl className="grid grid-cols-2 gap-3">
            <div>
              <dt className="text-xs text-muted-foreground">{t("fib.export.preview.period")}</dt>
              <dd>
                {formatDate(profile.period_start, language)} –{" "}
                {formatDate(profile.period_end, language)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">
                {t("fib.export.preview.monthsOfData")}
              </dt>
              <dd>{profile.months_of_data}</dd>
            </div>
          </dl>

          <div className="space-y-3 border-t pt-4">
            {METRIC_KEYS.map((key) => (
              <PreviewMetricBar key={key} metricKey={key} result={profile.metrics[key]} />
            ))}
          </div>

          {profile.verified_employment && profile.verified_employment.length > 0 && (
            <div className="space-y-2 border-t pt-4">
              <p className="text-xs font-medium text-muted-foreground">
                {t("fib.export.preview.verifiedEmployment")}
              </p>
              <ul className="space-y-1">
                {profile.verified_employment.map((job, index) => (
                  <li key={`${job.employer_name}-${index}`} className="flex justify-between gap-2">
                    <span>{job.employer_name}</span>
                    <span className="tabular-nums">
                      {formatMoney(job.salary_amount, job.salary_currency, language)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {profile.narrative.text && (
            <p className="border-t pt-4 leading-relaxed text-muted-foreground">
              {profile.narrative.text}
            </p>
          )}

          <p className="border-t pt-4 text-xs text-muted-foreground">
            {t("fib.export.preview.disclaimer")}
          </p>
        </div>
      </div>
    </div>
  );
}

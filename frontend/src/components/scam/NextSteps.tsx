import { useId } from "react";

import { useI18n } from "@/hooks/useI18n";

export interface NextStepsProps {
  steps: readonly string[];
  /** The language the steps are written in, so a screen reader pronounces them right. */
  language: string;
}

/** What to do now, as a numbered list. The number is drawn large for a worker who scans rather
 * than reads, and spoken to a screen reader as "Step 1" (the drawn digit is hidden from it, since
 * a list that has lost its default numbering would not say it). */
export default function NextSteps({ steps, language }: NextStepsProps) {
  const { t } = useI18n("scam");
  const titleId = useId();

  return (
    <section aria-labelledby={titleId} className="card-surface space-y-3 p-4 sm:p-5">
      <h2 id={titleId} className="text-lg font-extrabold">
        {t("result.nextSteps")}
      </h2>
      <ol role="list" className="space-y-3">
        {steps.map((step, index) => (
          <li key={`${index}-${step}`} className="flex items-start gap-3">
            <span
              aria-hidden="true"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-radar-tint text-base font-extrabold text-radar-ink"
            >
              {index + 1}
            </span>
            <span className="sr-only">{t("result.stepLabel", { number: index + 1 })}.</span>
            <p lang={language} className="pt-0.5 text-base leading-7">
              {step}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}

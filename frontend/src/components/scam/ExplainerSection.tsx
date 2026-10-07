import { useId, useMemo } from "react";
import { useTranslation } from "react-i18next";

import NextSteps from "@/components/scam/NextSteps";
import ReadAloudButton from "@/components/scam/ReadAloudButton";
import { useI18n } from "@/hooks/useI18n";
import type { ScamExplainer } from "@/types/scam";
import { explainerSpeech } from "@/utils/explainerSpeech";

export interface ExplainerSectionProps {
  explainer: ScamExplainer | null;
}

/** The explanation under the verdict card: why the message works on people, what the sender wants,
 * and what to do now as numbered steps (a scam), or the reassurance and the tip (not a scam). A
 * read-aloud button above them speaks it all for a worker who finds reading hard. When the
 * explanation could not be written the card still has its verdict; this says so. */
export default function ExplainerSection({ explainer }: ExplainerSectionProps) {
  const { t } = useI18n("scam");
  const { i18n } = useTranslation();
  const whyId = useId();

  // The explainer is written in the language the check was sent in, which is the UI language
  // unless the worker switched it while looking at the result. Headings are spoken only when they
  // match, so the voice never reads a heading in a language it was not chosen for.
  const parts = useMemo(() => {
    if (explainer === null) {
      return [];
    }
    const sameLanguage = i18n.resolvedLanguage === explainer.language;
    return explainerSpeech(
      explainer,
      sameLanguage
        ? {
            why: t("result.whyTitle"),
            wants: t("result.scammerWants"),
            steps: t("result.nextSteps"),
            step: (number) => t("result.stepLabel", { number }),
          }
        : undefined
    );
  }, [explainer, i18n.resolvedLanguage, t]);

  if (explainer === null) {
    return (
      <p className="card-surface p-4 text-sm text-muted-foreground">
        {t("result.explainerUnavailable")}
      </p>
    );
  }

  if (explainer.kind === "benign") {
    return (
      <div className="space-y-4">
        <ReadAloudButton language={explainer.language} parts={parts} />
        <section aria-labelledby={whyId} className="card-surface space-y-3 p-4 sm:p-5">
          <h2 id={whyId} className="text-lg font-extrabold">
            {t("result.benignTitle")}
          </h2>
          <p lang={explainer.language} className="text-base leading-7">
            {explainer.reassurance}
          </p>
          <p lang={explainer.language} className="text-sm leading-6 text-muted-foreground">
            {explainer.tip}
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <ReadAloudButton language={explainer.language} parts={parts} />
      <section aria-labelledby={whyId} className="card-surface space-y-4 p-4 sm:p-5">
        <h2 id={whyId} className="text-lg font-extrabold">
          {t("result.whyTitle")}
        </h2>
        {explainer.why_it_works.length > 0 && (
          <ul role="list" className="space-y-3">
            {explainer.why_it_works.map((item) => (
              <li key={item.tactic}>
                <strong className="block text-sm">
                  {t(`result.tactic.${item.tactic}.label`, {
                    defaultValue: item.tactic.replaceAll("_", " "),
                  })}
                </strong>
                <p lang={explainer.language} className="text-base leading-7">
                  {item.text}
                </p>
              </li>
            ))}
          </ul>
        )}
        <div className="space-y-1 rounded-xl bg-muted/60 p-3">
          <h3 className="text-sm font-extrabold">{t("result.scammerWants")}</h3>
          <p lang={explainer.language} className="text-base leading-7">
            {explainer.scammer_wants}
          </p>
        </div>
      </section>
      <NextSteps steps={explainer.next_steps} language={explainer.language} />
    </div>
  );
}

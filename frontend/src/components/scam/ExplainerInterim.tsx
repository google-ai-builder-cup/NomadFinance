import { useI18n } from "@/hooks/useI18n";
import type { ScamExplainer } from "@/types/scam";

export interface ExplainerInterimProps {
  explainer: ScamExplainer | null;
}

// The explanation under the verdict card: what the sender wants and what to do now (a scam), or the
// reassurance and the tip (not a scam). A plain version so a worker never loses their next steps;
// NF-SA-017 replaces it with the "why this is a scam" section, numbered steps and read-aloud.
export default function ExplainerInterim({ explainer }: ExplainerInterimProps) {
  const { t } = useI18n("scam");

  if (explainer === null) {
    return (
      <p className="card-surface p-4 text-sm text-muted-foreground">
        {t("result.explainerUnavailable")}
      </p>
    );
  }
  if (explainer.kind === "benign") {
    return (
      <div className="card-surface space-y-2 p-4 text-sm">
        <p>{explainer.reassurance}</p>
        <p className="text-muted-foreground">{explainer.tip}</p>
      </div>
    );
  }
  return (
    <div className="card-surface space-y-3 p-4 text-sm">
      <div>
        <h3 className="font-bold">{t("result.scammerWants")}</h3>
        <p>{explainer.scammer_wants}</p>
      </div>
      <div>
        <h3 className="font-bold">{t("result.nextSteps")}</h3>
        <ul className="list-disc space-y-1 pl-5">
          {explainer.next_steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

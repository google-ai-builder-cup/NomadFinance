import { Button } from "@/components/ui/button";
import RiskBadge from "@/components/common/RiskBadge";
import { useI18n } from "@/hooks/useI18n";
import type { ScamAnalyzeResponse } from "@/types/scam";
import { riskLevelForSeverity } from "@/utils/risk";

export interface InterimResultProps {
  result: ScamAnalyzeResponse;
  onCheckAnother: () => void;
}

// The plain answer that makes the check usable end to end. The full verdict card (risk meter,
// highlighted phrases, indicators, report button) is NF-SA-016 and replaces this component.
export default function InterimResult({ result, onCheckAnother }: InterimResultProps) {
  const { t } = useI18n("scam");
  const { verdict, explainer } = result;

  return (
    <section aria-labelledby="scam-result-title" className="card-surface space-y-4 p-5">
      <div className="space-y-2">
        <RiskBadge level={verdict.is_scam ? riskLevelForSeverity(verdict.risk_level) : "safe"}>
          {verdict.is_scam ? t(`result.risk.${verdict.risk_level}`) : t("result.notScam")}
        </RiskBadge>
        <h2 id="scam-result-title" className="text-lg font-extrabold">
          {verdict.is_scam ? t("result.scamTitle") : t("result.notScamTitle")}
        </h2>
        {result.cached && <p className="text-xs text-muted-foreground">{t("result.cached")}</p>}
      </div>

      {explainer?.kind === "scam" && (
        <div className="space-y-3 text-sm">
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
      )}
      {explainer?.kind === "benign" && (
        <div className="space-y-3 text-sm">
          <p>{explainer.reassurance}</p>
          <p className="text-muted-foreground">{explainer.tip}</p>
        </div>
      )}
      {explainer === null && (
        <p className="text-sm text-muted-foreground">{t("result.explainerUnavailable")}</p>
      )}

      <Button type="button" variant="outline" onClick={onCheckAnother}>
        {t("result.checkAnother")}
      </Button>
    </section>
  );
}

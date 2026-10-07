import ExplainerInterim from "@/components/scam/ExplainerInterim";
import VerdictCard from "@/components/scam/VerdictCard";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import type { ScamAnalyzeResponse } from "@/types/scam";

export interface ScamResultProps {
  result: ScamAnalyzeResponse;
  onCheckAnother: () => void;
}

/** What a worker sees after a check: the verdict card, the explanation under it, and a way to
 * check another message. The report to Radar and the history are NF-SA-018's. */
export default function ScamResult({ result, onCheckAnother }: ScamResultProps) {
  const { t } = useI18n("scam");

  return (
    <div className="space-y-4">
      <VerdictCard result={result} />
      <ExplainerInterim explainer={result.explainer} />
      <Button type="button" variant="outline" className="min-h-11 w-full" onClick={onCheckAnother}>
        {t("result.checkAnother")}
      </Button>
    </div>
  );
}

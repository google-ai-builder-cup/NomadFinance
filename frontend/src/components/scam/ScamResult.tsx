import ExplainerSection from "@/components/scam/ExplainerSection";
import ReportButton from "@/components/scam/ReportButton";
import VerdictCard from "@/components/scam/VerdictCard";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import type { ScamResultView } from "@/types/scam";

export interface ScamResultProps {
  result: ScamResultView;
  /** Omitted when the page has its own way on (a stored check opened from the history). */
  onCheckAnother?: () => void;
  /** Move focus to the verdict when it appears: for a check that has just finished. */
  focusOnMount?: boolean;
}

/** What a worker sees for a check, fresh or stored: the verdict card, the explanation under it,
 * "Warn other workers" for a scam, and a way to check another message. */
export default function ScamResult({ result, onCheckAnother, focusOnMount }: ScamResultProps) {
  const { t } = useI18n("scam");

  return (
    <div className="space-y-4">
      <VerdictCard result={result} focusOnMount={focusOnMount} />
      <ExplainerSection explainer={result.explainer} />
      <ReportButton result={result} />
      {onCheckAnother && (
        <Button
          type="button"
          variant="outline"
          className="min-h-11 w-full"
          onClick={onCheckAnother}
        >
          {t("result.checkAnother")}
        </Button>
      )}
    </div>
  );
}

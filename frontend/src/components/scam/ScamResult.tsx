import { useEffect } from "react";

import ExplainerSection from "@/components/scam/ExplainerSection";
import ReportButton from "@/components/scam/ReportButton";
import VerdictCard from "@/components/scam/VerdictCard";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { trackScamVerdictViewed } from "@/lib/analytics";
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
  const { id, cached, verdict } = result;

  // Once for each check put on the screen. A check that has just finished is the one that gets
  // focus; a stored one opened from the history does not.
  useEffect(() => {
    trackScamVerdictViewed({
      isScam: verdict.is_scam,
      riskLevel: verdict.risk_level,
      scamType: verdict.scam_type,
      cached: cached === true,
      source: focusOnMount ? "check" : "history",
    });
    // The verdict of one check never changes, so its id is what a new view is.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

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

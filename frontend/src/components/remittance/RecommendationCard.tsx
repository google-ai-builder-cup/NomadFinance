import { Lightbulb } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useRecommendRemittance, useRemittanceTrends } from "@/hooks/useRemittance";
import i18n from "@/lib/i18n";
import { isLanguageCode } from "@/types/enums";
import type { RemittanceComparison } from "@/types/remittance";
import { requestFailureKey } from "@/utils/pipelineProgress";

export interface RecommendationCardProps {
  comparison: RemittanceComparison;
}

/**
 * The Gemini recommendation for this comparison, in the app's language (NF-P2-016, step 9).
 * The trend chart's default period is passed along when it is already loaded, so the advice
 * can name the best day to send; it is never fetched just for this card.
 */
export default function RecommendationCard({ comparison }: RecommendationCardProps) {
  const { t } = useI18n();
  const resolved = i18n.resolvedLanguage ?? "en";
  const language = isLanguageCode(resolved) ? resolved : "en";
  const trend = useRemittanceTrends(comparison.corridor_id, 90);
  const recommend = useRecommendRemittance();
  const advice = recommend.data;
  // A language switch after the advice was written makes it stale: offer to write it again.
  const stale = advice !== undefined && advice.target_language !== language;

  function ask() {
    recommend.mutate({ comparison, trend: trend.data ?? null, target_language: language });
  }

  return (
    <section
      aria-labelledby="remittance-advice-title"
      aria-busy={recommend.isPending}
      className="space-y-3 rounded-lg border bg-card p-6"
    >
      <h2 id="remittance-advice-title" className="flex items-center gap-2 text-lg font-semibold">
        <Lightbulb className="h-5 w-5 text-primary" aria-hidden="true" />
        {t("remittance.advice.title")}
      </h2>

      {advice && !stale ? (
        <div className="space-y-2" aria-live="polite">
          <p className="font-medium">{advice.headline}</p>
          <p className="text-sm">{advice.explanation}</p>
          {advice.timing_tip && (
            <p className="text-sm text-muted-foreground">{advice.timing_tip}</p>
          )}
          <p className="text-xs text-muted-foreground">{t("remittance.advice.disclaimer")}</p>
        </div>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">{t("remittance.advice.intro")}</p>
          {recommend.isError && (
            <p role="alert" className="text-sm text-destructive">
              {t(requestFailureKey(recommend.error))}
            </p>
          )}
          <Button onClick={ask} disabled={recommend.isPending}>
            {recommend.isPending ? t("remittance.advice.writing") : t("remittance.advice.ask")}
          </Button>
        </>
      )}
    </section>
  );
}

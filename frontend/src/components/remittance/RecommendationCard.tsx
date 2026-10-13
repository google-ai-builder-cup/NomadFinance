import { Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useRecommendRemittance, useRemittanceTrends } from "@/hooks/useRemittance";
import i18n from "@/lib/i18n";
import { isLanguageCode } from "@/types/enums";
import type { RemittanceComparison } from "@/types/remittance";
import { adviceFailureKey } from "@/utils/corridors";

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
      className="ai-border space-y-3 rounded-2xl bg-card p-5 md:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2
          id="remittance-advice-title"
          className="flex items-center gap-2 text-lg font-bold tracking-tight"
        >
          <Sparkles className="h-5 w-5 text-contract-ink" aria-hidden="true" />
          {t("remittance.advice.title")}
        </h2>
        <Badge tone="info">{t("landing.hero.chips.gemini")}</Badge>
      </div>

      {advice && !stale ? (
        <div className="space-y-2" aria-live="polite">
          <p className="text-base font-bold">{advice.headline}</p>
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
            <p role="alert" className="text-sm text-danger-ink">
              {t(adviceFailureKey(recommend.error))}
            </p>
          )}
          <Button
            onClick={ask}
            disabled={recommend.isPending}
            className="h-11 rounded-xl bg-contract-deep px-5 font-bold text-white hover:bg-contract-deep/90"
          >
            {recommend.isPending ? t("remittance.advice.writing") : t("remittance.advice.ask")}
          </Button>
        </>
      )}
    </section>
  );
}

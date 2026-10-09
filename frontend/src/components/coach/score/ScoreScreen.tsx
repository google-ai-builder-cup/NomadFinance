import { Loader2 } from "lucide-react";

import FactorBars from "@/components/coach/score/FactorBars";
import PlanButton from "@/components/coach/score/PlanButton";
import ScoreGauge from "@/components/coach/score/ScoreGauge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCoachScore } from "@/hooks/useCoachScore";
import { useI18n } from "@/hooks/useI18n";
import type { LanguageCode } from "@/types/enums";
import { coachErrorView, toFailure } from "@/utils/coachErrors";
import { isHeldByFloor } from "@/utils/coachScore";

export interface ScoreScreenProps {
  sessionId: string;
  language: LanguageCode;
}

/**
 * What the worker sees once their answers are confirmed (stage `plan`): the preparedness score as
 * a ring and a band, one card for each of the five factors with what it means and how to improve
 * it, and the button that makes the 90-day plan. The score is read from the server, which works
 * it out with the current exchange rates; when it cannot (a rate is missing) the screen says so
 * and offers to ask again.
 */
export default function ScoreScreen({ sessionId, language }: ScoreScreenProps) {
  const { t } = useI18n("coach");
  const query = useCoachScore(sessionId, true);

  if (query.isPending) {
    return (
      <div role="status" aria-busy="true" className="space-y-3">
        <span className="sr-only">{t("score.loading")}</span>
        <Skeleton className="h-44 w-full rounded-2xl" />
        <Skeleton className="h-28 w-full rounded-2xl" />
      </div>
    );
  }

  const failure = query.isError ? toFailure(query.error) : null;
  const score = query.data?.score ?? null;
  if (score === null) {
    return (
      <div role="alert" className="space-y-3 rounded-2xl border bg-card p-4">
        <p className="text-sm font-bold">{t("score.unavailable.title")}</p>
        <p className="text-sm text-muted-foreground">
          {failure ? t(coachErrorView(failure).messageKey) : t("score.unavailable.description")}
        </p>
        <Button
          type="button"
          variant="outline"
          className="min-h-11 gap-2"
          disabled={query.isFetching}
          onClick={() => void query.refetch()}
        >
          {query.isFetching && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {t("common.retry")}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <header className="space-y-1">
        <h2 className="text-lg font-extrabold">{t("score.title")}</h2>
      </header>
      <ScoreGauge score={score} />
      {isHeldByFloor(score) && (
        <p className="rounded-xl border bg-muted/50 p-3 text-sm">{t("score.floorNote")}</p>
      )}
      <FactorBars score={score} />
      <PlanButton sessionId={sessionId} language={language} />
      <p className="text-xs text-muted-foreground">{t("score.disclaimer")}</p>
    </div>
  );
}

import { CircleCheck, Loader2, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useMakeCoachPlan } from "@/hooks/useMakeCoachPlan";
import type { LanguageCode } from "@/types/enums";
import { coachErrorView, toFailure } from "@/utils/coachErrors";

// A plan takes 20 to 40 seconds: say so up front, and again if it is taking longer.
const SLOW_AFTER_MS = 15_000;

/** What is said while the plan is made. Mounted only while it runs, so the clock starts again
 * with each try. */
function PendingText({ slowAfterMs }: { slowAfterMs: number }) {
  const { t } = useI18n("coach");
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), slowAfterMs);
    return () => clearTimeout(timer);
  }, [slowAfterMs]);
  return <>{slow ? t("score.plan.slow") : t("score.plan.wait")}</>;
}

export interface PlanButtonProps {
  sessionId: string;
  language: LanguageCode;
  /** Shorter allowance, for tests. */
  timeoutMs?: number;
  slowAfterMs?: number;
}

/**
 * "Make my 90-day plan". While it runs the button waits and a status line says what is happening;
 * a failure is told in words with a way to try again (pressing again returns the same plan, never
 * a second one); on success the plan's summary is shown (the full plan view is NF-FC-021's).
 */
export default function PlanButton({
  sessionId,
  language,
  timeoutMs,
  slowAfterMs = SLOW_AFTER_MS,
}: PlanButtonProps) {
  const { t } = useI18n("coach");
  const make = useMakeCoachPlan(sessionId, language, timeoutMs);

  if (make.isSuccess) {
    return (
      <div role="status" className="space-y-2 rounded-2xl border bg-card p-4">
        <div className="flex items-center gap-2">
          <CircleCheck className="h-5 w-5 shrink-0 text-safe-ink" aria-hidden="true" />
          <p className="text-sm font-bold">{t("score.plan.readyTitle")}</p>
        </div>
        <p className="text-sm text-muted-foreground">{make.data.plan.summary}</p>
        <Button asChild className="min-h-11 w-full font-bold sm:w-auto">
          <Link to={`/coach/plan/${make.data.id}`}>{t("score.plan.view")}</Link>
        </Button>
      </div>
    );
  }

  const view = make.isError ? coachErrorView(toFailure(make.error)) : null;

  return (
    <div className="space-y-3 rounded-2xl border bg-card p-4">
      <p className="text-sm text-muted-foreground">{t("score.plan.help")}</p>
      {view && (
        <div role="alert" className="flex items-start gap-2 text-sm text-danger-ink">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>{t(view.messageKey, { seconds: view.waitSeconds })}</p>
        </div>
      )}
      <Button
        type="button"
        className="min-h-12 w-full gap-2 text-base font-bold"
        disabled={make.isPending}
        aria-busy={make.isPending}
        onClick={() => make.mutate()}
      >
        {make.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {make.isPending
          ? t("score.plan.making")
          : view?.action === "retry"
            ? t("common.retry")
            : t("score.plan.button")}
      </Button>
      <p role="status" className="min-h-0 text-xs text-muted-foreground empty:hidden">
        {make.isPending ? <PendingText slowAfterMs={slowAfterMs} /> : null}
      </p>
    </div>
  );
}

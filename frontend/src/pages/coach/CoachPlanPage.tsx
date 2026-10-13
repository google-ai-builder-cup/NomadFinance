import { GraduationCap, Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";

import Checklist from "@/components/coach/plan/Checklist";
import BudgetCards from "@/components/coach/plan/BudgetCards";
import DebtFundCards from "@/components/coach/plan/DebtFundCards";
import PdfActions from "@/components/coach/plan/PdfActions";
import PlanHeader from "@/components/coach/plan/PlanHeader";
import RemittanceCard from "@/components/coach/plan/RemittanceCard";
import WarningsPanel from "@/components/coach/plan/WarningsPanel";
import WeekTimeline from "@/components/coach/plan/WeekTimeline";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/useAuth";
import { useCoachPlan } from "@/hooks/useCoachPlan";
import { useI18n } from "@/hooks/useI18n";
import { useUiLanguage } from "@/hooks/useUiLanguage";
import { trackCoachPlanViewed } from "@/lib/analytics";
import type { CorridorId } from "@/types/enums";
import { coachErrorView, toFailure } from "@/utils/coachErrors";

function BackLink() {
  const { t } = useI18n("coach");
  return (
    <Button asChild variant="outline" className="min-h-11 gap-2">
      <Link to="/coach">
        <GraduationCap className="h-4 w-4" aria-hidden="true" />
        {t("plan.back")}
      </Link>
    </Button>
  );
}

/** The page's own heading while the plan is not there (loading, failed, missing), so every state
 * starts from the same title the plan itself does. */
function PlanTitle() {
  const { t } = useI18n("coach");
  return <h1 className="text-xl font-extrabold tracking-tight sm:text-2xl">{t("plan.title")}</h1>;
}

function PlanSkeleton({ label }: { label: string }) {
  return (
    <div role="status" aria-busy="true" className="space-y-3">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-32 w-full rounded-2xl" />
      <Skeleton className="h-24 w-full rounded-2xl" />
      <Skeleton className="h-40 w-full rounded-2xl" />
    </div>
  );
}

/** `/coach/plan/:planId`: the worker's 90-day plan in the app's language, with the PDF to download
 * or share. A language the plan is not yet stored in is translated by the server on the first
 * request, so the plan already on screen stays while it loads. */
export default function CoachPlanPage() {
  const { t } = useI18n("coach");
  const { planId = "" } = useParams();
  const language = useUiLanguage();
  const { user } = useAuth();
  const query = useCoachPlan(planId, language);

  // One "viewed" for each plan on each opening of this screen: not again when the plan is
  // translated into another language, which keeps the same plan on screen.
  const viewed = useRef<string | null>(null);
  const shown = query.data;
  useEffect(() => {
    if (shown !== undefined && viewed.current !== shown.id) {
      viewed.current = shown.id;
      trackCoachPlanViewed({
        band: shown.score.band,
        corridorId: shown.corridor_id as CorridorId | undefined,
        language: shown.language,
      });
    }
  }, [shown]);

  if (query.isPending) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-3">
        <PlanTitle />
        <PlanSkeleton label={t("plan.loading")} />
      </div>
    );
  }

  if (query.isError && query.data === undefined) {
    const failure = toFailure(query.error);
    const missing = failure.code === "not_found" || failure.status === 404;
    return (
      <div className="mx-auto w-full max-w-3xl space-y-3">
        <PlanTitle />
        <div role="alert" className="space-y-3 rounded-2xl border bg-card p-4">
          <p className="text-sm font-bold">
            {missing ? t("plan.notFound.title") : t("plan.error.title")}
          </p>
          <p className="text-sm text-muted-foreground">
            {missing ? t("plan.notFound.description") : t(coachErrorView(failure).messageKey)}
          </p>
          <div className="flex flex-wrap gap-2">
            {!missing && (
              <Button type="button" className="min-h-11" onClick={() => void query.refetch()}>
                {t("common.retry")}
              </Button>
            )}
            <BackLink />
          </div>
        </div>
      </div>
    );
  }

  const response = query.data;
  const translating = query.isPlaceholderData;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-5 pb-4">
      {translating && (
        <p
          role="status"
          className="flex items-center gap-2 rounded-xl border bg-muted/50 p-3 text-sm"
        >
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          {t("plan.translating")}
        </p>
      )}
      <div lang={response.language} className={translating ? "opacity-60" : undefined}>
        <div className="space-y-5">
          <PlanHeader plan={response} />
          <WarningsPanel plan={response.plan} />
          <BudgetCards plan={response.plan} />
          <RemittanceCard plan={response.plan} />
          <DebtFundCards plan={response.plan} />
          <WeekTimeline plan={response.plan} />
          <Checklist
            key={`${response.id}:${response.language}`}
            plan={response.plan}
            planId={response.id}
            uid={user?.uid}
          />
          <p className="text-xs text-muted-foreground">{response.plan.disclaimer}</p>
        </div>
      </div>
      <PdfActions planId={response.id} language={language} />
      <BackLink />
    </div>
  );
}

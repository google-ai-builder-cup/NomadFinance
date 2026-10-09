import { ListChecks } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import type { CoachOverview } from "@/types/coach";

/** "Your plan is ready": the way back to a plan that was made, from the Coach page, until the
 * dashboard has its own card (NF-FC-022). Shown whenever the worker has a plan, also while a new
 * interview is under way. */
export default function PlanCard({ plan }: { plan: NonNullable<CoachOverview["plan"]> }) {
  const { t } = useI18n("coach");
  return (
    <div className="flex shrink-0 items-center gap-3 rounded-2xl border bg-card p-3">
      <ListChecks className="h-5 w-5 shrink-0 text-safe-ink" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-bold">{t("home.plan.title")}</p>
        <p className="text-xs text-muted-foreground">
          {t("home.plan.description", { total: plan.score_total })}
        </p>
      </div>
      <Button asChild size="sm" className="min-h-11 shrink-0 font-bold">
        <Link to={`/coach/plan/${plan.id}`}>{t("home.plan.open")}</Link>
      </Button>
    </div>
  );
}

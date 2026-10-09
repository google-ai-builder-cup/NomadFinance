import { ClipboardCheck } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import CheckinSheet from "@/components/coach/checkin/CheckinSheet";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { milestoneDays, milestoneFromParam } from "@/utils/coachCheckin";
import { PILLAR_STYLES } from "@/utils/pillars";

/** `/coach/checkin/:planId?m=30`: the three questions a reminder asks on day 30, 60 or 90 after
 * the worker left. The link is the reminder's own (`checkin_job.py`), so a tap on the push, on the
 * feed item or on the toast lands here. */
export default function CoachCheckinPage() {
  const { t } = useI18n("coach");
  const { planId = "" } = useParams();
  const [params] = useSearchParams();
  const milestone = milestoneFromParam(params.get("m"));
  const usable = milestone !== null && planId !== "";

  return (
    <div className="mx-auto w-full max-w-md space-y-4">
      <header className="flex items-center gap-3">
        <span
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl shadow-sm",
            PILLAR_STYLES.coach.tile
          )}
        >
          <ClipboardCheck className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h1 className="text-xl font-extrabold tracking-tight">
            {usable
              ? t("checkin.title", { days: milestoneDays(milestone) })
              : t("checkin.invalid.title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {usable ? t("checkin.description") : t("checkin.invalid.description")}
          </p>
        </div>
      </header>

      <section className="card-surface p-5">
        {usable ? (
          // A different plan or milestone is a different check-in: start its questions again.
          <CheckinSheet key={`${planId}:${milestone}`} planId={planId} milestone={milestone} />
        ) : (
          <Button asChild className="min-h-11 font-bold">
            <Link to="/coach">{t("checkin.invalid.open")}</Link>
          </Button>
        )}
      </section>
    </div>
  );
}

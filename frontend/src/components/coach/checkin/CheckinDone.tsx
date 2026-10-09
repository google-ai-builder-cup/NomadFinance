import { CircleCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useFocusOnMount } from "@/hooks/useFocusOnMount";
import { useI18n } from "@/hooks/useI18n";
import type { CheckinResult } from "@/types/coachCheckin";

export interface CheckinDoneProps {
  planId: string;
  result: CheckinResult;
}

/** After the answers are saved: thanks, and the one next step each answer points to. */
export default function CheckinDone({ planId, result }: CheckinDoneProps) {
  const { t } = useI18n("coach");
  const ref = useFocusOnMount<HTMLDivElement>();
  const { remittance, savings, pay } = result.answers;
  const behind = remittance !== "on_track" || savings !== "on_track";

  return (
    <div ref={ref} role="status" tabIndex={-1} className="space-y-4 focus:outline-none">
      <div className="flex items-center gap-2">
        <CircleCheck className="h-6 w-6 shrink-0 text-safe-ink" aria-hidden="true" />
        <h2 className="text-lg font-bold">{t("checkin.done.title")}</h2>
      </div>
      <p className="text-sm text-muted-foreground">
        {result.already_answered ? t("checkin.done.already") : t("checkin.done.saved")}
      </p>

      {behind && (
        <div className="space-y-2 rounded-2xl border bg-card p-3">
          <p className="text-sm">{t("checkin.done.planHelp")}</p>
          <Button asChild variant="outline" className="min-h-11">
            <Link to={`/coach/plan/${encodeURIComponent(planId)}`}>
              {t("checkin.done.planLink")}
            </Link>
          </Button>
        </div>
      )}

      {pay !== "full_on_time" && (
        <div className="space-y-2 rounded-2xl border bg-card p-3">
          <p className="text-sm">{t("checkin.done.payHelp")}</p>
          <Button asChild variant="outline" className="min-h-11">
            <Link to="/radar/report">{t("checkin.done.payLink")}</Link>
          </Button>
        </div>
      )}

      <Button asChild className="min-h-11 font-bold">
        <Link to="/dashboard">{t("checkin.done.home")}</Link>
      </Button>
    </div>
  );
}

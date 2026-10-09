import { Info, OctagonAlert, TriangleAlert } from "lucide-react";

import { useI18n } from "@/hooks/useI18n";
import type { CoachPlanBody, WarningSeverity } from "@/types/coach";
import { warningsBySeverity } from "@/utils/coachPlan";

const STYLE: Record<WarningSeverity, { box: string; icon: typeof Info }> = {
  urgent: { box: "border-danger/40 bg-danger-tint", icon: OctagonAlert },
  warning: { box: "border-caution/40 bg-caution-tint", icon: TriangleAlert },
  info: { box: "border-border bg-muted/50", icon: Info },
};

/** What the worker should look at first, the most serious on top. The severity is a word as well
 * as an icon and a colour. Nothing is shown when the plan has no warning. */
export default function WarningsPanel({ plan }: { plan: CoachPlanBody }) {
  const { t } = useI18n("coach");
  const warnings = warningsBySeverity(plan);
  if (warnings.length === 0) {
    return null;
  }
  return (
    <section aria-labelledby="plan-warnings" className="space-y-3">
      <h2 id="plan-warnings" className="text-base font-extrabold">
        {t("plan.warnings.heading")}
      </h2>
      <ul className="space-y-2">
        {warnings.map((warning) => {
          const { box, icon: Icon } = STYLE[warning.severity];
          return (
            <li key={warning.id} className={`flex gap-3 rounded-2xl border p-3 ${box}`}>
              <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
              <div className="min-w-0 space-y-0.5">
                <p className="text-xs font-extrabold uppercase tracking-wide">
                  {t(`plan.warnings.severity.${warning.severity}`)}
                </p>
                <p className="text-sm">{warning.text}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

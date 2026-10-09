import { useI18n } from "@/hooks/useI18n";
import type { CoachPlanBody } from "@/types/coach";
import { sendWeeks } from "@/utils/coachPlan";

/** The 13 weeks, one after the other: the week's number, its title and what to do. A week in
 * which money is to be sent is marked with a word. */
export default function WeekTimeline({ plan }: { plan: CoachPlanBody }) {
  const { t } = useI18n("coach");
  const sends = sendWeeks(plan);
  return (
    <section aria-labelledby="plan-weeks" className="space-y-3">
      <h2 id="plan-weeks" className="text-base font-extrabold">
        {t("plan.weeks.heading")}
      </h2>
      <ol className="space-y-3">
        {plan.weeks.map((week) => (
          <li key={week.week} className="flex gap-3">
            <span
              aria-hidden="true"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-coach text-sm font-extrabold text-white"
            >
              {week.week}
            </span>
            <div className="min-w-0 flex-1 rounded-2xl border bg-card p-3">
              <h3 className="flex flex-wrap items-center gap-2 text-sm font-bold">
                <span>
                  <span className="sr-only">{t("plan.weeks.week", { week: week.week })}: </span>
                  {week.title}
                </span>
                {sends.has(week.week) && (
                  <span className="rounded-full border border-safe/40 bg-safe-tint px-2 py-0.5 text-xs font-bold text-safe-tint-ink">
                    {t("plan.weeks.sendMoney")}
                  </span>
                )}
              </h3>
              <ul className="mt-1.5 list-disc space-y-1 ps-5 text-sm text-muted-foreground">
                {week.actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

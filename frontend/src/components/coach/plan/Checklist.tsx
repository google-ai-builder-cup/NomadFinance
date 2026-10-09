import { useState } from "react";

import { useI18n } from "@/hooks/useI18n";
import type { CoachPlanBody } from "@/types/coach";
import { readTicks, writeTicks } from "@/utils/coachChecklist";

export interface ChecklistProps {
  plan: CoachPlanBody;
  planId: string;
  /** The signed-in person: with it the ticks are kept on this phone; without it they are not. */
  uid: string | undefined;
}

/** What to do before leaving. A tick is the worker's own note and stays on this phone (never sent
 * to the server), under their id and this plan. */
export default function Checklist({ plan, planId, uid }: ChecklistProps) {
  const { t } = useI18n("coach");
  const [ticks, setTicks] = useState<ReadonlySet<string>>(() =>
    uid === undefined ? new Set() : readTicks(uid, planId)
  );
  const done = plan.checklist.filter((item) => ticks.has(item.id)).length;

  function toggle(id: string) {
    const next = new Set(ticks);
    if (!next.delete(id)) {
      next.add(id);
    }
    setTicks(next);
    if (uid !== undefined) {
      writeTicks(uid, planId, next);
    }
  }

  return (
    <section aria-labelledby="plan-checklist" className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="plan-checklist" className="text-base font-extrabold">
          {t("plan.checklist.heading")}
        </h2>
        <p role="status" className="text-xs font-semibold text-muted-foreground">
          {t("plan.checklist.progress", { done, total: plan.checklist.length })}
        </p>
      </div>
      <ul className="space-y-2">
        {plan.checklist.map((item) => (
          <li key={item.id}>
            <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-2xl border bg-card p-3 text-sm">
              <input
                type="checkbox"
                checked={ticks.has(item.id)}
                onChange={() => toggle(item.id)}
                className="mt-0.5 h-5 w-5 shrink-0 accent-[hsl(var(--coach))]"
              />
              <span
                className={ticks.has(item.id) ? "text-muted-foreground line-through" : undefined}
              >
                {item.text}
              </span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

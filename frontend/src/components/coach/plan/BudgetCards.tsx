import { useI18n } from "@/hooks/useI18n";
import type { BudgetLine, CoachPlanBody } from "@/types/coach";
import { humanId, isKnownId, KNOWN_COST_IDS, KNOWN_GOAL_IDS, planMoney } from "@/utils/coachPlan";

function Rows({
  lines,
  prefix,
  known,
}: {
  lines: BudgetLine[];
  prefix: string;
  known: readonly string[];
}) {
  const { t } = useI18n("coach");
  return (
    <ul className="divide-y text-sm">
      {lines.map((line) => (
        <li key={line.id} className="flex items-baseline justify-between gap-3 py-1.5">
          <span>{isKnownId(known, line.id) ? t(`${prefix}.${line.id}`) : humanId(line.id)}</span>
          <span className="shrink-0 font-semibold tabular-nums">{planMoney(line.amount)}</span>
        </li>
      ))}
    </ul>
  );
}

/** One normal month after arrival: what comes in, what the costs are, what is set aside, and what
 * is left. A gap (costs and goals more than the pay) is said in words, not only in a colour. */
export default function BudgetCards({ plan }: { plan: CoachPlanBody }) {
  const { t } = useI18n("coach");
  const budget = plan.monthly_budget;
  const gap = budget.left_over.amount < 0;
  return (
    <section aria-labelledby="plan-budget" className="space-y-3">
      <h2 id="plan-budget" className="text-base font-extrabold">
        {t("plan.budget.heading")}
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl border bg-card p-4 sm:col-span-2">
          <p className="text-xs font-semibold text-muted-foreground">{t("plan.budget.income")}</p>
          <p className="text-2xl font-extrabold tabular-nums">{planMoney(budget.income)}</p>
        </div>
        <div className="rounded-2xl border bg-card p-4">
          <h3 className="mb-1 text-sm font-bold">{t("plan.budget.costs")}</h3>
          <Rows lines={budget.costs} prefix="plan.cost" known={KNOWN_COST_IDS} />
        </div>
        <div className="rounded-2xl border bg-card p-4">
          <h3 className="mb-1 text-sm font-bold">{t("plan.budget.goals")}</h3>
          <Rows lines={budget.goals} prefix="plan.goal" known={KNOWN_GOAL_IDS} />
        </div>
        <div
          className={`rounded-2xl border p-4 sm:col-span-2 ${gap ? "border-danger/40 bg-danger-tint" : "bg-card"}`}
        >
          <p className="text-xs font-semibold text-muted-foreground">
            {gap ? t("plan.budget.gap") : t("plan.budget.leftOver")}
          </p>
          <p className="text-2xl font-extrabold tabular-nums">{planMoney(budget.left_over)}</p>
          {gap && <p className="mt-1 text-sm">{t("plan.budget.gapHelp")}</p>}
        </div>
        {budget.setup_costs && (
          <div className="rounded-2xl border bg-muted/40 p-4 sm:col-span-2">
            <p className="text-sm">
              <span className="font-bold">{t("plan.budget.setup")}</span>{" "}
              <span className="font-semibold tabular-nums">{planMoney(budget.setup_costs)}</span>
            </p>
            <p className="text-xs text-muted-foreground">{t("plan.budget.setupHelp")}</p>
          </div>
        )}
      </div>
    </section>
  );
}

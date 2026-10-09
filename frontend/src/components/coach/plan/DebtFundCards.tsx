import { useI18n } from "@/hooks/useI18n";
import type { CoachPlanBody } from "@/types/coach";
import { planMoney } from "@/utils/coachPlan";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

/** The debt paydown (only when the worker owes something) and the emergency fund. */
export default function DebtFundCards({ plan }: { plan: CoachPlanBody }) {
  const { t } = useI18n("coach");
  const { debt, emergency_fund: fund } = plan;
  const toTarget =
    fund.weeks_to_target === 0
      ? t("plan.fund.reached")
      : fund.weeks_to_target === null
        ? t("plan.fund.noSaving")
        : t("plan.fund.weeks", { n: fund.weeks_to_target });
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {debt && (
        <section aria-labelledby="plan-debt" className="rounded-2xl border bg-card p-4">
          <h2 id="plan-debt" className="mb-1 text-base font-extrabold">
            {t("plan.debt.heading")}
          </h2>
          <dl className="divide-y">
            <Row label={t("plan.debt.outstanding")} value={planMoney(debt.outstanding)} />
            <Row label={t("plan.debt.payment")} value={planMoney(debt.monthly_payment)} />
            <Row
              label={t("plan.debt.toClear")}
              value={
                debt.months_to_clear === null
                  ? t("plan.debt.notCovered")
                  : t("plan.debt.months", { n: debt.months_to_clear })
              }
            />
          </dl>
        </section>
      )}
      <section aria-labelledby="plan-fund" className="rounded-2xl border bg-card p-4">
        <h2 id="plan-fund" className="mb-1 text-base font-extrabold">
          {t("plan.fund.heading")}
        </h2>
        <dl className="divide-y">
          <Row label={t("plan.fund.target")} value={planMoney(fund.target)} />
          <Row
            label={t("plan.fund.coversMonths")}
            value={t("plan.fund.months", { n: fund.months_of_costs })}
          />
          <Row label={t("plan.fund.saving")} value={planMoney(fund.monthly_saving)} />
          <Row label={t("plan.fund.toTarget")} value={toTarget} />
        </dl>
      </section>
    </div>
  );
}

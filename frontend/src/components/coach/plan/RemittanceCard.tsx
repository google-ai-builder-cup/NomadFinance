import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import type { CoachPlanBody } from "@/types/coach";
import { planMoney, remittanceLink } from "@/utils/coachPlan";

/** Sending money home: how much each month, the cheapest service Remittance X-Ray found with what
 * it costs and what arrives, the weeks to send, and a link into Remittance X-Ray with the route and
 * the amount already filled in. */
export default function RemittanceCard({ plan }: { plan: CoachPlanBody }) {
  const { t } = useI18n("coach");
  const { monthly_amount: amount, provider, schedule } = plan.remittance;
  const link = remittanceLink(plan);
  return (
    <section aria-labelledby="plan-remit" className="space-y-3 rounded-2xl border bg-card p-4">
      <h2 id="plan-remit" className="text-base font-extrabold">
        {t("plan.remittance.heading")}
      </h2>
      <p className="text-sm">
        <span className="text-muted-foreground">{t("plan.remittance.monthly")}</span>{" "}
        <span className="font-bold tabular-nums">{planMoney(amount)}</span>
      </p>
      {provider ? (
        <div className="space-y-1.5 rounded-xl bg-muted/40 p-3">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div className="col-span-2">
              <dt className="text-xs font-semibold text-muted-foreground">
                {t("plan.remittance.cheapest")}
              </dt>
              <dd className="font-bold">{provider.name}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-muted-foreground">
                {t("plan.remittance.fee")}
              </dt>
              <dd className="font-semibold tabular-nums">{planMoney(provider.fee)}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-muted-foreground">
                {t("plan.remittance.receives")}
              </dt>
              <dd className="font-semibold tabular-nums">{planMoney(provider.receives)}</dd>
            </div>
          </dl>
          <p className="text-xs text-muted-foreground">
            {t("plan.remittance.rate", {
              from: amount.currency,
              rate: provider.fx_rate,
              to: provider.receives.currency,
              date: provider.quoted_at.slice(0, 10),
            })}
          </p>
        </div>
      ) : (
        amount.amount > 0 && (
          <p className="text-sm text-muted-foreground">{t("plan.remittance.noProvider")}</p>
        )
      )}
      {schedule.length > 0 && (
        <div className="space-y-1.5">
          <h3 className="text-sm font-bold">{t("plan.remittance.schedule")}</h3>
          <ul className="flex flex-wrap gap-2">
            {schedule.map((send) => (
              <li
                key={send.week}
                className="rounded-full border bg-card px-3 py-1 text-xs font-semibold"
              >
                {t("plan.remittance.sendOn", { week: send.week, amount: planMoney(send.amount) })}
              </li>
            ))}
          </ul>
        </div>
      )}
      {link && (
        <Button asChild variant="outline" className="min-h-11 w-full gap-2 font-bold sm:w-auto">
          <Link to={link}>
            {t("plan.remittance.compare")}
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </Button>
      )}
    </section>
  );
}

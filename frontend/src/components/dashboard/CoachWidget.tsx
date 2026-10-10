import { Link } from "react-router-dom";

import WidgetCard from "@/components/dashboard/WidgetCard";
import type { ModuleItem } from "@/components/layout/navItems";
import { useCoachOverview } from "@/hooks/useCoachPlan";
import { useI18n } from "@/hooks/useI18n";
import { useUiLanguage } from "@/hooks/useUiLanguage";
import { cn } from "@/lib/utils";
import { CARD_STEPS, coachCardState, type OverviewPlan } from "@/utils/coachCardState";
import { relativeTime } from "@/utils/relativeTime";

const KNOWN_BANDS = ["needs_work", "getting_ready", "well_prepared"];

function planPath(plan: OverviewPlan): string {
  return `/coach/plan/${encodeURIComponent(plan.id)}`;
}

function PlanScore({ plan }: { plan: OverviewPlan }) {
  const { t } = useI18n();
  // A band this version does not know is left out, as on the score screen.
  return (
    <>
      {KNOWN_BANDS.includes(plan.band)
        ? t("dashboard.widgets.coach.scoreBand", {
            total: plan.score_total,
            band: t(`dashboard.widgets.coach.band.${plan.band}`),
          })
        : t("dashboard.widgets.coach.score", { total: plan.score_total })}
    </>
  );
}

/**
 * The Coach's card on the signed-in home (NF-FC-022): Start, Continue or View plan, from the
 * worker's open interview and newest plan. The strings are the shared ones, not the Coach's own:
 * the dashboard must not download the whole Coach namespace for one card. While the overview
 * loads, and if it cannot be read, the card is the plain pitch with a link to the Coach, so a
 * failed read never takes the way in away.
 */
export default function CoachWidget({ item }: { item: ModuleItem }) {
  const { t } = useI18n();
  const language = useUiLanguage();
  const overview = useCoachOverview();
  const state = overview.isSuccess ? coachCardState(overview.data) : null;

  let to = item.to;
  let openLabel = t("dashboard.widgets.coach.open");
  let body = <p className="text-sm text-muted-foreground">{t(item.descriptionKey)}</p>;

  if (state?.kind === "start") {
    openLabel = t("dashboard.widgets.coach.start");
  } else if (state?.kind === "plan") {
    to = planPath(state.plan);
    openLabel = t("dashboard.widgets.coach.viewPlan");
    body = (
      <div className="space-y-1">
        <p className="text-sm font-bold">{t("dashboard.widgets.coach.planReady")}</p>
        <p className="text-sm text-muted-foreground">
          <PlanScore plan={state.plan} />
        </p>
      </div>
    );
  } else if (state?.kind === "resume") {
    openLabel = t("dashboard.widgets.coach.resume");
    const when = relativeTime(state.lastActive, language);
    body = (
      <div className="space-y-2">
        <p className="text-sm font-bold">
          {t("dashboard.widgets.coach.step", { current: state.step, total: CARD_STEPS })}
        </p>
        <div className="flex gap-1" aria-hidden="true">
          {Array.from({ length: CARD_STEPS }, (_, index) => (
            <span
              key={index}
              className={cn(
                "h-1.5 flex-1 rounded-full",
                index < state.step ? "bg-primary" : "bg-muted"
              )}
            />
          ))}
        </div>
        <p className="text-sm text-muted-foreground max-sm:!line-clamp-2">
          {when !== null && `${t("dashboard.widgets.coach.lastAnswer", { when })} `}
          {t("dashboard.widgets.coach.saved")}
        </p>
        {state.plan !== null && (
          <Link
            to={planPath(state.plan)}
            className="inline-flex min-h-11 items-center text-sm font-bold underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {t("dashboard.widgets.coach.viewPlan")}
          </Link>
        )}
      </div>
    );
  }

  return (
    <WidgetCard
      icon={item.icon}
      pillar={item.pillar}
      title={t(item.nameKey)}
      to={to}
      openLabel={openLabel}
    >
      {body}
    </WidgetCard>
  );
}

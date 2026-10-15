import { Bell, BellOff, Fingerprint, LineChart, ShieldCheck, FileSearch } from "lucide-react";
import { useMemo } from "react";

import RiskBadge from "@/components/common/RiskBadge";
import StatCard, { type StatState } from "@/components/dashboard/StatCard";
import { Badge } from "@/components/ui/badge";
import ScoreRing from "@/components/visual/ScoreRing";
import { useRecentContracts } from "@/hooks/useContract";
import { useFinancialProfile } from "@/hooks/useFIB";
import { useI18n } from "@/hooks/useI18n";
import { useUnreadNotificationCount } from "@/hooks/useNotifications";
import { useRemittanceTrends } from "@/hooks/useRemittance";
import { useUserProfile } from "@/hooks/useUser";
import i18n from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { ApiError } from "@/services/apiClient";
import { defaultCorridor } from "@/utils/corridors";
import { STATUS_COLOR, STATUS_INK, statusFor } from "@/utils/fibScore";

// How many recent contracts the "checked" count looks at; past it the card says "50+".
const CONTRACT_COUNT_WINDOW = 50;

type QueryLike = { isPending: boolean; isError: boolean; error?: unknown };

function stateOf(query: QueryLike, hasData: boolean): StatState {
  if (query.isPending) {
    return "loading";
  }
  if (query.isError) {
    // The trends endpoint answers 404 when no history is stored yet: that is "empty", not broken.
    return query.error instanceof ApiError && query.error.status === 404 ? "empty" : "error";
  }
  return hasData ? "ready" : "empty";
}

const bigFigure =
  "text-[1.75rem] font-extrabold leading-none tracking-tight tabular-nums sm:text-[2.5rem]";

function IdentityKpi() {
  const { t } = useI18n();
  const profile = useFinancialProfile();
  const score = profile.data?.overall_score;
  const status = score === undefined ? null : statusFor(score);
  return (
    <StatCard
      label={t("dashboard.kpi.identity.label")}
      icon={Fingerprint}
      pillar="identity"
      state={stateOf(profile, score !== undefined)}
      empty={{
        icon: Fingerprint,
        message: t("dashboard.kpi.identity.empty"),
        actionLabel: t("dashboard.kpi.identity.action"),
        to: "/identity/log",
      }}
    >
      {score !== undefined && status !== null && (
        <div className="flex items-center gap-3 sm:gap-4">
          <ScoreRing
            className="max-sm:!h-14 max-sm:!w-14 max-sm:[&_svg]:h-14 max-sm:[&_svg]:w-14"
            value={score}
            color={STATUS_COLOR[status]}
            label={t("dashboard.kpi.identity.ring", { score })}
          />
          <p className="text-sm font-semibold" style={{ color: STATUS_INK[status] }}>
            {t(`fib.score.status.${status}`)}
          </p>
        </div>
      )}
    </StatCard>
  );
}

function AlertsKpi() {
  const { t } = useI18n();
  const unread = useUnreadNotificationCount();
  const count = unread.data;
  // Zero unread is good news, not an error: say so with a way to look anyway.
  return (
    <StatCard
      label={t("dashboard.kpi.alerts.label")}
      icon={Bell}
      pillar="radar"
      state={stateOf(unread, count !== undefined && count > 0)}
      empty={{
        icon: BellOff,
        message: t("dashboard.kpi.alerts.empty"),
        actionLabel: t("dashboard.kpi.alerts.action"),
        to: "/radar/alerts",
      }}
    >
      <p className={bigFigure}>{count}</p>
      <p className="text-sm text-muted-foreground">
        {t("dashboard.kpi.alerts.unread", { count: count ?? 0 })}
      </p>
    </StatCard>
  );
}

function ContractsKpi() {
  const { t } = useI18n();
  const contracts = useRecentContracts(CONTRACT_COUNT_WINDOW);
  const summary = useMemo(() => {
    const checked = (contracts.data ?? []).filter((c) => c.status === "completed");
    return {
      checked: checked.length,
      atLimit: (contracts.data?.length ?? 0) >= CONTRACT_COUNT_WINDOW,
      caution: checked.filter((c) => c.risk_level === "caution").length,
      danger: checked.filter((c) => c.risk_level === "danger").length,
    };
  }, [contracts.data]);
  return (
    <StatCard
      label={t("dashboard.kpi.contracts.label")}
      icon={ShieldCheck}
      pillar="contract"
      state={stateOf(contracts, summary.checked > 0)}
      empty={{
        icon: FileSearch,
        message: t("dashboard.kpi.contracts.empty"),
        actionLabel: t("dashboard.kpi.contracts.action"),
        to: "/contract",
      }}
    >
      <p className={bigFigure}>
        {summary.checked}
        {summary.atLimit && "+"}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {summary.danger > 0 && (
          <RiskBadge level="danger">
            {t("dashboard.kpi.contracts.danger", { count: summary.danger })}
          </RiskBadge>
        )}
        {summary.caution > 0 && (
          <RiskBadge level="caution">
            {t("dashboard.kpi.contracts.caution", { count: summary.caution })}
          </RiskBadge>
        )}
        {summary.danger === 0 && summary.caution === 0 && (
          <RiskBadge level="safe">{t("dashboard.kpi.contracts.allClear")}</RiskBadge>
        )}
      </div>
    </StatCard>
  );
}

function RateKpi() {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const profile = useUserProfile();
  const corridorId = defaultCorridor(profile.data?.host_country, profile.data?.home_country);
  const trends = useRemittanceTrends(profile.isSuccess ? corridorId : null, 30);
  const latest = trends.data?.summary?.latest;
  const change = trends.data?.summary?.change_pct;
  return (
    <StatCard
      label={t("dashboard.kpi.rate.label", { corridor: corridorId.replace("-", " → ") })}
      icon={LineChart}
      pillar="remit"
      state={stateOf(profile.isSuccess ? trends : profile, latest !== undefined)}
      empty={{
        icon: LineChart,
        message: t("dashboard.kpi.rate.empty"),
        actionLabel: t("dashboard.kpi.rate.action"),
        to: "/remittance",
      }}
    >
      {latest && trends.data && (
        <>
          {/* The unit never splits ("INR /" over "SGD"): it drops below the figure whole. */}
          <p className={cn(bigFigure, "flex flex-wrap items-baseline gap-x-1.5 gap-y-1")}>
            {latest.rate.toLocaleString(language, { maximumFractionDigits: 4 })}
            <span className="whitespace-nowrap text-sm font-bold text-subtle">
              {trends.data.quote_currency} / {trends.data.base_currency}
            </span>
          </p>
          {change !== undefined && (
            <Badge tone={change >= 0 ? "safe" : "caution"} className="self-start">
              {t("dashboard.kpi.rate.change", {
                value: `${change >= 0 ? "+" : ""}${change.toLocaleString(language, { maximumFractionDigits: 1 })}`,
              })}
            </Badge>
          )}
        </>
      )}
    </StatCard>
  );
}

/** The four numbers at the top of the dashboard. Each one is read from a hook the pillar pages
 * already use, so the figures match what the worker sees when they open that pillar. */
export default function KpiRow() {
  const { t } = useI18n();
  return (
    <section
      aria-label={t("dashboard.kpi.heading")}
      className="grid grid-cols-2 gap-2.5 sm:gap-4 xl:grid-cols-4"
    >
      <IdentityKpi />
      <AlertsKpi />
      <ContractsKpi />
      <RateKpi />
    </section>
  );
}

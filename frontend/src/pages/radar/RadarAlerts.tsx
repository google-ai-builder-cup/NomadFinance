import { Bell } from "lucide-react";
import { Link } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import AlertItem from "@/components/radar/AlertItem";
import RouteAlertItem from "@/components/radar/RouteAlertItem";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useNotifications } from "@/hooks/useNotifications";
import { useRouteAlerts } from "@/hooks/useRadar";
import { useUserProfile } from "@/hooks/useUser";
import i18n from "@/lib/i18n";
import { alertRoutes } from "@/utils/alertRoutes";
import { CORRIDORS } from "@/utils/corridors";
import { countryName } from "@/utils/format";

/**
 * The worker's alerts: what is active on their routes right now, then their own notification
 * feed (radar alerts today, reminders and system messages later). The first is read from
 * `radar_alerts` directly, so a worker who joined after an alert was created still sees it.
 */
export default function RadarAlerts() {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const profile = useUserProfile();
  const routes = alertRoutes(profile.data);
  const routeAlerts = useRouteAlerts(routes);
  const notifications = useNotifications();

  if (
    profile.isPending ||
    notifications.isPending ||
    (routes.length > 0 && routeAlerts.isPending)
  ) {
    return <LoadingSpinner label={t("common.loading")} className="py-16" />;
  }
  if (notifications.isError || routeAlerts.isError) {
    return (
      <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
        <p className="text-sm text-muted-foreground">{t("radar.alerts.loadError")}</p>
        <Button
          onClick={() => {
            void notifications.refetch();
            void routeAlerts.refetch();
          }}
        >
          {t("common.retry")}
        </Button>
      </div>
    );
  }

  const active = routeAlerts.data ?? [];
  const feed = notifications.data;
  const routeNames = routes
    .map(
      (id) =>
        `${countryName(CORRIDORS[id].host, language)} → ${countryName(CORRIDORS[id].home, language)}`
    )
    .join(", ");

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">{t("radar.alerts.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("radar.alerts.subtitle")}</p>
      </header>

      <section aria-labelledby="route-alerts-title" className="space-y-3">
        <h2 id="route-alerts-title" className="text-lg font-semibold">
          {t("radar.alerts.route.title")}
        </h2>
        <p className="text-xs text-muted-foreground">
          {routes.length > 0
            ? t("radar.alerts.route.routes", { routes: routeNames })
            : t("radar.alerts.route.noRoutes")}{" "}
          <Link to="/profile" className="underline">
            {t("radar.alerts.route.chooseRoutes")}
          </Link>
        </p>
        {active.length === 0 ? (
          <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
            {t("radar.alerts.route.none")}
          </p>
        ) : (
          <ul className="space-y-3">
            {active.map((alert) => (
              <li key={`${alert.corridor_id}/${alert.id}`}>
                <RouteAlertItem alert={alert} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="alert-feed-title" className="space-y-3">
        <h2 id="alert-feed-title" className="text-lg font-semibold">
          {t("radar.alerts.feedTitle")}
        </h2>
        {feed.length === 0 ? (
          <EmptyState
            icon={Bell}
            title={t("radar.alerts.emptyTitle")}
            description={t("radar.alerts.emptyDescription")}
          />
        ) : (
          <ul className="space-y-3">
            {feed.map((notification) => (
              <li key={notification.id}>
                <AlertItem notification={notification} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

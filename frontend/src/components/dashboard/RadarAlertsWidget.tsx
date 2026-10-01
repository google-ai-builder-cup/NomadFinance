import { Radar } from "lucide-react";

import WidgetCard from "@/components/dashboard/WidgetCard";
import AlertItem from "@/components/radar/AlertItem";
import { useI18n } from "@/hooks/useI18n";
import { useNotifications } from "@/hooks/useNotifications";

const MAX_SHOWN = 2;

/** Home dashboard widget: the worker's most recent radar alerts, reusing `AlertItem` as-is
 * (read/unread styling, deep links, mark-as-read) rather than a parallel compact copy
 * (NF-P3-019). */
export default function RadarAlertsWidget() {
  const { t } = useI18n();
  const notifications = useNotifications();
  const unread = notifications.data?.filter((notification) => !notification.read).length ?? 0;

  return (
    <WidgetCard
      icon={Radar}
      title={t("pillars.radar.name")}
      to="/radar"
      openLabel={t("dashboard.widgets.radar.open")}
    >
      {notifications.isPending && (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      )}

      {notifications.isError && (
        <p className="text-sm text-muted-foreground">{t("dashboard.widgets.loadError")}</p>
      )}

      {notifications.isSuccess && notifications.data.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("dashboard.widgets.radar.empty")}</p>
      )}

      {notifications.isSuccess && notifications.data.length > 0 && (
        <div className="space-y-2">
          {unread > 0 && (
            <p className="text-xs font-medium text-primary">
              {t("dashboard.widgets.radar.unread", { count: unread })}
            </p>
          )}
          <ul className="space-y-2">
            {notifications.data.slice(0, MAX_SHOWN).map((notification) => (
              <li key={notification.id}>
                <AlertItem notification={notification} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </WidgetCard>
  );
}

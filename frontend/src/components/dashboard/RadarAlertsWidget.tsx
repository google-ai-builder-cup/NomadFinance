import { Radar } from "lucide-react";

import WidgetCard from "@/components/dashboard/WidgetCard";
import AlertItem from "@/components/radar/AlertItem";
import { useI18n } from "@/hooks/useI18n";
import { useNotifications, useUnreadNotificationCount } from "@/hooks/useNotifications";
import { cn } from "@/lib/utils";

const MAX_SHOWN = 2;

/** Home dashboard widget: the worker's most recent radar alerts, reusing `AlertItem` as-is
 * (read/unread styling, deep links, mark-as-read) rather than a parallel compact copy
 * (NF-P3-019). */
export default function RadarAlertsWidget() {
  const { t } = useI18n();
  // Two rows and a count, not the whole feed (NF-P4-003). A failed count only hides the
  // "N new" line; the alerts still show.
  const notifications = useNotifications(MAX_SHOWN);
  const unread = useUnreadNotificationCount().data ?? 0;

  return (
    <WidgetCard
      icon={Radar}
      pillar="radar"
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
          {/* On a phone the card is the count alone (the alerts are one tap away), so it stays
              as short as its neighbours; the count is shown even at zero there. */}
          <p className={cn("text-xs font-bold text-radar-ink", unread === 0 && "sm:hidden")}>
            {t("dashboard.widgets.radar.unread", { count: unread })}
          </p>
          <ul className="hidden space-y-2 sm:block">
            {notifications.data.map((notification) => (
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

import { Bell } from "lucide-react";

import EmptyState from "@/components/common/EmptyState";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import AlertItem from "@/components/radar/AlertItem";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useNotifications } from "@/hooks/useNotifications";

/** The worker's notification feed: radar alerts (NF-P3-004) today, reminders and system
 * messages later — `users/{uid}/notifications` doesn't distinguish who reads it. */
export default function RadarAlerts() {
  const { t } = useI18n();
  const notifications = useNotifications();

  if (notifications.isPending) {
    return <LoadingSpinner label={t("common.loading")} className="py-16" />;
  }
  if (notifications.isError) {
    return (
      <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
        <p className="text-sm text-muted-foreground">{t("radar.alerts.loadError")}</p>
        <Button onClick={() => void notifications.refetch()}>{t("common.retry")}</Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">{t("radar.alerts.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("radar.alerts.subtitle")}</p>
      </header>

      {notifications.data.length === 0 ? (
        <EmptyState
          icon={Bell}
          title={t("radar.alerts.emptyTitle")}
          description={t("radar.alerts.emptyDescription")}
        />
      ) : (
        <ul className="space-y-3">
          {notifications.data.map((notification) => (
            <li key={notification.id}>
              <AlertItem notification={notification} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

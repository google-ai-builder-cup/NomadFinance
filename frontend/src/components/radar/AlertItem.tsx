import { Link } from "react-router-dom";

import { useI18n } from "@/hooks/useI18n";
import { useMarkNotificationRead } from "@/hooks/useNotifications";
import i18n from "@/lib/i18n";
import type { AppNotification } from "@/types/notification";

export interface AlertItemProps {
  notification: AppNotification;
}

/** One row of the alert feed: unread styling, tap to mark read and open its deep link. */
export default function AlertItem({ notification }: AlertItemProps) {
  const { t } = useI18n();
  const markRead = useMarkNotificationRead();
  const language = i18n.resolvedLanguage ?? "en";
  const date = notification.created_at.toDate().toLocaleDateString(language, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  function handleOpen() {
    if (!notification.read) {
      markRead.mutate(notification.id);
    }
  }

  const body = (
    <div className="flex items-start gap-3">
      {!notification.read && (
        <span aria-hidden="true" className="mt-2 h-2 w-2 shrink-0 rounded-full bg-radar" />
      )}
      <div
        className={`min-w-0 flex-1 space-y-1 ${notification.read ? "text-muted-foreground" : ""}`}
      >
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <p className="font-bold text-foreground">{notification.title}</p>
          <span className="text-xs text-muted-foreground">{date}</span>
        </div>
        <p className="text-sm">{notification.body}</p>
      </div>
    </div>
  );

  const className = `block rounded-xl border p-4 text-left shadow-sm transition-colors ${
    notification.read ? "bg-card" : "border-radar/30 bg-radar-tint"
  } hover:bg-accent`;

  if (notification.deep_link) {
    return (
      <Link
        to={notification.deep_link}
        onClick={handleOpen}
        className={className}
        aria-label={
          notification.read
            ? notification.title
            : t("radar.alerts.unread", { title: notification.title })
        }
      >
        {body}
      </Link>
    );
  }

  return (
    <button type="button" onClick={handleOpen} className={`w-full ${className}`}>
      {body}
    </button>
  );
}

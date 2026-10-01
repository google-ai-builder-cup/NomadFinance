import { ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { RouteAlert } from "@/types/radar";
import { CORRIDORS } from "@/utils/corridors";
import { countryName } from "@/utils/format";

const SEVERITY_CLASSES: Record<RouteAlert["severity"], string> = {
  info: "border-amber-500/30 bg-amber-500/5",
  warning: "border-orange-500/40 bg-orange-500/10",
  critical: "border-destructive/40 bg-destructive/10",
};

export interface RouteAlertItemProps {
  alert: RouteAlert;
}

/** One alert still active on one of the worker's routes, linking to the business's profile. */
export default function RouteAlertItem({ alert }: RouteAlertItemProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const route = CORRIDORS[alert.corridor_id];
  const routeName = `${countryName(route.host, language)} → ${countryName(route.home, language)}`;
  const date = alert.created_at.toDate().toLocaleDateString(language, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <Link
      to={`/radar/entity/${alert.entity_slug}`}
      className={cn(
        "block rounded-lg border p-4 transition-colors hover:bg-accent",
        SEVERITY_CLASSES[alert.severity]
      )}
    >
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-destructive" aria-hidden="true" />
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <p className="font-medium">{alert.entity_name}</p>
            <span className="text-xs text-muted-foreground">{date}</span>
          </div>
          <p className="text-sm">
            {t("radar.alerts.route.summary", {
              number: String(alert.report_count),
              days: String(alert.window_days),
              violation: t(`radar.violation.${alert.violation_type}`),
            })}
          </p>
          <p className="text-xs text-muted-foreground">
            {t(`radar.alerts.route.severity.${alert.severity}`)} · {routeName}
          </p>
        </div>
      </div>
    </Link>
  );
}

import { Fingerprint } from "lucide-react";

import WidgetCard from "@/components/dashboard/WidgetCard";
import { useFinancialProfile } from "@/hooks/useFIB";
import { useI18n } from "@/hooks/useI18n";
import { STATUS_COLOR, statusFor } from "@/utils/fibScore";

/** Home dashboard widget: the worker's overall Financial Identity score, reusing the exact
 * status colors `ScoreMeter`/`ReportPreviewModal` already use (NF-P3-019). */
export default function FIBProgressWidget() {
  const { t } = useI18n();
  const profile = useFinancialProfile();

  return (
    <WidgetCard
      icon={Fingerprint}
      title={t("pillars.identity.name")}
      to="/identity"
      openLabel={t("dashboard.widgets.identity.open")}
    >
      {profile.isPending && <p className="text-sm text-muted-foreground">{t("common.loading")}</p>}

      {profile.isError && (
        <p className="text-sm text-muted-foreground">{t("dashboard.widgets.loadError")}</p>
      )}

      {profile.isSuccess && profile.data === null && (
        <p className="text-sm text-muted-foreground">{t("dashboard.widgets.identity.empty")}</p>
      )}

      {profile.isSuccess && profile.data !== null && (
        <div className="flex items-center gap-3">
          <span
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-4 text-sm font-bold tabular-nums"
            style={{ borderColor: STATUS_COLOR[statusFor(profile.data.overall_score)] }}
          >
            {profile.data.overall_score}
          </span>
          <p
            className="text-sm font-medium"
            style={{ color: STATUS_COLOR[statusFor(profile.data.overall_score)] }}
          >
            {t(`fib.score.status.${statusFor(profile.data.overall_score)}`)}
          </p>
        </div>
      )}
    </WidgetCard>
  );
}

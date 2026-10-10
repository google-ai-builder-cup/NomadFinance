import { Fingerprint } from "lucide-react";

import WidgetCard from "@/components/dashboard/WidgetCard";
import ScoreRing from "@/components/visual/ScoreRing";
import { useFinancialProfile } from "@/hooks/useFIB";
import { useI18n } from "@/hooks/useI18n";
import { STATUS_COLOR, STATUS_INK, statusFor } from "@/utils/fibScore";

/** Home dashboard widget: the worker's overall Financial Identity score, reusing the exact
 * status colors `ScoreMeter`/`ReportPreviewModal` already use (NF-P3-019). */
export default function FIBProgressWidget() {
  const { t } = useI18n();
  const profile = useFinancialProfile();

  return (
    <WidgetCard
      icon={Fingerprint}
      pillar="identity"
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
        <div className="flex items-center gap-3 sm:gap-4">
          <ScoreRing
            className="max-sm:!h-14 max-sm:!w-14 max-sm:[&_svg]:h-14 max-sm:[&_svg]:w-14"
            value={profile.data.overall_score}
            color={STATUS_COLOR[statusFor(profile.data.overall_score)]}
            label={t("dashboard.kpi.identity.ring", { score: profile.data.overall_score })}
          />
          <p
            className="text-sm font-semibold"
            style={{ color: STATUS_INK[statusFor(profile.data.overall_score)] }}
          >
            {t(`fib.score.status.${statusFor(profile.data.overall_score)}`)}
          </p>
        </div>
      )}
    </WidgetCard>
  );
}

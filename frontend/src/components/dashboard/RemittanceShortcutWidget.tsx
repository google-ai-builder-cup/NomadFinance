import { ArrowLeftRight } from "lucide-react";

import WidgetCard from "@/components/dashboard/WidgetCard";
import { useUserProfile } from "@/hooks/useUser";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { defaultCorridor } from "@/utils/corridors";
import { countryName } from "@/utils/format";

/** Home dashboard widget: a shortcut straight into comparing the worker's own corridor
 * (NF-P3-019). No transfer history to show — nothing reads `transfers` anywhere in the
 * frontend yet, and the task names this one a "shortcut," not a summary. */
export default function RemittanceShortcutWidget() {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const profile = useUserProfile();
  const corridorId = defaultCorridor(profile.data?.host_country, profile.data?.home_country);
  const [host, home] = corridorId.split("-");

  return (
    <WidgetCard
      icon={ArrowLeftRight}
      pillar="remit"
      title={t("pillars.remittance.name")}
      to="/remittance"
      openLabel={t("dashboard.widgets.remittance.open")}
    >
      <p className="text-sm text-muted-foreground">
        {t("dashboard.widgets.remittance.description", {
          from: countryName(host, language),
          to: countryName(home, language),
        })}
      </p>
    </WidgetCard>
  );
}

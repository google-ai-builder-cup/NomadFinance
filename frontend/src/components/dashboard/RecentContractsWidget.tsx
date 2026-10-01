import { ShieldCheck } from "lucide-react";

import WidgetCard from "@/components/dashboard/WidgetCard";
import { useRecentContracts } from "@/hooks/useContract";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { RISK_BADGE_CLASSES } from "@/utils/contractRisk";

const MAX_SHOWN = 3;

/** Home dashboard widget: the worker's most recent contracts and their risk badges, or their
 * in-progress/failed status while a score isn't ready yet (NF-P3-019). */
export default function RecentContractsWidget() {
  const { t } = useI18n();
  const contracts = useRecentContracts(MAX_SHOWN);

  return (
    <WidgetCard
      icon={ShieldCheck}
      title={t("pillars.contract.name")}
      to="/contract"
      openLabel={t("dashboard.widgets.contract.open")}
    >
      {contracts.isPending && (
        <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
      )}

      {contracts.isError && (
        <p className="text-sm text-muted-foreground">{t("dashboard.widgets.loadError")}</p>
      )}

      {contracts.isSuccess && contracts.data.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("dashboard.widgets.contract.empty")}</p>
      )}

      {contracts.isSuccess && contracts.data.length > 0 && (
        <ul className="space-y-2">
          {contracts.data.map((contract) => (
            <li key={contract.id} className="flex items-center justify-between gap-2 text-sm">
              <span className="min-w-0 truncate">
                {contract.title ?? t("dashboard.widgets.contract.untitled")}
              </span>
              {contract.risk_level ? (
                <span
                  className={cn(
                    "shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium",
                    RISK_BADGE_CLASSES[contract.risk_level]
                  )}
                >
                  {t(`contract.result.counts.${contract.risk_level}`)}
                </span>
              ) : (
                <span className="shrink-0 text-xs text-muted-foreground">
                  {t(`dashboard.widgets.contract.status.${contract.status}`)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </WidgetCard>
  );
}

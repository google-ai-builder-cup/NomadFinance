import { ChevronRight, FileText, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import WidgetCard from "@/components/dashboard/WidgetCard";
import { useRecentContracts } from "@/hooks/useContract";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { RISK_BADGE_CLASSES } from "@/utils/contractRisk";

const MAX_SHOWN = 3;

// Contracts are often titled in capitals, which reads as shouting in a list. Only an all-caps
// title is softened; a title the worker or the parser already cased is left as it is.
function tidyTitle(title: string): string {
  const letters = title.replace(/[^\p{L}]/gu, "");
  if (
    letters.length < 4 ||
    letters !== letters.toUpperCase() ||
    letters === letters.toLowerCase()
  ) {
    return title;
  }
  const lower = title.toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

/** Home dashboard widget: the worker's most recent contracts and their risk badges, or their
 * in-progress/failed status while a score isn't ready yet (NF-P3-019). */
export default function RecentContractsWidget() {
  const { t } = useI18n();
  const contracts = useRecentContracts(MAX_SHOWN);

  return (
    <WidgetCard
      icon={ShieldCheck}
      pillar="contract"
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
          {contracts.data.map((contract) => {
            const title = tidyTitle(contract.title ?? t("dashboard.widgets.contract.untitled"));
            const open = contract.status === "completed";
            const row = (
              <>
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-contract-tint text-contract-ink">
                  <FileText className="h-4 w-4" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1 truncate text-sm font-semibold">{title}</span>
                {contract.risk_level ? (
                  <span
                    className={cn(
                      "shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-bold",
                      RISK_BADGE_CLASSES[contract.risk_level]
                    )}
                  >
                    {t(`contract.result.counts.${contract.risk_level}`)}
                  </span>
                ) : (
                  <span className="shrink-0 rounded-full border bg-muted px-2.5 py-0.5 text-xs font-semibold text-muted-foreground">
                    {t(`dashboard.widgets.contract.status.${contract.status}`)}
                  </span>
                )}
                {open && (
                  <ChevronRight
                    className="h-4 w-4 shrink-0 text-subtle transition-transform group-hover:translate-x-0.5"
                    aria-hidden="true"
                  />
                )}
              </>
            );
            const rowClass =
              "group flex items-center gap-3 rounded-xl border bg-background/60 p-2.5 transition-colors";
            return (
              <li key={contract.id}>
                {open ? (
                  <Link
                    to={`/contract/${contract.id}`}
                    className={cn(rowClass, "hover:border-contract/40 hover:bg-contract-tint/50")}
                  >
                    {row}
                  </Link>
                ) : (
                  <div className={rowClass}>{row}</div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </WidgetCard>
  );
}

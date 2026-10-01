import { ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import { Button } from "@/components/ui/button";
import { useRecentContracts } from "@/hooks/useContract";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { ContractSummary } from "@/types/contract";
import { RISK_BADGE_CLASSES } from "@/utils/contractRisk";

// Plenty for a worker's own contracts; the list is not paged.
const MAX_SHOWN = 50;

const ROW_CLASS = "flex items-center justify-between gap-3 rounded-lg border bg-card p-4";

function ContractRow({ contract }: { contract: ContractSummary }) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const date = contract.created_at?.toDate().toLocaleDateString(language, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
  const content = (
    <>
      <div className="min-w-0">
        <p className="truncate font-medium">
          {contract.title ?? t("dashboard.widgets.contract.untitled")}
        </p>
        {date && <p className="text-xs text-muted-foreground">{date}</p>}
      </div>
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
    </>
  );

  if (contract.status !== "completed") {
    return <div className={ROW_CLASS}>{content}</div>;
  }
  return (
    <Link
      to={`/contract/${contract.id}`}
      className={cn(ROW_CLASS, "transition-colors hover:bg-accent")}
    >
      {content}
    </Link>
  );
}

/** Every contract the worker has checked, newest first; a finished one reopens its report. */
export default function ContractList() {
  const { t } = useI18n();
  const contracts = useRecentContracts(MAX_SHOWN);

  if (contracts.isPending) {
    return <LoadingSpinner label={t("common.loading")} className="py-16" />;
  }
  if (contracts.isError) {
    return (
      <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
        <p className="text-sm text-muted-foreground">{t("contract.history.loadError")}</p>
        <Button onClick={() => void contracts.refetch()}>{t("common.retry")}</Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <header className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">{t("contract.history.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("contract.history.subtitle")}</p>
        </div>
        <Button asChild size="sm" className="shrink-0">
          <Link to="/contract">{t("contract.history.checkNew")}</Link>
        </Button>
      </header>

      {contracts.data.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title={t("contract.history.emptyTitle")}
          description={t("dashboard.widgets.contract.empty")}
        />
      ) : (
        <ul className="space-y-2">
          {contracts.data.map((contract) => (
            <li key={contract.id}>
              <ContractRow contract={contract} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

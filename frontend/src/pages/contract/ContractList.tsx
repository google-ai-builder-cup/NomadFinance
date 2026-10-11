import { ChevronRight, FilePlus2, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import PageHeader from "@/components/common/PageHeader";
import PageStateFrame from "@/components/common/PageStateFrame";
import RiskBadge from "@/components/common/RiskBadge";
import { Button } from "@/components/ui/button";
import PillarIllustration from "@/components/visual/PillarIllustration";
import { useRecentContracts } from "@/hooks/useContract";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { ContractSummary } from "@/types/contract";
import { RISK_BAR_CLASSES } from "@/utils/contractRisk";

// Plenty for a worker's own contracts; the list is not paged.
const MAX_SHOWN = 50;

const ROW_CLASS = "card-surface flex items-center gap-3 overflow-hidden p-0 pr-4";

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
      <span
        className={cn(
          "w-1.5 shrink-0 self-stretch",
          contract.risk_level ? RISK_BAR_CLASSES[contract.risk_level] : "bg-border"
        )}
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1 py-4">
        <p className="truncate font-bold">
          {contract.title ?? t("dashboard.widgets.contract.untitled")}
        </p>
        {date && <p className="text-xs text-muted-foreground">{date}</p>}
      </div>
      {contract.risk_level ? (
        <RiskBadge level={contract.risk_level}>
          {t(`contract.result.counts.${contract.risk_level}`)}
        </RiskBadge>
      ) : (
        <span className="shrink-0 text-xs text-muted-foreground">
          {t(`dashboard.widgets.contract.status.${contract.status}`)}
        </span>
      )}
      {contract.status === "completed" && (
        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      )}
    </>
  );

  if (contract.status !== "completed") {
    return <div className={ROW_CLASS}>{content}</div>;
  }
  return (
    <Link
      to={`/contract/${contract.id}`}
      className={cn(ROW_CLASS, "transition-shadow duration-base hover:shadow-md")}
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
    return (
      <PageStateFrame pillar="contract" icon={ShieldCheck} title={t("contract.history.title")}>
        <LoadingSpinner label={t("common.loading")} className="py-16" />
      </PageStateFrame>
    );
  }
  if (contracts.isError) {
    return (
      <PageStateFrame pillar="contract" icon={ShieldCheck} title={t("contract.history.title")}>
        <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-sm text-muted-foreground">{t("contract.history.loadError")}</p>
          <Button onClick={() => void contracts.refetch()}>{t("common.retry")}</Button>
        </div>
      </PageStateFrame>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        pillar="contract"
        icon={ShieldCheck}
        title={t("contract.history.title")}
        description={t("contract.history.subtitle")}
        compact
        actions={
          <Button
            asChild
            className="h-11 rounded-xl bg-contract-deep px-5 font-bold text-white hover:bg-contract-deep/90"
          >
            <Link to="/contract">
              <FilePlus2 className="mr-2 h-4 w-4" aria-hidden="true" />
              {t("contract.history.checkNew")}
            </Link>
          </Button>
        }
      />

      {contracts.data.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title={t("contract.history.emptyTitle")}
          description={t("dashboard.widgets.contract.empty")}
          illustration={<PillarIllustration pillar="contract" />}
        />
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
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

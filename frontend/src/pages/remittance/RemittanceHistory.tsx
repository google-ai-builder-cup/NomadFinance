import { ArrowLeftRight } from "lucide-react";
import { Link } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import PageHeader from "@/components/common/PageHeader";
import PageStateFrame from "@/components/common/PageStateFrame";
import { Button } from "@/components/ui/button";
import PillarIllustration from "@/components/visual/PillarIllustration";
import { useI18n } from "@/hooks/useI18n";
import { useLoggedTransfers } from "@/hooks/useRemittance";
import i18n from "@/lib/i18n";
import { CORRIDORS } from "@/utils/corridors";
import { formatMoney } from "@/utils/format";

/** The transfers the worker logged with "I used this": when, which service, how much was sent and
 * what arrived. The same entries feed their Financial Identity and the Coach's "money you send
 * home". Read-only: a wrong entry is not edited here. */
export default function RemittanceHistory() {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const transfers = useLoggedTransfers();

  if (transfers.isPending) {
    return (
      <PageStateFrame pillar="remit" icon={ArrowLeftRight} title={t("remittance.history.title")}>
        <LoadingSpinner label={t("common.loading")} className="py-16" />
      </PageStateFrame>
    );
  }
  if (transfers.isError) {
    return (
      <PageStateFrame pillar="remit" icon={ArrowLeftRight} title={t("remittance.history.title")}>
        <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-sm text-muted-foreground">{t("remittance.history.loadError")}</p>
          <Button onClick={() => void transfers.refetch()}>{t("common.retry")}</Button>
        </div>
      </PageStateFrame>
    );
  }

  const back = (
    <Button asChild variant="outline" className="h-11 rounded-xl bg-card font-bold">
      <Link to="/remittance">{t("remittance.history.compare")}</Link>
    </Button>
  );

  return (
    <div className="space-y-5">
      <PageHeader
        pillar="remit"
        icon={ArrowLeftRight}
        title={t("remittance.history.title")}
        description={t("remittance.history.subtitle")}
        actions={back}
        compact
      />
      {transfers.data.length === 0 ? (
        <EmptyState
          icon={ArrowLeftRight}
          title={t("remittance.history.empty.title")}
          description={t("remittance.history.empty.description")}
          illustration={<PillarIllustration pillar="remit" />}
          className="min-h-[18rem] justify-center"
        />
      ) : (
        <ul className="space-y-3">
          {transfers.data.map((transfer) => {
            const route = CORRIDORS[transfer.corridor_id];
            const sent = formatMoney(
              transfer.send_amount,
              transfer.send_currency,
              language,
              route?.decimals ?? 2
            );
            const received = formatMoney(
              transfer.receive_amount,
              transfer.receive_currency,
              language,
              0
            );
            return (
              <li key={transfer.id} className="card-surface space-y-1 p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <p className="font-bold">{transfer.provider_name}</p>
                  <time dateTime={transfer.entry_date} className="text-xs text-muted-foreground">
                    {new Date(`${transfer.entry_date}T00:00:00`).toLocaleDateString(language, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </time>
                </div>
                <p className="text-sm tabular-nums">
                  {t("remittance.history.row", { sent, received })}
                </p>
                <p className="text-xs text-muted-foreground">
                  {transfer.corridor_id.replace("-", " → ")}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

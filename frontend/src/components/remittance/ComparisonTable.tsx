import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { ProviderResult, RemittanceComparison } from "@/types/remittance";
import { CORRIDORS } from "@/utils/corridors";
import { formatMoney } from "@/utils/format";
import {
  type SortColumn,
  type SortState,
  nextSortState,
  sortProviders,
} from "@/utils/remittanceTable";

export interface ComparisonTableProps {
  comparison: RemittanceComparison;
}

const COLUMNS: readonly { key: SortColumn; labelKey: string; align: "left" | "right" }[] = [
  { key: "provider", labelKey: "remittance.table.columns.provider", align: "left" },
  { key: "speed", labelKey: "remittance.table.columns.speed", align: "right" },
  { key: "fee", labelKey: "remittance.table.columns.fee", align: "right" },
  { key: "totalCost", labelKey: "remittance.table.columns.totalCost", align: "right" },
  { key: "receives", labelKey: "remittance.table.columns.receives", align: "right" },
];

function SortMark({ direction }: { direction: "asc" | "desc" | null }) {
  return (
    <span
      aria-hidden="true"
      className={cn("text-xs", direction === null && "text-muted-foreground/40")}
    >
      {direction === "asc" ? "▲" : direction === "desc" ? "▼" : "↕"}
    </span>
  );
}

function ProviderRow({
  provider,
  rank,
  total,
  sendMoney,
  receiveMoney,
}: {
  provider: ProviderResult;
  rank: number;
  total: number;
  sendMoney: (amount: number) => string;
  receiveMoney: (amount: number) => string;
}) {
  const { t } = useI18n();
  const isBest = provider.rank === 1;

  return (
    <tr className={cn("border-b last:border-0", isBest && "bg-emerald-500/10")}>
      <td className="px-3 py-3 align-top">
        <span className="sr-only">
          {t("remittance.table.rankSr", { rank: String(rank), count: String(total) })}
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{provider.firm}</span>
          {isBest && (
            <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-semibold text-white">
              {t("remittance.table.bestBadge")}
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {provider.payment_instrument} → {provider.pickup_method}
        </p>
      </td>
      <td className="px-3 py-3 text-right align-top tabular-nums">{provider.speed}</td>
      <td className="px-3 py-3 text-right align-top tabular-nums">
        {sendMoney(provider.fee)}
        {provider.estimated && (
          <span className="block text-xs text-amber-600">{t("remittance.table.estimatedTag")}</span>
        )}
      </td>
      <td className="px-3 py-3 text-right align-top tabular-nums">
        {provider.total_cost_pct.toLocaleString(i18n.resolvedLanguage ?? "en", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}
        %
      </td>
      <td className="px-3 py-3 text-right align-top tabular-nums">
        <span className={cn("font-semibold", isBest && "text-emerald-700 dark:text-emerald-400")}>
          {receiveMoney(provider.recipient_receives ?? 0)}
        </span>
        {!isBest && !!provider.less_than_best && (
          <span className="block text-xs text-destructive">
            {t("remittance.table.vsBest", { amount: receiveMoney(provider.less_than_best) })}
          </span>
        )}
      </td>
    </tr>
  );
}

/** Every surveyed service of a comparison, sortable, with the best one highlighted (NF-P2-019). */
export default function ComparisonTable({ comparison }: ComparisonTableProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const [sort, setSort] = useState<SortState>({ column: "receives", direction: "desc" });
  const info = CORRIDORS[comparison.corridor_id];
  const sendMoney = (amount: number) =>
    formatMoney(amount, comparison.send_currency, language, info.decimals);
  const receiveMoney = (amount: number) =>
    formatMoney(amount, comparison.receive_currency, language, info.receiveDecimals);

  const rows = sortProviders(comparison.providers, sort);
  const comparableRows = rows.filter((provider) => provider.comparable);
  const notComparable = rows.filter((provider) => !provider.comparable);

  return (
    <section aria-labelledby="remittance-table-title" className="space-y-3">
      <h2 id="remittance-table-title" className="text-lg font-semibold">
        {t("remittance.table.heading")}
      </h2>

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <caption className="sr-only">{t("remittance.table.caption")}</caption>
          <thead>
            <tr className="border-b bg-muted/50">
              {COLUMNS.map(({ key, labelKey, align }) => {
                const active = sort.column === key;
                return (
                  <th
                    key={key}
                    scope="col"
                    aria-sort={
                      active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"
                    }
                  >
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => setSort((current) => nextSortState(current, key))}
                      className={cn(
                        "h-auto w-full gap-1 rounded-none px-3 py-2 font-medium",
                        align === "left" ? "justify-start" : "justify-end"
                      )}
                    >
                      {t(labelKey)}
                      <SortMark direction={active ? sort.direction : null} />
                    </Button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {comparableRows.map((provider, index) => (
              <ProviderRow
                key={provider.rpw_id}
                provider={provider}
                rank={index + 1}
                total={comparableRows.length}
                sendMoney={sendMoney}
                receiveMoney={receiveMoney}
              />
            ))}
          </tbody>
        </table>
      </div>

      {notComparable.length > 0 && (
        <div className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">
            {t("remittance.table.notComparable.heading")}
          </p>
          <p>
            {t("remittance.table.notComparable.note", {
              receiveCurrency: comparison.receive_currency,
            })}
          </p>
          <ul className="mt-2 space-y-1">
            {notComparable.map((provider) => (
              <li key={provider.rpw_id}>
                {t("remittance.table.notComparable.row", {
                  firm: provider.firm,
                  fee: sendMoney(provider.fee),
                  currency: provider.payout_currency,
                })}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

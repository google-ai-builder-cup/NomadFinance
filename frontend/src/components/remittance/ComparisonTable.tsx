import { Crown } from "lucide-react";
import { useState } from "react";

import FlaggedProviderBadge from "@/components/remittance/FlaggedProviderBadge";
import { Badge } from "@/components/ui/badge";
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
  /** Logs the transfer with this provider (NF-P3-016's "I used this" action). Omitted hides
   * the action entirely, e.g. while the worker's profile is still loading. */
  onLog?: (provider: ProviderResult) => void;
  /** `rpw_id` of the row whose log request is in flight; disables every row's button. */
  pendingRpwId?: number | null;
  /** Rows already logged this session: show a confirmation instead of the button. */
  loggedRpwIds?: ReadonlySet<number>;
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

interface RowProps {
  provider: ProviderResult;
  rank: number;
  total: number;
  /** The largest total cost in the comparison: every bar is drawn against it. */
  maxCost: number;
  sendMoney: (amount: number) => string;
  receiveMoney: (amount: number) => string;
  onLog?: (provider: ProviderResult) => void;
  pendingRpwId?: number | null;
  logged: boolean;
}

/** Fee and exchange-rate markup as one stacked bar, scaled to the dearest service, so cost reads
 * at a glance without a number. The numbers sit next to it. */
function CostBar({ provider, maxCost }: { provider: ProviderResult; maxCost: number }) {
  const { t } = useI18n();
  const scale = maxCost > 0 ? provider.total_cost / maxCost : 0;
  const fee = provider.total_cost > 0 ? provider.fee / provider.total_cost : 0;
  return (
    <div
      className="h-2 w-full min-w-[5rem] overflow-hidden rounded-full bg-muted"
      role="img"
      aria-label={t("remittance.table.costBar", {
        fee: `${Math.round(fee * 100)}%`,
        markup: `${Math.round((1 - fee) * 100)}%`,
      })}
    >
      <div className="flex h-full" style={{ width: `${Math.max(6, scale * 100)}%` }}>
        <span className="h-full bg-remit" style={{ width: `${fee * 100}%` }} />
        <span className="h-full flex-1 bg-gold" />
      </div>
    </div>
  );
}

function LogAction({
  provider,
  onLog,
  pendingRpwId,
  logged,
}: Pick<RowProps, "provider" | "onLog" | "pendingRpwId" | "logged">) {
  const { t } = useI18n();
  if (!onLog) {
    return null;
  }
  if (logged) {
    return (
      <p className="mt-1 text-xs font-semibold text-safe-ink">
        {t("remittance.table.logAction.logged")}
      </p>
    );
  }
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="mt-1.5 h-9 rounded-lg px-3 text-xs"
      disabled={pendingRpwId !== null && pendingRpwId !== undefined}
      onClick={() => onLog(provider)}
    >
      {pendingRpwId === provider.rpw_id
        ? t("remittance.table.logAction.logging")
        : t("remittance.table.logAction.useThis")}
    </Button>
  );
}

function BestBadge() {
  const { t } = useI18n();
  return (
    <Badge tone="gold" className="gap-1">
      <Crown className="h-3 w-3" aria-hidden="true" />
      {t("remittance.table.bestBadge")}
    </Badge>
  );
}

function ProviderRow(props: RowProps) {
  const { t } = useI18n();
  const { provider, rank, total, maxCost, sendMoney, receiveMoney } = props;
  const isBest = provider.rank === 1;

  return (
    <tr className={cn("border-b last:border-0", isBest && "bg-gold/10")}>
      <td className="px-3 py-3.5 align-top">
        <span className="sr-only">
          {t("remittance.table.rankSr", { rank: String(rank), count: String(total) })}
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-bold">{provider.firm}</span>
          {isBest && <BestBadge />}
          <FlaggedProviderBadge firm={provider.firm} />
        </div>
        <p className="text-xs text-muted-foreground">
          {provider.payment_instrument} → {provider.pickup_method}
        </p>
        <LogAction {...props} />
      </td>
      <td className="px-3 py-3.5 text-right align-top tabular-nums">{provider.speed}</td>
      <td className="px-3 py-3.5 text-right align-top tabular-nums">
        {sendMoney(provider.fee)}
        {provider.estimated && (
          <span className="block text-xs text-caution-ink">
            {t("remittance.table.estimatedTag")}
          </span>
        )}
      </td>
      <td className="min-w-[8rem] px-3 py-3.5 align-top">
        <div className="text-right tabular-nums">
          {provider.total_cost_pct.toLocaleString(i18n.resolvedLanguage ?? "en", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
          %
        </div>
        <div className="mt-1.5">
          <CostBar provider={provider} maxCost={maxCost} />
        </div>
      </td>
      <td className="px-3 py-3.5 text-right align-top tabular-nums">
        <span className={cn("font-bold", isBest && "text-gold-ink")}>
          {receiveMoney(provider.recipient_receives ?? 0)}
        </span>
        {!isBest && !!provider.less_than_best && (
          <span className="block text-xs text-danger-ink">
            {t("remittance.table.vsBest", { amount: receiveMoney(provider.less_than_best) })}
          </span>
        )}
      </td>
    </tr>
  );
}

/** The same row on a phone: a ranked card, so nothing needs a sideways scroll. */
function ProviderCard(props: RowProps) {
  const { t } = useI18n();
  const { provider, rank, total, maxCost, sendMoney, receiveMoney } = props;
  const isBest = provider.rank === 1;
  return (
    <li
      className={cn(
        "card-surface space-y-3 p-4",
        isBest && "border-gold/50 bg-gradient-to-br from-gold/15 via-card to-card"
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-extrabold",
            isBest ? "bg-gold text-navy" : "bg-muted text-muted-foreground"
          )}
        >
          {rank}
        </span>
        <div className="min-w-0 flex-1">
          <span className="sr-only">
            {t("remittance.table.rankSr", { rank: String(rank), count: String(total) })}
          </span>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-bold">{provider.firm}</span>
            {isBest && <BestBadge />}
            <FlaggedProviderBadge firm={provider.firm} />
          </div>
          <p className="text-xs text-muted-foreground">
            {provider.payment_instrument} → {provider.pickup_method}
          </p>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-muted-foreground">
            {t("remittance.table.columns.receives")}
          </dt>
          <dd className={cn("text-lg font-extrabold tabular-nums", isBest && "text-gold-ink")}>
            {receiveMoney(provider.recipient_receives ?? 0)}
          </dd>
        </div>
        <div className="text-right">
          <dt className="text-xs text-muted-foreground">
            {t("remittance.table.columns.totalCost")}
          </dt>
          <dd className="text-lg font-bold tabular-nums">
            {provider.total_cost_pct.toLocaleString(i18n.resolvedLanguage ?? "en", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
            %
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">{t("remittance.table.columns.fee")}</dt>
          <dd className="font-semibold tabular-nums">{sendMoney(provider.fee)}</dd>
        </div>
        <div className="text-right">
          <dt className="text-xs text-muted-foreground">{t("remittance.table.columns.speed")}</dt>
          <dd className="font-semibold">{provider.speed}</dd>
        </div>
      </dl>
      <CostBar provider={provider} maxCost={maxCost} />
      {!isBest && !!provider.less_than_best && (
        <p className="text-xs font-medium text-danger-ink">
          {t("remittance.table.vsBest", { amount: receiveMoney(provider.less_than_best) })}
        </p>
      )}
      <LogAction {...props} />
    </li>
  );
}

/** Every surveyed service of a comparison, sortable, with the best one highlighted in gold
 * (NF-P2-019). A table from md up, ranked cards on a phone. */
export default function ComparisonTable({
  comparison,
  onLog,
  pendingRpwId = null,
  loggedRpwIds,
}: ComparisonTableProps) {
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
  const maxCost = Math.max(0, ...comparableRows.map((provider) => provider.total_cost));
  const rowProps = (provider: ProviderResult, index: number): RowProps => ({
    provider,
    rank: index + 1,
    total: comparableRows.length,
    maxCost,
    sendMoney,
    receiveMoney,
    onLog,
    pendingRpwId,
    logged: loggedRpwIds?.has(provider.rpw_id) ?? false,
  });

  return (
    <section aria-labelledby="remittance-table-title" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="remittance-table-title" className="text-lg font-bold tracking-tight">
          {t("remittance.table.heading")}
        </h2>
        <p className="flex items-center gap-3 text-xs text-muted-foreground" aria-hidden="true">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-remit" />
            {t("remittance.table.columns.fee")}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-gold" />
            {t("remittance.table.legendMarkup")}
          </span>
        </p>
      </div>

      <ul className="space-y-3 md:hidden">
        {comparableRows.map((provider, index) => (
          <ProviderCard key={provider.rpw_id} {...rowProps(provider, index)} />
        ))}
      </ul>

      <div className="card-surface hidden overflow-x-auto md:block">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <caption className="sr-only">{t("remittance.table.caption")}</caption>
          <thead>
            <tr className="border-b bg-muted/60">
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
                        "h-auto min-h-11 w-full gap-1 rounded-none px-3 py-2 font-bold",
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
              <ProviderRow key={provider.rpw_id} {...rowProps(provider, index)} />
            ))}
          </tbody>
        </table>
      </div>

      {notComparable.length > 0 && (
        <div className="rounded-xl border border-dashed p-3 text-sm text-muted-foreground">
          <p className="font-bold text-foreground">{t("remittance.table.notComparable.heading")}</p>
          <p>
            {t("remittance.table.notComparable.note", {
              receiveCurrency: comparison.receive_currency,
            })}
          </p>
          <ul className="mt-2 space-y-1">
            {notComparable.map((provider) => (
              <li key={provider.rpw_id} className="flex flex-wrap items-center gap-x-2">
                {t("remittance.table.notComparable.row", {
                  firm: provider.firm,
                  fee: sendMoney(provider.fee),
                  currency: provider.payout_currency,
                })}
                <FlaggedProviderBadge firm={provider.firm} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

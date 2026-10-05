import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { BILL_CATEGORIES, INCOME_CATEGORIES, type BillEntry, type IncomeEntry } from "@/types/fib";
import { CATEGORY_CHART_COLORS } from "@/utils/fibChartColors";
import { currencyDecimals } from "@/utils/fibForm";
import { billsByCategory, incomeByCategory, type CategoryTotal } from "@/utils/fibTimeline";
import { formatMoney } from "@/utils/format";

export interface CategoryBreakdownProps {
  income: readonly IncomeEntry[];
  bills: readonly BillEntry[];
  /** `null` when there is no majority currency yet (no entries at all). */
  currency: string | null;
}

/** Shares of a total as a ring, in the same fixed category colours as the bars beside it. */
function Donut<C extends string>({
  rows,
  order,
  total,
}: {
  rows: readonly CategoryTotal<C>[];
  order: readonly C[];
  total: number;
}) {
  const r = 40;
  const circumference = 2 * Math.PI * r;
  let offset = 0;
  return (
    <svg viewBox="0 0 120 120" className="h-24 w-24 shrink-0" aria-hidden="true">
      <circle cx="60" cy="60" r={r} fill="none" stroke="hsl(var(--muted))" strokeWidth="18" />
      <g transform="rotate(-90 60 60)">
        {total > 0 &&
          rows.map((row) => {
            const length = (row.amount / total) * circumference;
            const slot = order.indexOf(row.category);
            const node = (
              <circle
                key={row.category}
                cx="60"
                cy="60"
                r={r}
                fill="none"
                stroke={CATEGORY_CHART_COLORS[slot % CATEGORY_CHART_COLORS.length]}
                strokeWidth="18"
                strokeDasharray={`${Math.max(0, length - 1.5)} ${circumference}`}
                strokeDashoffset={-offset}
              />
            );
            offset += length;
            return node;
          })}
      </g>
    </svg>
  );
}

function BreakdownList<C extends string>({
  title,
  rows,
  order,
  i18nPrefix,
  currency,
  language,
}: {
  title: string;
  rows: readonly CategoryTotal<C>[];
  order: readonly C[];
  i18nPrefix: string;
  currency: string;
  language: string;
}) {
  const { t } = useI18n();
  const total = rows.reduce((sum, row) => sum + row.amount, 0);
  const max = Math.max(...rows.map((row) => row.amount), 0);
  const decimals = currencyDecimals(currency);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4">
        <Donut rows={rows} order={order} total={total} />
        <h3 className="text-sm font-bold">{title}</h3>
      </div>
      <ul className="space-y-2.5">
        {rows.map((row) => {
          const slot = order.indexOf(row.category);
          const color = CATEGORY_CHART_COLORS[slot % CATEGORY_CHART_COLORS.length];
          const share = total > 0 ? row.amount / total : 0;
          return (
            <li key={row.category} className="space-y-1">
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="flex items-center gap-2 truncate">
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: color }}
                    aria-hidden="true"
                  />
                  {t(`${i18nPrefix}.${row.category}`)}
                </span>
                <span className="shrink-0 tabular-nums text-muted-foreground">
                  {formatMoney(row.amount, currency, language, decimals)} ·{" "}
                  {share.toLocaleString(language, { style: "percent", maximumFractionDigits: 0 })}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${max > 0 ? (row.amount / max) * 100 : 0}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Income and expenses broken down by category, trailing 12 months (NF-P3-017). Two separate
 * direct-labeled lists, each in its own type's fixed category order — never re-sorted by
 * amount, so a category keeps the same color and position every time this renders. */
export default function CategoryBreakdown({ income, bills, currency }: CategoryBreakdownProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const incomeRows = currency ? incomeByCategory(income, INCOME_CATEGORIES, currency) : [];
  const billRows = currency ? billsByCategory(bills, BILL_CATEGORIES, currency) : [];
  const empty = incomeRows.length === 0 && billRows.length === 0;

  return (
    <section aria-labelledby="fib-breakdown-title" className="card-surface space-y-5 p-5">
      <h2 id="fib-breakdown-title" className="text-lg font-bold tracking-tight">
        {t("fib.breakdown.heading")}
      </h2>

      {empty && <p className="text-sm text-muted-foreground">{t("fib.breakdown.empty")}</p>}

      {currency && incomeRows.length > 0 && (
        <BreakdownList
          title={t("fib.breakdown.income")}
          rows={incomeRows}
          order={INCOME_CATEGORIES}
          i18nPrefix="fib.categories.income"
          currency={currency}
          language={language}
        />
      )}

      {currency && billRows.length > 0 && (
        <BreakdownList
          title={t("fib.breakdown.expenses")}
          rows={billRows}
          order={BILL_CATEGORIES}
          i18nPrefix="fib.categories.bill"
          currency={currency}
          language={language}
        />
      )}
    </section>
  );
}

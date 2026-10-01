import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from "recharts";

import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import type { BillEntry, IncomeEntry } from "@/types/fib";
import { CHART_EXPENSE_COLOR, CHART_INCOME_COLOR } from "@/utils/fibChartColors";
import { currencyDecimals } from "@/utils/fibForm";
import { monthlyTotals, monthWindow, type MonthlyTotal } from "@/utils/fibTimeline";
import { formatMoney } from "@/utils/format";

export interface FinancialTimelineProps {
  income: readonly IncomeEntry[];
  bills: readonly BillEntry[];
  /** `null` when there is no majority currency yet (no entries at all). */
  currency: string | null;
}

function monthLabel(key: string, language: string): string {
  const [year, month] = key.split("-").map(Number);
  try {
    return new Intl.DateTimeFormat(language, { month: "short" }).format(
      new Date(Date.UTC(year, month - 1, 1))
    );
  } catch {
    return key;
  }
}

function ChartTooltip({
  active,
  payload,
  language,
  currency,
}: TooltipProps<number, string> & { language: string; currency: string }) {
  const { t } = useI18n();
  const row = payload?.[0]?.payload as MonthlyTotal | undefined;
  if (!active || !row) {
    return null;
  }
  const decimals = currencyDecimals(currency);
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <p className="font-medium">{monthLabel(row.month, language)}</p>
      <p className="tabular-nums" style={{ color: CHART_INCOME_COLOR }}>
        {t("fib.timeline.income")}: {formatMoney(row.income, currency, language, decimals)}
      </p>
      <p className="tabular-nums" style={{ color: CHART_EXPENSE_COLOR }}>
        {t("fib.timeline.expense")}: {formatMoney(row.expense, currency, language, decimals)}
      </p>
    </div>
  );
}

/** Income vs. expense (bills) each month, trailing 12 months, one axis since both share a
 * currency (NF-P3-017). Reads raw `income`/`bills` entries live, not the weekly profile. */
export default function FinancialTimeline({ income, bills, currency }: FinancialTimelineProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const monthKeys = useMemo(() => monthWindow(12, new Date()), []);
  const rows = useMemo(
    () => (currency ? monthlyTotals(income, bills, monthKeys, currency) : []),
    [income, bills, monthKeys, currency]
  );
  const hasData = rows.some((row) => row.income > 0 || row.expense > 0);

  return (
    <section aria-labelledby="fib-timeline-title" className="space-y-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="fib-timeline-title" className="text-lg font-semibold">
          {t("fib.timeline.heading")}
        </h2>
        {currency && hasData && (
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: CHART_INCOME_COLOR }}
                aria-hidden="true"
              />
              {t("fib.timeline.income")}
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: CHART_EXPENSE_COLOR }}
                aria-hidden="true"
              />
              {t("fib.timeline.expense")}
            </span>
          </div>
        )}
      </div>

      {(!currency || !hasData) && (
        <p className="text-sm text-muted-foreground">{t("fib.timeline.empty")}</p>
      )}

      {currency && hasData && (
        <>
          <div className="h-56 w-full" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 4, right: 8, left: 0, bottom: 0 }} barGap={2}>
                <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
                <XAxis
                  dataKey="month"
                  tickFormatter={(value: string) => monthLabel(value, language)}
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tickFormatter={(value: number) => formatMoney(value, currency, language, 0)}
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={64}
                />
                <Tooltip content={<ChartTooltip language={language} currency={currency} />} />
                <Bar
                  dataKey="income"
                  fill={CHART_INCOME_COLOR}
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="expense"
                  fill={CHART_EXPENSE_COLOR}
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* A table alternative to the chart above, for screen readers and printed pages. */}
          <table className="sr-only">
            <caption>{t("fib.timeline.heading")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("fib.timeline.tableMonth")}</th>
                <th scope="col">{t("fib.timeline.income")}</th>
                <th scope="col">{t("fib.timeline.expense")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.month}>
                  <td>{monthLabel(row.month, language)}</td>
                  <td>{formatMoney(row.income, currency, language, currencyDecimals(currency))}</td>
                  <td>
                    {formatMoney(row.expense, currency, language, currencyDecimals(currency))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}

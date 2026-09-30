import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from "recharts";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/hooks/useI18n";
import { useRemittanceTrends } from "@/hooks/useRemittance";
import i18n from "@/lib/i18n";
import { ApiError } from "@/services/apiClient";
import {
  TREND_DAYS,
  type RemittanceComparison,
  type TrendDays,
  type TrendPoint,
} from "@/types/remittance";
import { weekdayName } from "@/utils/format";

export interface TrendChartProps {
  comparison: RemittanceComparison;
}

const PERIOD_LABEL_KEY: Record<TrendDays, string> = {
  30: "remittance.trend.period.month",
  90: "remittance.trend.period.quarter",
  180: "remittance.trend.period.halfYear",
  365: "remittance.trend.period.year",
};

function shortDate(isoDate: string, language: string): string {
  try {
    return new Intl.DateTimeFormat(language, { month: "short", day: "numeric" }).format(
      new Date(isoDate)
    );
  } catch {
    return isoDate;
  }
}

function mediumDate(isoDate: string, language: string): string {
  try {
    return new Intl.DateTimeFormat(language, { dateStyle: "medium" }).format(new Date(isoDate));
  } catch {
    return isoDate;
  }
}

function formatRate(rate: number, language: string): string {
  return rate.toLocaleString(language, { maximumFractionDigits: 4 });
}

function formatPct(pct: number, language: string): string {
  const signed = pct.toLocaleString(language, {
    signDisplay: "exceptZero",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${signed}%`;
}

function ChartTooltip({
  active,
  payload,
  language,
  sendCurrency,
  receiveCurrency,
}: TooltipProps<number, string> & {
  language: string;
  sendCurrency: string;
  receiveCurrency: string;
}) {
  const point = payload?.[0]?.payload as TrendPoint | undefined;
  if (!active || !point) {
    return null;
  }
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <p className="font-medium">{mediumDate(point.date, language)}</p>
      <p className="tabular-nums text-muted-foreground">
        1 {sendCurrency} = {formatRate(point.rate, language)} {receiveCurrency}
      </p>
    </div>
  );
}

function PeriodPicker({
  value,
  onChange,
  disabled,
}: {
  value: TrendDays;
  onChange: (days: TrendDays) => void;
  disabled: boolean;
}) {
  const { t } = useI18n();
  return (
    <div
      role="group"
      aria-label={t("remittance.trend.periodLabel")}
      className="inline-flex rounded-md border p-0.5"
    >
      {TREND_DAYS.map((days) => (
        <Button
          key={days}
          type="button"
          size="sm"
          variant={value === days ? "default" : "ghost"}
          aria-pressed={value === days}
          disabled={disabled}
          onClick={() => onChange(days)}
          className="h-7 px-2.5 text-xs"
        >
          {t(PERIOD_LABEL_KEY[days])}
        </Button>
      ))}
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-7 w-full max-w-[220px]" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

/**
 * Historical mid-market rate chart and the weekday that is usually best to send on
 * (NF-P2-020), from `GET /remittance/trends` (NF-P2-015). One line: the title names it, so
 * no legend. Grid and axes stay recessive; the line and hover state use the app's own
 * `--primary` token, which already has real light and dark values.
 */
export default function TrendChart({ comparison }: TrendChartProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const [days, setDays] = useState<TrendDays>(90);
  const trends = useRemittanceTrends(comparison.corridor_id, days);
  const notLoaded =
    trends.isError && trends.error instanceof ApiError && trends.error.status === 404;

  return (
    <section aria-labelledby="remittance-trend-title" className="space-y-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="remittance-trend-title" className="text-lg font-semibold">
          {t("remittance.trend.heading")}
        </h2>
        <PeriodPicker value={days} onChange={setDays} disabled={trends.isPending} />
      </div>

      {trends.isPending && <ChartSkeleton />}

      {notLoaded && (
        <p className="text-sm text-muted-foreground">{t("remittance.trend.notLoaded")}</p>
      )}

      {trends.isError && !notLoaded && (
        <div role="alert" className="flex flex-col items-start gap-2 text-sm">
          <p className="text-destructive">{t("remittance.trend.loadError")}</p>
          <Button size="sm" variant="outline" onClick={() => void trends.refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      )}

      {trends.isSuccess && trends.data.points.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("remittance.trend.empty")}</p>
      )}

      {trends.isSuccess && trends.data.points.length > 0 && (
        <>
          {trends.data.summary && (
            <p className="text-sm text-muted-foreground">
              {t("remittance.trend.change", {
                pct: formatPct(trends.data.summary.change_pct, language),
                from: shortDate(trends.data.summary.first.date, language),
                to: shortDate(trends.data.summary.latest.date, language),
              })}
            </p>
          )}

          <div className="h-48 w-full" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={trends.data.points}
                margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
              >
                <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={(value: string) => shortDate(value, language)}
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  minTickGap={24}
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tickFormatter={(value: number) => formatRate(value, language)}
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={56}
                />
                <Tooltip
                  content={
                    <ChartTooltip
                      language={language}
                      sendCurrency={comparison.send_currency}
                      receiveCurrency={comparison.receive_currency}
                    />
                  }
                />
                <Line
                  type="monotone"
                  dataKey="rate"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, stroke: "hsl(var(--background))", strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* A table alternative to the chart above, for screen readers and printed pages. */}
          <table className="sr-only">
            <caption>{t("remittance.trend.heading")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("remittance.trend.tableDate")}</th>
                <th scope="col">{t("remittance.trend.tableRate")}</th>
              </tr>
            </thead>
            <tbody>
              {trends.data.points.map((point) => (
                <tr key={point.date}>
                  <td>{mediumDate(point.date, language)}</td>
                  <td>{formatRate(point.rate, language)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {trends.data.best_day ? (
            <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm">
              {t("remittance.trend.bestDay", {
                weekday: weekdayName(trends.data.best_day.weekday, language),
                pct: formatPct(trends.data.best_day.advantage_pct, language),
              })}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t(
                trends.data.best_day_reason === "not_enough_history"
                  ? "remittance.trend.noBestDay.notEnoughHistory"
                  : "remittance.trend.noBestDay.noClearPattern"
              )}
            </p>
          )}
        </>
      )}
    </section>
  );
}

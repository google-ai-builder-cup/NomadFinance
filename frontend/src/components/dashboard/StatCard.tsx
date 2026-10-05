import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { PILLAR_STYLES, type PillarKey } from "@/utils/pillars";

export type StatState = "loading" | "error" | "empty" | "ready";

export interface StatCardProps {
  label: string;
  icon: LucideIcon;
  pillar: PillarKey;
  state: StatState;
  /** Shown while `state` is "empty": what is missing, and where to go to fix it. */
  empty: { icon: LucideIcon; message: string; actionLabel: string; to: string };
  /** The figure and its supporting line, shown while `state` is "ready". */
  children: ReactNode;
}

/** One KPI tile. It has four honest states: a skeleton shaped like the figure, a plain error line,
 * a friendly empty state with a way forward (never a bare "0"), and the figure itself. */
export default function StatCard({
  label,
  icon: Icon,
  pillar,
  state,
  empty,
  children,
}: StatCardProps) {
  const { t } = useI18n();
  const style = PILLAR_STYLES[pillar];
  const EmptyIcon = empty.icon;
  return (
    <article
      aria-busy={state === "loading"}
      className="card-surface flex min-h-[10.5rem] flex-col gap-3 p-5"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-[11px] font-extrabold uppercase tracking-widest text-subtle">
          {label}
        </h3>
        <span
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
            style.tint,
            style.text
          )}
        >
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
      </div>
      {state === "loading" && (
        <div role="status" className="grid gap-2.5">
          <span className="sr-only">{t("common.loading")}</span>
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="h-4 w-full" />
        </div>
      )}
      {state === "error" && (
        <p role="alert" className="text-sm text-muted-foreground">
          {t("dashboard.widgets.loadError")}
        </p>
      )}
      {state === "empty" && (
        <div className="flex flex-1 flex-col items-start gap-3">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border-2 border-dashed text-subtle">
              <EmptyIcon className="h-5 w-5" aria-hidden="true" />
            </span>
            <p className="text-sm font-semibold leading-snug">{empty.message}</p>
          </div>
          <Link
            to={empty.to}
            className={cn(
              "mt-auto inline-flex min-h-11 items-center rounded-xl border px-4 text-sm font-bold transition-colors hover:bg-accent",
              style.text
            )}
          >
            {empty.actionLabel}
          </Link>
        </div>
      )}
      {state === "ready" && <div className="flex flex-1 flex-col gap-2">{children}</div>}
    </article>
  );
}

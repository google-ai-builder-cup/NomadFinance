import { ArrowRight, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";
import { PILLAR_STYLES, type PillarKey } from "@/utils/pillars";

export interface WidgetCardProps {
  icon: LucideIcon;
  title: string;
  to: string;
  openLabel: string;
  /** The pillar's accent colour for the icon tile and the top edge. */
  pillar: PillarKey;
  children: ReactNode;
}

/** The shared card chrome of every home dashboard widget (NF-P3-019): icon, pillar name, its
 * own content, and a link to the full pillar page. Each widget's body (`children`) handles
 * its own query's loading/empty/error state — the shell renders immediately regardless. */
export default function WidgetCard({
  icon: Icon,
  title,
  to,
  openLabel,
  pillar,
  children,
}: WidgetCardProps) {
  const style = PILLAR_STYLES[pillar];
  return (
    <div className="card-surface flex h-full flex-col gap-4 overflow-hidden p-5 text-card-foreground transition-shadow duration-base hover:shadow-md">
      <span className={cn("absolute inset-x-0 top-0 h-1", style.bar)} aria-hidden="true" />
      <div className="flex items-center gap-3">
        <span
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl shadow-sm",
            style.tile
          )}
        >
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <h3 className="text-base font-bold tracking-tight">{title}</h3>
      </div>
      <div className="flex-1">{children}</div>
      <Link
        to={to}
        className={cn(
          "group inline-flex min-h-11 items-center gap-1.5 self-start rounded-lg text-sm font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          style.text
        )}
      >
        {openLabel}
        <ArrowRight
          className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </Link>
    </div>
  );
}

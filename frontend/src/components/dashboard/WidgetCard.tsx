import { ArrowRight, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useI18n } from "@/hooks/useI18n";
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
  const { t } = useI18n();
  const style = PILLAR_STYLES[pillar];
  return (
    <div className="card-surface flex h-full flex-col gap-1.5 overflow-hidden p-3 text-card-foreground transition-shadow duration-base hover:shadow-md sm:gap-4 sm:p-5">
      <span className={cn("absolute inset-x-0 top-0 h-1", style.bar)} aria-hidden="true" />
      <div className="flex items-center gap-2 sm:gap-3">
        <span
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg shadow-sm sm:h-10 sm:w-10 sm:rounded-xl",
            style.tile
          )}
        >
          <Icon className="h-4 w-4 sm:h-5 sm:w-5" aria-hidden="true" />
        </span>
        <h3 className="min-w-0 text-sm font-bold leading-tight tracking-tight sm:text-base">
          {title}
        </h3>
      </div>
      {/* On a phone the body keeps to three lines and the first row of a list, so six cards stay
          within two screens; the full content is one tap away on the pillar's own page. */}
      <div className="min-w-0 flex-1 max-sm:[&_p]:line-clamp-3 max-sm:[&_ul>li:nth-child(n+2)]:hidden">
        {children}
      </div>
      <Link
        to={to}
        className={cn(
          "group inline-flex min-h-11 items-center gap-1.5 self-start rounded-lg text-sm font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          style.text
        )}
      >
        {/* On a phone a short "Open" is shown and the full name stays for screen readers, so a
            long label never makes the tile three lines taller than its neighbour. */}
        <span aria-hidden="true" className="sm:hidden">
          {t("dashboard.widgets.openShort")}
        </span>
        <span className="max-sm:sr-only">{openLabel}</span>
        <ArrowRight
          className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </Link>
    </div>
  );
}

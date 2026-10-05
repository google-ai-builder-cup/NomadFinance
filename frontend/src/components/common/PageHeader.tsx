import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import PillarIllustration from "@/components/visual/PillarIllustration";
import { cn } from "@/lib/utils";
import { PILLAR_STYLES, type PillarKey } from "@/utils/pillars";

export interface PageHeaderProps {
  pillar: PillarKey;
  icon: LucideIcon;
  title: string;
  description?: string;
  /** Buttons or links shown under the description. */
  actions?: ReactNode;
  /** Hide the illustration on pages that need the room (forms, long lists). */
  compact?: boolean;
  className?: string;
}

/** The band at the top of every pillar page: the pillar's own colour, icon tile, title, one line
 * of description and its illustration, so people always know which pillar they are in. */
export default function PageHeader({
  pillar,
  icon: Icon,
  title,
  description,
  actions,
  compact = false,
  className,
}: PageHeaderProps) {
  const style = PILLAR_STYLES[pillar];
  return (
    <header
      className={cn(
        "grid items-center gap-5 overflow-hidden rounded-2xl border p-5 shadow-sm md:p-7",
        style.band,
        !compact && "md:grid-cols-[minmax(0,1fr)_minmax(0,15rem)]",
        className
      )}
    >
      <div className="flex min-w-0 flex-col items-start gap-3">
        <span
          className={cn(
            "flex h-11 w-11 items-center justify-center rounded-xl shadow-sm",
            style.tile
          )}
        >
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <h1 className="text-2xl font-extrabold tracking-tight text-balance md:text-3xl">{title}</h1>
        {description && (
          <p className="max-w-[58ch] text-base text-muted-foreground">{description}</p>
        )}
        {actions && <div className="flex flex-wrap gap-2 pt-1">{actions}</div>}
      </div>
      {!compact && (
        <div className="hidden w-full max-w-[15rem] justify-self-end md:block" aria-hidden="false">
          <PillarIllustration pillar={pillar} />
        </div>
      )}
    </header>
  );
}

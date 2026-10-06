import { Check, Circle, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type TimelineStatus = "done" | "current" | "upcoming";

export interface TimelineItemProps {
  title: string;
  /** Free content under the title: a description, a checklist, links. */
  children?: ReactNode;
  /** Already formatted, e.g. "Week 3" or "12 Nov 2026". */
  timeLabel?: string;
  status?: TimelineStatus;
  /** Spoken status, e.g. "completed". Without it the marker is purely visual. */
  statusLabel?: string;
  /** Replaces the default marker (a tick when done, a dot otherwise). */
  icon?: LucideIcon;
  /** The last item draws no line below its marker. */
  isLast?: boolean;
  className?: string;
}

/** One entry of a vertical timeline. It is a list item: put several inside an `<ol>`. The marker
 * is on the start side and the connecting line follows it, so the whole item mirrors in
 * right-to-left. */
export default function TimelineItem({
  title,
  children,
  timeLabel,
  status = "upcoming",
  statusLabel,
  icon: Icon,
  isLast = false,
  className,
}: TimelineItemProps) {
  const Marker = Icon ?? (status === "done" ? Check : Circle);
  return (
    <li
      aria-current={status === "current" ? "step" : undefined}
      className={cn("relative ps-10", !isLast && "pb-6", className)}
    >
      {!isLast && (
        <span aria-hidden="true" className="absolute bottom-0 start-3.5 top-7 w-0.5 bg-border" />
      )}
      <span
        aria-hidden="true"
        className={cn(
          "absolute start-0 top-0 flex h-7 w-7 items-center justify-center rounded-full border-2",
          status === "done" && "border-primary bg-primary text-primary-foreground",
          status === "current" && "border-primary bg-card text-primary",
          status === "upcoming" && "border-input bg-card text-muted-foreground"
        )}
      >
        <Marker className="h-3.5 w-3.5" />
      </span>
      {timeLabel && <p className="text-xs font-semibold text-muted-foreground">{timeLabel}</p>}
      <h3 className="text-sm font-bold leading-snug">
        {title}
        {statusLabel && <span className="sr-only"> ({statusLabel})</span>}
      </h3>
      {children && <div className="mt-1 text-sm text-muted-foreground">{children}</div>}
    </li>
  );
}

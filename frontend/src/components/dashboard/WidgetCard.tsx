import { ArrowRight, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export interface WidgetCardProps {
  icon: LucideIcon;
  title: string;
  to: string;
  openLabel: string;
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
  children,
}: WidgetCardProps) {
  return (
    <div className="flex h-full flex-col gap-3 rounded-lg border bg-card p-5 text-card-foreground shadow-sm">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <h3 className="text-base font-semibold">{title}</h3>
      </div>

      <div className="flex-1">{children}</div>

      <Link
        to={to}
        className="group inline-flex items-center gap-1 rounded text-sm font-medium focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
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

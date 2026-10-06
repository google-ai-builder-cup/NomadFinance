import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  /** Usually a button or link that gets the user somewhere useful. */
  action?: ReactNode;
  /** A larger illustration (for example a PillarIllustration) shown instead of the icon tile. */
  illustration?: ReactNode;
  /** Heading level for the title, so the page's heading order stays correct. Defaults to 2. */
  headingLevel?: 2 | 3 | 4;
  className?: string;
}

export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  illustration,
  headingLevel = 2,
  className,
}: EmptyStateProps) {
  const Heading = `h${headingLevel}` as const;
  return (
    <div
      className={cn(
        "dotted flex flex-col items-center gap-3 rounded-2xl border border-dashed bg-card/60 p-8 text-center",
        className
      )}
    >
      {illustration ? (
        <div className="w-full max-w-[11rem]">{illustration}</div>
      ) : (
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent text-primary shadow-sm">
          <Icon className="h-7 w-7" aria-hidden="true" />
        </span>
      )}
      <Heading className="text-lg font-bold tracking-tight">{title}</Heading>
      <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
      {action}
    </div>
  );
}

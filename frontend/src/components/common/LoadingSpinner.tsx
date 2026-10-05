import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

export interface LoadingSpinnerProps {
  label: string;
  /** Centre in the whole viewport, for page-level loading. */
  fullScreen?: boolean;
  className?: string;
}

export default function LoadingSpinner({
  label,
  fullScreen = false,
  className,
}: LoadingSpinnerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-center justify-center gap-3 text-muted-foreground",
        fullScreen && "min-h-screen min-h-dvh",
        className
      )}
    >
      <Loader2 className="h-5 w-5 animate-spin text-primary" aria-hidden="true" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

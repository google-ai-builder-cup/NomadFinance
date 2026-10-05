import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

// shadcn/ui's skeleton, copied in as shadcn intends; not a package. The shimmer sweeps across
// the block and stops (a plain muted block) under prefers-reduced-motion.
function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("skeleton-shimmer rounded-md motion-safe:animate-shimmer", className)}
      {...props}
    />
  );
}

export { Skeleton };

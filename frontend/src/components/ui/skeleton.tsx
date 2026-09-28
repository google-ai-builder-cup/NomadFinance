import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

// shadcn/ui's skeleton, copied in as shadcn intends; not a package.
function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("rounded-md bg-muted motion-safe:animate-pulse", className)}
      {...props}
    />
  );
}

export { Skeleton };

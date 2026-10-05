import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/** shadcn's Card: a solid surface with a hairline border. `edge` adds the soft gradient outline
 * used on the hero and feature cards; body cards stay plain for legibility. */
export function Card({
  className,
  edge = false,
  ...props
}: HTMLAttributes<HTMLDivElement> & { edge?: boolean }) {
  return <div className={cn("card-surface", edge && "card-edge", className)} {...props} />;
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1.5 p-5", className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-base font-semibold tracking-tight", className)} {...props} />;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pt-0", className)} {...props} />;
}

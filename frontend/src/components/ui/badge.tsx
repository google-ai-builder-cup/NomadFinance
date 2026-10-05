import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold leading-5",
  {
    variants: {
      tone: {
        neutral: "border-transparent bg-muted text-muted-foreground",
        safe: "border-safe/25 bg-safe-tint text-safe-tint-ink",
        caution: "border-caution/30 bg-caution-tint text-caution-tint-ink",
        danger: "border-danger/25 bg-danger-tint text-danger-tint-ink",
        info: "border-info/25 bg-info-tint text-info-tint-ink",
        gold: "border-gold/40 bg-gold/15 text-gold-ink",
      },
    },
    defaultVariants: { tone: "neutral" },
  }
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

/** A small status pill. Colour is never the only signal: pair it with an icon or a word. */
export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export { badgeVariants };

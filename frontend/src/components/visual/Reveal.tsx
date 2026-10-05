import type { CSSProperties, ElementType, ReactNode } from "react";

import { useReveal } from "@/hooks/useReveal";
import { cn } from "@/lib/utils";

/** Fades its content up the first time it scrolls into view. `delay` staggers siblings in a
 * grid. Content is never left hidden when motion is reduced or IntersectionObserver is missing. */
export default function Reveal({
  as: Tag = "div",
  delay = 0,
  className,
  children,
}: {
  as?: ElementType;
  delay?: number;
  className?: string;
  children: ReactNode;
}) {
  const [ref, shown] = useReveal<HTMLElement>();
  const style: CSSProperties | undefined = delay ? { animationDelay: `${delay}ms` } : undefined;
  return (
    <Tag ref={ref} style={style} className={cn(shown ? "animate-fade-up" : "opacity-0", className)}>
      {children}
    </Tag>
  );
}

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Kicker, heading and optional lead paragraph shared by every landing section. */
export default function SectionHeading({
  id,
  kicker,
  title,
  lead,
  className,
  leadClassName,
}: {
  id: string;
  kicker: string;
  title: ReactNode;
  lead?: ReactNode;
  className?: string;
  leadClassName?: string;
}) {
  return (
    <div className={cn("mb-9 flex max-w-3xl flex-col gap-3.5", className)}>
      <p className="text-[12.5px] font-bold uppercase tracking-[0.12em] text-primary">{kicker}</p>
      <h2
        id={id}
        className="text-balance text-[clamp(1.75rem,3.6vw,2.75rem)] font-extrabold leading-[1.12] tracking-tight"
      >
        {title}
      </h2>
      {lead && (
        <p className={cn("max-w-[62ch] text-base text-muted-foreground md:text-lg", leadClassName)}>
          {lead}
        </p>
      )}
    </div>
  );
}

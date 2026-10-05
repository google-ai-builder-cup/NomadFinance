import { CircleAlert, CircleCheck, Info, TriangleAlert, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type RiskLevel = "safe" | "caution" | "danger" | "info";

const ICONS: Record<RiskLevel, LucideIcon> = {
  safe: CircleCheck,
  caution: TriangleAlert,
  danger: CircleAlert,
  info: Info,
};

/** The one risk badge: the same four states and colours for contract health, radar risk, alerts
 * and provider flags. It always carries an icon next to the label, so colour is never alone. */
export default function RiskBadge({
  level,
  children,
  className,
}: {
  level: RiskLevel;
  children: ReactNode;
  className?: string;
}) {
  const Icon = ICONS[level];
  return (
    <Badge tone={level} className={cn(className)}>
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {children}
    </Badge>
  );
}

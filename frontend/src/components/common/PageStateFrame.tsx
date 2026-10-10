import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import PageHeader from "@/components/common/PageHeader";
import type { PillarKey } from "@/utils/pillars";

export interface PageStateFrameProps {
  pillar: PillarKey;
  icon: LucideIcon;
  title: string;
  children: ReactNode;
}

/** A screen's loading or failed state under the screen's own header. Every state of a screen
 * starts from the same title, so a screen reader always has a page heading to begin with and the
 * layout does not jump when the data arrives. */
export default function PageStateFrame({ pillar, icon, title, children }: PageStateFrameProps) {
  return (
    <div className="space-y-5">
      <PageHeader pillar={pillar} icon={icon} title={title} compact />
      {children}
    </div>
  );
}

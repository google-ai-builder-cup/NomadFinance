import { type ReactNode, Suspense } from "react";
import { Navigate } from "react-router-dom";

import FlagGate from "@/components/common/FlagGate";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/hooks/useI18n";
import type { FeatureFlag } from "@/types/flags";

function ModuleSkeleton() {
  const { t } = useI18n();
  return (
    <div role="status" aria-busy="true" className="space-y-4">
      <span className="sr-only">{t("common.loading")}</span>
      <Skeleton className="h-28 w-full rounded-2xl" />
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-40 w-full rounded-2xl" />
    </div>
  );
}

export interface FlagRouteProps {
  flag: FeatureFlag;
  /** The module's page, a lazy component: its code is fetched only once the flag is known to be on. */
  children: ReactNode;
}

/**
 * Element of a route that exists only for users the flag is on for. A user it is off for is
 * sent back to the dashboard (replacing the entry, so Back does not return to a page that is
 * not theirs), and the module's code is never downloaded for them.
 */
export default function FlagRoute({ flag, children }: FlagRouteProps) {
  return (
    <FlagGate
      flag={flag}
      loading={<ModuleSkeleton />}
      fallback={<Navigate to="/dashboard" replace />}
    >
      <Suspense fallback={<ModuleSkeleton />}>{children}</Suspense>
    </FlagGate>
  );
}

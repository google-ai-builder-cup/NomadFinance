import type { ReactNode } from "react";

import { useFeatureFlag } from "@/hooks/useFeatureFlag";
import type { FeatureFlag } from "@/types/flags";

export interface FlagGateProps {
  flag: FeatureFlag;
  children: ReactNode;
  /** Shown until the backend has answered. Nothing by default, so no module flashes in. */
  loading?: ReactNode;
  /** Shown when the flag is off, or when the answer could not be read. Nothing by default. */
  fallback?: ReactNode;
}

/** Renders `children` only for a user the module's flag is on for. */
export default function FlagGate({
  flag,
  children,
  loading = null,
  fallback = null,
}: FlagGateProps) {
  const { enabled, isLoading } = useFeatureFlag(flag);
  if (isLoading) {
    return <>{loading}</>;
  }
  return <>{enabled ? children : fallback}</>;
}

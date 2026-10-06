import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/hooks/useAuth";
import { isApiConfigured } from "@/services/apiClient";
import { getFeatureFlags } from "@/services/featureFlagService";
import { ALL_FLAGS_OFF, type FeatureFlag, type FeatureFlags } from "@/types/flags";

export interface FeatureFlagsState {
  flags: FeatureFlags;
  /** True only during the first answer; a failed or refused call ends it with everything off. */
  isLoading: boolean;
}

/**
 * Which new modules are on for the signed-in user.
 *
 * Fails closed: until the backend has answered, and if it cannot be reached or does not know
 * the route (an older deployment), every module is off and nothing new is shown. A refetch
 * that fails keeps the last good answer, as the backend does with its own copy.
 */
export function useFeatureFlags(): FeatureFlagsState {
  const { user } = useAuth();
  const uid = user?.uid;
  const query = useQuery({
    // The uid is part of the key so one person's answer is never shown to the next account
    // that signs in on the same browser.
    queryKey: ["featureFlags", uid],
    queryFn: getFeatureFlags,
    enabled: uid !== undefined && isApiConfigured,
    // The backend keeps its own copy for 60 seconds, so asking more often learns nothing. A
    // flag changed in Firestore reaches an open app on its next focus or reconnect after that.
    staleTime: 60_000,
  });
  return { flags: query.data ?? ALL_FLAGS_OFF, isLoading: query.isLoading };
}

/** Whether one module is on, and whether the answer is still on its way. */
export function useFeatureFlag(flag: FeatureFlag): { enabled: boolean; isLoading: boolean } {
  const { flags, isLoading } = useFeatureFlags();
  return { enabled: flags[flag], isLoading };
}

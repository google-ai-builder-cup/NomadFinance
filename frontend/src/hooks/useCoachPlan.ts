import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { getCoachOverview, getCoachPlan } from "@/services/coachService";
import type { LanguageCode } from "@/types/enums";

/**
 * A stored plan in the app's language. A plan never changes, so it is read once per language; the
 * first read in a new language is translated by the server and can take a few seconds, so while it
 * loads the plan in the language already shown stays on screen (`isPlaceholderData`).
 */
export function useCoachPlan(planId: string, language: LanguageCode) {
  return useQuery({
    queryKey: ["coach", "plan", planId, language],
    queryFn: () => getCoachPlan(planId, language),
    placeholderData: keepPreviousData,
    staleTime: Infinity,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}

/** The newest plan and the open interview, to offer a worker the way back to their plan. */
export function useCoachOverview(enabled = true) {
  return useQuery({
    queryKey: ["coach", "overview"],
    queryFn: getCoachOverview,
    enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

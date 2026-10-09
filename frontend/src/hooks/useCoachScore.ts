import { useQuery } from "@tanstack/react-query";

import { getCoachSession } from "@/services/coachService";

/**
 * The server's copy of the session once the answers are confirmed: the score is there, and only
 * there (the turn stream does not carry it). Asked once the interview is at `plan`, and again only
 * when the worker presses "try again": a score that cannot be worked out right now (a missing
 * rate) is `null`, not an error.
 */
export function useCoachScore(sessionId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["coach", "score", sessionId],
    queryFn: () => getCoachSession(sessionId),
    enabled,
    staleTime: Infinity,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

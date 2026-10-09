import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useUiLanguage } from "@/hooks/useUiLanguage";
import { startCoachSession } from "@/services/coachService";

export const COACH_SESSION_KEY = ["coach", "session"] as const;

/**
 * The worker's open interview, started if there is none (asking twice gives the same one). A
 * query for its loading and retry states, but never refetched behind the chat's back: the chat
 * owns the session from then on, and leaving the screen drops it so a return starts from the
 * server's copy.
 */
export function useCoachSession() {
  const language = useUiLanguage();
  return useQuery({
    queryKey: COACH_SESSION_KEY,
    queryFn: () => startCoachSession(language),
    staleTime: Infinity,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

/** Close the open interview and start a new one (the session is full, over, or gone). */
export function useCoachRestart() {
  const client = useQueryClient();
  const language = useUiLanguage();
  return useMutation({
    mutationFn: () => startCoachSession(language, true),
    retry: false,
    meta: { inlineError: true },
    onSuccess: (session) => client.setQueryData(COACH_SESSION_KEY, session),
  });
}

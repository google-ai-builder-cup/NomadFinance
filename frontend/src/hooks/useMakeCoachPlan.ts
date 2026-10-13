import { useMutation } from "@tanstack/react-query";

import { trackCoachPlanCreated } from "@/lib/analytics";
import { createCoachPlan } from "@/services/coachService";
import type { CorridorId, LanguageCode } from "@/types/enums";

/**
 * Make the 90-day plan. A plan takes 20 to 40 seconds, so the call has a long allowance and the
 * screen shows progress; a worker who presses again while it runs gets the same plan, not a second
 * one (the server finds it by the answers). Errors are shown inline, never in a global toast.
 */
export function useMakeCoachPlan(sessionId: string, language: LanguageCode, timeoutMs?: number) {
  return useMutation({
    mutationFn: () => createCoachPlan(sessionId, language, timeoutMs),
    retry: false,
    meta: { inlineError: true },
    onSuccess: (plan) =>
      trackCoachPlanCreated({
        band: plan.score.band,
        corridorId: plan.corridor_id as CorridorId | undefined,
        language,
      }),
  });
}

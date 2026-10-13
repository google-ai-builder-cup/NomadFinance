import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/hooks/useAuth";
import { trackCoachCheckinAnswered } from "@/lib/analytics";
import { markNotificationRead } from "@/services/notificationService";
import { submitCoachCheckin } from "@/services/coachCheckinService";
import type { CheckinAnswers, CheckinMilestone } from "@/types/coachCheckin";
import { checkinNotificationId } from "@/utils/coachCheckin";

/** Send the answers of one check-in. The sheet shows a failure itself, so no global toast. */
export function useSubmitCheckin(planId: string, milestone: CheckinMilestone) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const uid = user?.uid;
  return useMutation({
    mutationFn: (answers: CheckinAnswers) => submitCoachCheckin(planId, milestone, answers),
    retry: false,
    meta: { inlineError: true },
    onSuccess: (result) => {
      // Only the first answers count: a second tap or another phone gets the stored ones back.
      if (!result.already_answered) {
        trackCoachCheckinAnswered(milestone);
      }
      if (uid === undefined) {
        return;
      }
      // Not awaited: Firestore holds a write until the server has it, so on a poor connection the
      // thank-you would wait for a feed tidy-up. If it fails the reminder stays "unread" in the
      // feed; the answers are saved, and that is what matters.
      void markNotificationRead(uid, checkinNotificationId(planId, milestone))
        .catch(() => undefined)
        .finally(() => queryClient.invalidateQueries({ queryKey: ["notifications"] }));
    },
  });
}

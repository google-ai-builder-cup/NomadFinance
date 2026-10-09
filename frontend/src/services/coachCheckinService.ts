import { apiRequest } from "@/services/apiClient";
import type { CheckinAnswers, CheckinMilestone, CheckinResult } from "@/types/coachCheckin";

/**
 * Send the answers to one check-in. The server keeps the first answers of a milestone, so a second
 * tap or a second phone changes nothing and gets the stored answers back (`already_answered`).
 */
export async function submitCoachCheckin(
  planId: string,
  milestone: CheckinMilestone,
  answers: CheckinAnswers
): Promise<CheckinResult> {
  const response = await apiRequest(
    `/api/v2/coach/plans/${encodeURIComponent(planId)}/checkins/${milestone}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    }
  );
  return (await response.json()) as CheckinResult;
}

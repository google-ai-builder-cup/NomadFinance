import type { CoachFailure } from "@/types/coach";
import {
  CHECKIN_MILESTONES,
  PACE_ANSWERS,
  PAY_ANSWERS,
  type CheckinAnswers,
  type CheckinMilestone,
  type CheckinQuestionId,
} from "@/types/coachCheckin";
import { ApiError } from "@/services/apiClient";
import { errorMessageKey } from "@/utils/errors";

export interface CheckinQuestion {
  id: CheckinQuestionId;
  /** The choices, in the order they are shown. */
  options: readonly string[];
}

/** The three questions, in the order they are asked. Their words are `checkin.*` in the `coach` strings. */
export const CHECKIN_QUESTIONS: readonly CheckinQuestion[] = [
  { id: "remittance", options: PACE_ANSWERS },
  { id: "savings", options: PACE_ANSWERS },
  { id: "pay", options: PAY_ANSWERS },
];

const MILESTONE_DAYS: Record<CheckinMilestone, number> = { d30: 30, d60: 60, d90: 90 };

export function milestoneDays(milestone: CheckinMilestone): number {
  return MILESTONE_DAYS[milestone];
}

/** The milestone a reminder's link names: `?m=30`, also written `d30`. Anything else is null. */
export function milestoneFromParam(param: string | null): CheckinMilestone | null {
  if (param === null) {
    return null;
  }
  return CHECKIN_MILESTONES.find((m) => m === param || String(MILESTONE_DAYS[m]) === param) ?? null;
}

/** The link the reminder carries (backend `checkin_job.py` writes the same one). */
export function checkinPath(planId: string, milestone: CheckinMilestone): string {
  return `/coach/checkin/${encodeURIComponent(planId)}?m=${MILESTONE_DAYS[milestone]}`;
}

/** The id of the reminder's notification, the same one the job writes, so answering can mark it read. */
export function checkinNotificationId(planId: string, milestone: CheckinMilestone): string {
  return `coach_checkin_${planId}_${milestone}`;
}

export function isComplete(answers: Partial<CheckinAnswers>): answers is CheckinAnswers {
  return CHECKIN_QUESTIONS.every(({ id }) => answers[id] !== undefined);
}

export interface CheckinErrorView {
  /** i18n key in the `coach` namespace (the shared `errors.*` keys resolve from there too). */
  messageKey: string;
  /** Whether the same answers can be sent again. */
  retry: boolean;
}

/**
 * What to tell a worker whose answers did not go through. The words are the check-in's own where
 * the chat's would be wrong ("the coach is busy", "your last message"), and the shared ones for a
 * lost connection, a lapsed sign-in or a server problem.
 */
export function checkinErrorView(failure: CoachFailure): CheckinErrorView {
  switch (failure.code) {
    case "checkin_not_due":
      return { messageKey: "checkin.error.notDue", retry: false };
    case "request_in_progress":
      return { messageKey: "checkin.error.inProgress", retry: true };
    case "validation_failed":
      return { messageKey: "checkin.error.invalid", retry: false };
    default:
      break;
  }
  if (failure.code === "not_found" || failure.status === 404) {
    return { messageKey: "checkin.error.notFound", retry: false };
  }
  return {
    messageKey: errorMessageKey(new ApiError(failure.status, failure.code)),
    retry: failure.status !== 401,
  };
}

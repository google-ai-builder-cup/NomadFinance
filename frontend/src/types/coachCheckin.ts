// The day 30, 60 and 90 check-in of a Coach plan, as docs/api/v2-coach.md defines it. The three
// questions are fixed choices: the API stores the choice, never a sentence the worker typed.

export const CHECKIN_MILESTONES = ["d30", "d60", "d90"] as const;
export type CheckinMilestone = (typeof CHECKIN_MILESTONES)[number];

export const PACE_ANSWERS = ["on_track", "behind", "not_yet"] as const;
export type PaceAnswer = (typeof PACE_ANSWERS)[number];

export const PAY_ANSWERS = ["full_on_time", "late_or_less", "not_paid"] as const;
export type PayAnswer = (typeof PAY_ANSWERS)[number];

export interface CheckinAnswers {
  /** Money sent home, compared with the plan. */
  remittance: PaceAnswer;
  /** Money saved, compared with the plan. */
  savings: PaceAnswer;
  /** Whether the employer pays in full and on time. */
  pay: PayAnswer;
}
export type CheckinQuestionId = keyof CheckinAnswers;

/** `PUT /coach/plans/{id}/checkins/{milestone}`: what is stored, which is the first answers when
 * the milestone was already answered. */
export interface CheckinResult {
  plan_id: string;
  milestone: CheckinMilestone;
  answers: CheckinAnswers;
  answered_at: string;
  already_answered: boolean;
}

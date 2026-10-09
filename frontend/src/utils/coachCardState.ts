import type { CoachOverview, CoachStage } from "@/types/coach";

export type OverviewPlan = NonNullable<CoachOverview["plan"]>;

// The interview's steps as the stepper counts them (`plan` is past the last one).
const STEPS: readonly CoachStage[] = [
  "intro",
  "income",
  "obligations",
  "debt",
  "savings",
  "review",
];
export const CARD_STEPS = STEPS.length;

/** What the home dashboard's Coach card offers. */
export type CoachCardState =
  | { kind: "start" }
  | { kind: "resume"; step: number; lastActive: string; plan: OverviewPlan | null }
  | { kind: "plan"; plan: OverviewPlan };

/** The step an interview is at, 1 to `CARD_STEPS`. Confirmed answers (`plan`) count as the last. */
function stepOf(stage: CoachStage): number {
  const index = STEPS.indexOf(stage);
  return index === -1 ? CARD_STEPS : index + 1;
}

/**
 * Start, Resume or View plan, from `GET /coach/overview`. An open session with no answer in it is
 * what opening the Coach page leaves behind, not an interview under way, so it does not make the
 * card say "Continue". A worker with a plan and an interview under way is offered both, the
 * interview first because it is the one waiting for them.
 */
export function coachCardState({ session, plan }: CoachOverview): CoachCardState {
  if (session !== null && session.turn_count > 0) {
    return { kind: "resume", step: stepOf(session.stage), lastActive: session.last_active, plan };
  }
  return plan === null ? { kind: "start" } : { kind: "plan", plan };
}

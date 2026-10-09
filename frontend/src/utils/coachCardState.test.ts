import { describe, expect, it } from "vitest";

import { jsonMocks } from "@/mocks/files";
import type { CoachOverview, CoachStage } from "@/types/coach";
import { CARD_STEPS, coachCardState } from "@/utils/coachCardState";

function overview(name: string): CoachOverview {
  return jsonMocks.get(name)?.body as CoachOverview;
}

const session = (stage: CoachStage, turns: number): NonNullable<CoachOverview["session"]> => ({
  id: "s_1",
  stage,
  language: "en",
  turn_count: turns,
  last_active: "2026-10-20T08:00:00Z",
});
const plan: NonNullable<CoachOverview["plan"]> = {
  id: "5a202702c922fc9b4fcf",
  created_at: "2026-10-20T09:08:30Z",
  score_total: 57,
  band: "getting_ready",
};

describe("the dashboard card's state", () => {
  it("says Start to a worker with nothing yet", () => {
    expect(coachCardState(overview("coach/overview-04-empty.json"))).toEqual({ kind: "start" });
  });

  it("says Continue to a worker in the middle of an interview, at the step it stopped", () => {
    expect(coachCardState(overview("coach/overview-01-active-session.json"))).toEqual({
      kind: "resume",
      step: 4,
      lastActive: "2026-10-20T08:06:30Z",
      plan: null,
    });
  });

  it("says View plan to a worker whose plan is made and who has no interview open", () => {
    const state = coachCardState(overview("coach/overview-02-plan-only.json"));

    expect(state.kind).toBe("plan");
  });

  it("does not take an open session with no answer in it for an interview under way", () => {
    // Opening the Coach page starts a session; the worker has not answered anything yet.
    expect(coachCardState({ session: session("intro", 0), plan: null })).toEqual({ kind: "start" });
    expect(coachCardState(overview("coach/overview-03-session-and-plan.json")).kind).toBe("plan");
  });

  it("offers both to a worker with a plan who has an interview under way, the interview first", () => {
    expect(coachCardState({ session: session("income", 2), plan })).toEqual({
      kind: "resume",
      step: 2,
      lastActive: "2026-10-20T08:00:00Z",
      plan,
    });
  });

  it.each([
    ["intro", 1],
    ["income", 2],
    ["obligations", 3],
    ["debt", 4],
    ["savings", 5],
    ["review", 6],
    // Confirmed answers are past the last step the stepper shows: the card counts it as the last.
    ["plan", CARD_STEPS],
  ] as const)("counts the %s stage as step %i", (stage, step) => {
    const state = coachCardState({ session: session(stage, 3), plan: null });

    expect(state).toMatchObject({ kind: "resume", step });
  });
});

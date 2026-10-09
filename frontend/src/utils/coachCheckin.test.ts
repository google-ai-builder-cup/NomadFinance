import { describe, expect, it } from "vitest";

import {
  CHECKIN_QUESTIONS,
  checkinErrorView,
  checkinNotificationId,
  checkinPath,
  isComplete,
  milestoneDays,
  milestoneFromParam,
} from "@/utils/coachCheckin";

describe("the milestone in a reminder's link", () => {
  it.each([
    ["30", "d30"],
    ["60", "d60"],
    ["90", "d90"],
    ["d30", "d30"],
    ["d90", "d90"],
  ])("reads ?m=%s as %s", (param, milestone) => {
    expect(milestoneFromParam(param)).toBe(milestone);
  });

  it.each([null, "", "0", "45", "120", "d45", "30days", "-30", "30.0"])(
    "reads %j as no milestone",
    (param) => {
      expect(milestoneFromParam(param)).toBeNull();
    }
  );

  it("writes the same link the backend's reminder carries", () => {
    // backend/app/services/coach/checkin_job.py: f"/coach/checkin/{plan_id}?m={days}"
    expect(checkinPath("5a202702c922fc9b4fcf", "d60")).toBe(
      "/coach/checkin/5a202702c922fc9b4fcf?m=60"
    );
    expect(milestoneDays("d90")).toBe(90);
  });

  it("names the reminder's notification as the backend does", () => {
    // checkin_job.py: f"coach_checkin_{plan_id}_{milestone}"
    expect(checkinNotificationId("5a202702c922fc9b4fcf", "d30")).toBe(
      "coach_checkin_5a202702c922fc9b4fcf_d30"
    );
  });
});

describe("the three questions", () => {
  it("are the remittance, savings and pay questions in that order, with three choices each", () => {
    expect(CHECKIN_QUESTIONS.map(({ id }) => id)).toEqual(["remittance", "savings", "pay"]);
    expect(CHECKIN_QUESTIONS.map(({ options }) => options.length)).toEqual([3, 3, 3]);
  });

  it("are complete only when all three are answered", () => {
    expect(isComplete({})).toBe(false);
    expect(isComplete({ remittance: "on_track", savings: "behind" })).toBe(false);
    expect(isComplete({ remittance: "on_track", savings: "behind", pay: "not_paid" })).toBe(true);
  });
});

describe("what a failed answer says", () => {
  it("tells a check-in that is not open yet apart from a plan that is not found", () => {
    expect(checkinErrorView({ code: "checkin_not_due", status: 409 })).toEqual({
      messageKey: "checkin.error.notDue",
      retry: false,
    });
    expect(checkinErrorView({ code: "not_found", status: 404 })).toEqual({
      messageKey: "checkin.error.notFound",
      retry: false,
    });
  });

  it("uses the check-in's own words, not the chat's, for a save in progress or answers refused", () => {
    expect(checkinErrorView({ code: "request_in_progress", status: 409 })).toEqual({
      messageKey: "checkin.error.inProgress",
      retry: true,
    });
    expect(checkinErrorView({ code: "validation_failed", status: 422 })).toEqual({
      messageKey: "checkin.error.invalid",
      retry: false,
    });
  });

  it("uses the shared words for a lost connection, a server problem and a lapsed sign-in", () => {
    expect(checkinErrorView({ code: "network", status: 0 })).toEqual({
      messageKey: "errors.offline",
      retry: true,
    });
    expect(checkinErrorView({ code: "internal_error", status: 500 }).messageKey).toBe(
      "errors.server"
    );
    expect(checkinErrorView({ code: "unauthenticated", status: 401 })).toEqual({
      messageKey: "errors.sessionExpired",
      retry: false,
    });
  });
});

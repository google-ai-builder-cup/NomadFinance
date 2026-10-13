// @vitest-environment jsdom
// The Coach funnel events a hook sends (NF-HR-015): when, and with what.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSubmitCheckin } from "@/hooks/useCoachCheckin";
import { useCoachRestart, useCoachSession } from "@/hooks/useCoachSession";
import { useMakeCoachPlan } from "@/hooks/useMakeCoachPlan";

const mocks = vi.hoisted(() => ({
  started: vi.fn(),
  created: vi.fn(),
  answered: vi.fn(),
  start: vi.fn(),
  makePlan: vi.fn(),
  checkin: vi.fn(),
}));

vi.mock("@/lib/analytics", () => ({
  trackCoachStarted: mocks.started,
  trackCoachPlanCreated: mocks.created,
  trackCoachCheckinAnswered: mocks.answered,
}));
vi.mock("@/services/coachService", () => ({
  startCoachSession: mocks.start,
  createCoachPlan: mocks.makePlan,
}));
vi.mock("@/services/coachCheckinService", () => ({ submitCoachCheckin: mocks.checkin }));
vi.mock("@/services/notificationService", () => ({ markNotificationRead: async () => undefined }));
vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ user: { uid: "alice" } }) }));
vi.mock("@/hooks/useUiLanguage", () => ({ useUiLanguage: () => "tl" }));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => vi.clearAllMocks());

describe("coach_started", () => {
  it("says whether the interview is new or the open one picked up again", async () => {
    mocks.start.mockResolvedValueOnce({ id: "s_1", resumed: false });
    const first = renderHook(() => useCoachSession(), { wrapper });
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true));
    mocks.start.mockResolvedValueOnce({ id: "s_1", resumed: true });
    const second = renderHook(() => useCoachSession(), { wrapper });
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true));

    expect(mocks.started.mock.calls).toEqual([
      ["new", "tl"],
      ["resumed", "tl"],
    ]);
  });

  it("is not sent when starting fails", async () => {
    mocks.start.mockRejectedValueOnce(new Error("offline"));
    const view = renderHook(() => useCoachSession(), { wrapper });
    await waitFor(() => expect(view.result.current.isError).toBe(true));

    expect(mocks.started).not.toHaveBeenCalled();
  });

  it("says restart when the worker starts over", async () => {
    mocks.start.mockResolvedValueOnce({ id: "s_2", resumed: false });
    const view = renderHook(() => useCoachRestart(), { wrapper });

    view.result.current.mutate();
    await waitFor(() => expect(view.result.current.isSuccess).toBe(true));

    expect(mocks.started).toHaveBeenCalledWith("restart", "tl");
  });
});

describe("coach_plan_created", () => {
  it("sends the band and the route of the plan, once, when it is made", async () => {
    mocks.makePlan.mockResolvedValueOnce({
      score: { band: "getting_ready", total: 57 },
      corridor_id: "SG-IN",
    });
    const view = renderHook(() => useMakeCoachPlan("s_1", "tl"), { wrapper });

    view.result.current.mutate();
    await waitFor(() => expect(view.result.current.isSuccess).toBe(true));

    expect(mocks.created).toHaveBeenCalledTimes(1);
    expect(mocks.created).toHaveBeenCalledWith({
      band: "getting_ready",
      corridorId: "SG-IN",
      language: "tl",
    });
  });

  it("is not sent when the plan could not be made", async () => {
    mocks.makePlan.mockRejectedValueOnce(new Error("busy"));
    const view = renderHook(() => useMakeCoachPlan("s_1", "tl"), { wrapper });

    view.result.current.mutate();
    await waitFor(() => expect(view.result.current.isError).toBe(true));

    expect(mocks.created).not.toHaveBeenCalled();
  });
});

describe("coach_checkin_answered", () => {
  const answers = { remittance: "on_track", savings: "behind", pay: "full_on_time" } as const;

  it("is sent for the first answers of a milestone", async () => {
    mocks.checkin.mockResolvedValueOnce({ already_answered: false });
    const view = renderHook(() => useSubmitCheckin("p_1", "d30"), { wrapper });

    view.result.current.mutate(answers);
    await waitFor(() => expect(view.result.current.isSuccess).toBe(true));

    expect(mocks.answered).toHaveBeenCalledWith("d30");
  });

  it("is not sent again when the stored answers come back", async () => {
    mocks.checkin.mockResolvedValueOnce({ already_answered: true });
    const view = renderHook(() => useSubmitCheckin("p_1", "d30"), { wrapper });

    view.result.current.mutate(answers);
    await waitFor(() => expect(view.result.current.isSuccess).toBe(true));

    expect(mocks.answered).not.toHaveBeenCalled();
  });
});

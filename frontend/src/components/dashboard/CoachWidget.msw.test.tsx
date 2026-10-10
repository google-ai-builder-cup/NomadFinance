// @vitest-environment jsdom
// The Coach's card on the home dashboard against the mock API (NF-FC-022): it says Start,
// Continue or View plan from what `GET /coach/overview` returns, and stays a way in when it cannot.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import CoachWidget from "@/components/dashboard/CoachWidget";
import { MODULE_ITEMS } from "@/components/layout/navItems";
import { setLanguage } from "@/lib/i18n";
import { replayOverview } from "@/mocks/coachTurns";
import { server, setupMockServer } from "@/mocks/server";
import type { CoachOverview, CoachStage } from "@/types/coach";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();
afterEach(async () => {
  cleanup();
  await setLanguage("en");
});

const COACH = MODULE_ITEMS.find(({ pillar }) => pillar === "coach")!;
const PLAN_ID = "5a202702c922fc9b4fcf";

function renderCard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <CoachWidget item={COACH} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function replay(body: CoachOverview) {
  server.use(http.get("*/api/v2/coach/overview", () => HttpResponse.json(body)));
}

const hoursAgo = (hours: number) => new Date(Date.now() - hours * 3_600_000).toISOString();
const plan = {
  id: PLAN_ID,
  created_at: "2026-10-20T09:08:30Z",
  score_total: 57,
  band: "getting_ready",
};
const session = (stage: CoachStage) => ({
  id: "s_02",
  stage,
  language: "en" as const,
  turn_count: 6,
  last_active: hoursAgo(2),
});

describe("the Coach card", () => {
  it("is the plain pitch with a way in while the overview loads", () => {
    replayOverview("coach/overview-04-empty.json");

    renderCard();

    expect(screen.getByText(/Talk through your money/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /Open the Coach/ }).getAttribute("href")).toBe(
      "/coach"
    );
  });

  it("says Start to a worker with no interview and no plan", async () => {
    replayOverview("coach/overview-04-empty.json");

    renderCard();

    const link = await screen.findByRole("link", { name: /Start my interview/ });
    expect(link.getAttribute("href")).toBe("/coach");
    expect(screen.getByText(/Talk through your money/)).toBeTruthy();
  });

  it("says Continue to a worker in the middle of an interview, with the step and when they stopped", async () => {
    replay({ session: session("debt"), plan: null });

    renderCard();

    const link = await screen.findByRole("link", { name: /Continue my interview/ });
    expect(link.getAttribute("href")).toBe("/coach");
    expect(screen.getByText("Step 4 of 6")).toBeTruthy();
    expect(
      screen.getByText(/Your last answer was 2 hours ago\. Your answers are saved\./)
    ).toBeTruthy();
    expect(screen.queryByRole("link", { name: /View my plan/ })).toBeNull();
  });

  it("says View plan to a worker with a plan, linking to that plan", async () => {
    replayOverview("coach/overview-02-plan-only.json");

    renderCard();

    const link = await screen.findByRole("link", { name: /View my plan/ });
    expect(link.getAttribute("href")).toBe(`/coach/plan/${PLAN_ID}`);
    expect(screen.getByText("Your 90-day plan is ready.")).toBeTruthy();
    expect(screen.getByText("Score 57 out of 100: Getting ready.")).toBeTruthy();
  });

  it("offers both to a worker with a plan and an interview under way, the interview first", async () => {
    replay({ session: session("savings"), plan });

    renderCard();

    const interview = await screen.findByRole("link", { name: "Continue my interview" });
    const viewPlan = screen.getByRole("link", { name: "View my plan" });
    expect(screen.getAllByRole("link")).toHaveLength(2);
    expect(viewPlan.getAttribute("href")).toBe(`/coach/plan/${PLAN_ID}`);
    expect(interview.getAttribute("href")).toBe("/coach");
    // The plan link sits in the card's body, above the card's own link.
    expect(
      viewPlan.compareDocumentPosition(interview) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(screen.getByText("Step 5 of 6")).toBeTruthy();
  });

  it("does not call an untouched session an interview under way", async () => {
    replayOverview("coach/overview-03-session-and-plan.json");

    renderCard();

    expect(await screen.findByRole("link", { name: /View my plan/ })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Continue my interview/ })).toBeNull();
  });

  it("leaves a band it does not know out of the sentence", async () => {
    replay({ session: null, plan: { ...plan, band: "brand_new_band" } });

    renderCard();

    expect(await screen.findByText("Score 57 out of 100.")).toBeTruthy();
  });

  it("stays the plain pitch with its way in when the overview cannot be read", async () => {
    server.use(
      http.get("*/api/v2/coach/overview", () =>
        HttpResponse.json({ code: "internal_error" }, { status: 500 })
      )
    );

    renderCard();

    // The failed read must not take the card away: wait until it has settled, then check.
    await vi.waitFor(() =>
      expect(screen.getByRole("link", { name: /Open the Coach/ })).toBeTruthy()
    );
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.getByText(/Talk through your money/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /Open the Coach/ }).getAttribute("href")).toBe(
      "/coach"
    );
  });

  it("is written in the language of the app", async () => {
    await setLanguage("hi");
    replayOverview("coach/overview-02-plan-only.json");

    renderCard();

    const link = await screen.findByRole("link", { name: "मेरी योजना देखें" });
    expect(link.getAttribute("href")).toBe(`/coach/plan/${PLAN_ID}`);
    expect(screen.getByText("स्कोर 57 / 100: तैयारी हो रही है।")).toBeTruthy();
  });
});

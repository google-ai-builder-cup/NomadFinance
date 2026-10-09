// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import PlanButton from "@/components/coach/score/PlanButton";
import { loadNamespace } from "@/lib/i18n";
import { replayPlan } from "@/mocks/coachTurns";
import { setupMockServer } from "@/mocks/server";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(cleanup);

describe("the wait for a plan", () => {
  it("says it takes up to a minute, then that it is still working if it takes longer", async () => {
    replayPlan("coach/plan-01-created.json", 500);
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <PlanButton sessionId="s_01" language="en" slowAfterMs={100} />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await user.click(screen.getByRole("button", { name: "Make my 90-day plan" }));

    expect(screen.getByRole("status").textContent).toMatch(/takes up to a minute/);
    expect(await screen.findByText(/Still working/)).toBeTruthy();
    await screen.findByText("Your plan is ready");
  });
});

describe("a plan that was made", () => {
  it("links to the plan page by the plan's id", async () => {
    replayPlan("coach/plan-01-created.json");
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <PlanButton sessionId="s_01" language="en" />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await user.click(screen.getByRole("button", { name: "Make my 90-day plan" }));

    const link = await screen.findByRole("link", { name: "View my plan" });
    expect(link.getAttribute("href")).toMatch(/^\/coach\/plan\/[0-9a-f]{20}$/);
    expect(screen.queryByRole("button", { name: "Make my 90-day plan" })).toBeNull();
  });
});

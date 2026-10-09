// @vitest-environment jsdom
// `/coach/plan/:planId` is behind the `coach` flag like `/coach` (NF-FC-021): a worker it is off
// for goes back to the dashboard and the plan page is never loaded.
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import CoachPlanRoute from "@/pages/coach/CoachPlanRoute";

const state = vi.hoisted(() => ({ enabled: false, isLoading: false, pageRendered: vi.fn() }));

vi.mock("@/hooks/useFeatureFlag", () => ({
  useFeatureFlag: () => ({ enabled: state.enabled, isLoading: state.isLoading }),
}));
vi.mock("@/pages/coach/CoachPlanPage", () => ({
  default: function Page() {
    state.pageRendered();
    return <p>The plan page</p>;
  },
}));

beforeEach(() => {
  state.enabled = false;
  state.isLoading = false;
  state.pageRendered.mockClear();
});
afterEach(cleanup);

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/coach/plan/5a202702c922fc9b4fcf"]}>
      <Routes>
        <Route path="/coach/plan/:planId" element={<CoachPlanRoute />} />
        <Route path="/dashboard" element={<p>The dashboard</p>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("the plan route", () => {
  it("sends a worker the flag is off for to the dashboard, without loading the page", async () => {
    renderRoute();

    expect(await screen.findByText("The dashboard")).toBeTruthy();
    expect(state.pageRendered).not.toHaveBeenCalled();
  });

  it("shows the plan page when the flag is on", async () => {
    state.enabled = true;

    renderRoute();

    expect(await screen.findByText("The plan page")).toBeTruthy();
    expect(screen.queryByText("The dashboard")).toBeNull();
  });
});

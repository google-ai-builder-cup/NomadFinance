// @vitest-environment jsdom
// `/coach/checkin/:planId` is behind the `coach` flag like `/coach` (NF-FC-022): a worker it is off
// for goes back to the dashboard and the check-in page is never loaded.
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import CoachCheckinRoute from "@/pages/coach/CoachCheckinRoute";

const state = vi.hoisted(() => ({ enabled: false, isLoading: false, pageRendered: vi.fn() }));

vi.mock("@/hooks/useFeatureFlag", () => ({
  useFeatureFlag: () => ({ enabled: state.enabled, isLoading: state.isLoading }),
}));
vi.mock("@/pages/coach/CoachCheckinPage", () => ({
  default: function Page() {
    state.pageRendered();
    return <p>The check-in page</p>;
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
    <MemoryRouter initialEntries={["/coach/checkin/5a202702c922fc9b4fcf?m=30"]}>
      <Routes>
        <Route path="/coach/checkin/:planId" element={<CoachCheckinRoute />} />
        <Route path="/dashboard" element={<p>The dashboard</p>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("the check-in route", () => {
  it("sends a worker the flag is off for to the dashboard, without loading the page", async () => {
    renderRoute();

    expect(await screen.findByText("The dashboard")).toBeTruthy();
    expect(state.pageRendered).not.toHaveBeenCalled();
  });

  it("shows the check-in page when the flag is on", async () => {
    state.enabled = true;

    renderRoute();

    expect(await screen.findByText("The check-in page")).toBeTruthy();
    expect(screen.queryByText("The dashboard")).toBeNull();
  });
});

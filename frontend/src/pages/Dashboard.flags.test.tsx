// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import Dashboard from "@/pages/Dashboard";

const state = vi.hoisted(() => ({ flags: { coach: false, scam: false } }));

vi.mock("@/hooks/useFeatureFlag", () => ({
  useFeatureFlags: () => ({ flags: state.flags, isLoading: false }),
}));
// The other cards read the API and Firestore; this test is about which cards there are.
vi.mock("@/components/dashboard/GreetingBand", () => ({ default: () => null }));
vi.mock("@/components/dashboard/KpiRow", () => ({ default: () => null }));
vi.mock("@/components/dashboard/RemittanceShortcutWidget", () => ({ default: () => null }));
vi.mock("@/components/dashboard/RecentContractsWidget", () => ({ default: () => null }));
vi.mock("@/components/dashboard/RadarAlertsWidget", () => ({ default: () => null }));
vi.mock("@/components/dashboard/FIBProgressWidget", () => ({ default: () => null }));
vi.mock("@/components/visual/Reveal", () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

beforeEach(() => {
  state.flags = { coach: false, scam: false };
});
afterEach(cleanup);

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  );
}

describe("the dashboard's Future Scope cards", () => {
  it("shows none to a worker both modules are off for", () => {
    renderDashboard();

    expect(screen.queryByRole("link", { name: /Check a message/ })).toBeNull();
    expect(screen.queryByRole("link", { name: /Open the Coach/ })).toBeNull();
  });

  it("shows the Scam Check card, linking to its page, when its flag is on", () => {
    state.flags = { coach: false, scam: true };

    renderDashboard();

    expect(screen.getByText("Scam Check")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Check a message/ }).getAttribute("href")).toBe(
      "/scam-check"
    );
    expect(screen.queryByText("Financial Coach")).toBeNull();
  });

  it("shows both when both are on", () => {
    state.flags = { coach: true, scam: true };

    renderDashboard();

    expect(screen.getByRole("link", { name: /Open the Coach/ }).getAttribute("href")).toBe(
      "/coach"
    );
    expect(screen.getByRole("link", { name: /Check a message/ })).toBeTruthy();
  });
});

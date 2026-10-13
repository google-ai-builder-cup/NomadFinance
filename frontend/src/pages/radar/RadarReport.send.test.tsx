// @vitest-environment jsdom
// "Send report" (QA-C-01, NF-HR-006): two taps in the same instant send one report, not two.
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import RadarReport from "@/pages/radar/RadarReport";

const state = vi.hoisted(() => ({ mutate: vi.fn() }));

vi.mock("@/hooks/useRadar", () => ({
  useSubmitReport: () => ({
    mutate: state.mutate,
    isPending: false,
    isError: false,
    error: null,
    data: undefined,
    reset: vi.fn(),
  }),
}));
vi.mock("@/hooks/useUser", () => ({
  useUserProfile: () => ({
    isPending: false,
    isError: false,
    data: { host_country: "SG", home_country: "IN", preferred_language: "en" },
  }),
}));
// The form is not what this test is about: a button that submits twice at once.
vi.mock("@/components/radar/ReportForm", () => ({
  default: ({ onSubmit }: { onSubmit: (report: unknown, files: File[]) => void }) => (
    <button
      type="button"
      onClick={() => {
        onSubmit({ description: "a fee at the counter" }, []);
        onSubmit({ description: "a fee at the counter" }, []);
      }}
    >
      send twice
    </button>
  ),
}));

beforeEach(() => state.mutate.mockClear());
afterEach(cleanup);

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/radar/report"]}>
      <RadarReport />
    </MemoryRouter>
  );
}

describe("sending a report", () => {
  it("sends one request for two taps in the same instant", async () => {
    renderPage();

    await userEvent.setup().click(screen.getByRole("button", { name: "send twice" }));

    expect(state.mutate).toHaveBeenCalledTimes(1);
  });

  it("lets the worker send again once the request has failed", async () => {
    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "send twice" }));
    const callbacks = state.mutate.mock.calls[0][1] as { onSettled: () => void };

    callbacks.onSettled();
    await user.click(screen.getByRole("button", { name: "send twice" }));

    expect(state.mutate).toHaveBeenCalledTimes(2);
  });
});

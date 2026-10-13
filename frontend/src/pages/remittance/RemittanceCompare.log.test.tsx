// @vitest-environment jsdom
// "I used this" (QA-B-03, NF-HR-005): two taps in the same instant log one transfer, not two.
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import RemittanceCompare from "@/pages/remittance/RemittanceCompare";

const state = vi.hoisted(() => ({
  log: vi.fn(),
  comparison: {
    corridor_id: "SG-IN",
    send_amount: 500,
    providers: [{ rpw_id: 7, firm: "Wise" }],
  },
}));

vi.mock("@/hooks/useRemittance", () => ({
  useCompareRemittance: () => ({
    mutate: vi.fn(),
    data: state.comparison,
    isPending: false,
    isError: false,
    error: null,
    variables: undefined,
  }),
  useLogTransfer: () => ({ mutate: state.log, isPending: false, variables: undefined }),
}));
vi.mock("@/hooks/useUser", () => ({
  useUserProfile: () => ({ isPending: false, data: { host_country: "SG", home_country: "IN" } }),
}));
// The table is the only piece this test is about: a button that taps its log action twice at once.
vi.mock("@/components/remittance/ComparisonTable", () => ({
  default: ({ onLog }: { onLog: (provider: { rpw_id: number }) => void }) => (
    <button
      type="button"
      onClick={() => {
        onLog({ rpw_id: 7 });
        onLog({ rpw_id: 7 });
      }}
    >
      tap twice
    </button>
  ),
}));
vi.mock("@/components/remittance/ComparisonSummary", () => ({ default: () => null }));
vi.mock("@/components/remittance/RecommendationCard", () => ({ default: () => null }));
vi.mock("@/components/remittance/SavingsCallout", () => ({ default: () => null }));
vi.mock("@/components/remittance/TrendChart", () => ({ default: () => null }));

beforeEach(() => state.log.mockClear());
afterEach(cleanup);

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/remittance"]}>
      <RemittanceCompare />
    </MemoryRouter>
  );
}

describe("logging a transfer", () => {
  it("sends one request for two taps in the same instant", async () => {
    renderPage();

    await userEvent.setup().click(screen.getByRole("button", { name: "tap twice" }));

    expect(state.log).toHaveBeenCalledTimes(1);
    expect(state.log.mock.calls[0][0]).toMatchObject({ rpwId: 7 });
  });

  it("lets the worker try again once the request has failed", async () => {
    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "tap twice" }));
    const callbacks = state.log.mock.calls[0][1] as { onSettled: () => void };

    callbacks.onSettled();
    await user.click(screen.getByRole("button", { name: "tap twice" }));

    expect(state.log).toHaveBeenCalledTimes(2);
  });
});

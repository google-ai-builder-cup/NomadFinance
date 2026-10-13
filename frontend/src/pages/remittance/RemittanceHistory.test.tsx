// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import RemittanceHistory from "@/pages/remittance/RemittanceHistory";

const state = vi.hoisted(() => ({
  result: { isPending: false, isError: false, data: [] as unknown[], refetch: vi.fn() },
}));

vi.mock("@/hooks/useRemittance", () => ({ useLoggedTransfers: () => state.result }));

afterEach(cleanup);

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/remittance/history"]}>
      <RemittanceHistory />
    </MemoryRouter>
  );
}

describe("RemittanceHistory", () => {
  it("lists what was logged, newest first, with what was sent and what arrived", () => {
    state.result = {
      ...state.result,
      data: [
        {
          id: "t2",
          entry_date: "2026-10-12",
          corridor_id: "SG-IN",
          provider_name: "Wise",
          send_amount: 500,
          send_currency: "SGD",
          receive_amount: 30800,
          receive_currency: "INR",
        },
        {
          id: "t1",
          entry_date: "2026-09-12",
          corridor_id: "SG-IN",
          provider_name: "Remitly",
          send_amount: 400,
          send_currency: "SGD",
          receive_amount: 24500,
          receive_currency: "INR",
        },
      ],
    };

    renderPage();

    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain("Wise");
    expect(rows[0].textContent).toContain("SG → IN");
    expect(rows[1].textContent).toContain("Remitly");
  });

  it("says how a transfer gets here when none is logged", () => {
    state.result = { ...state.result, data: [] };

    renderPage();

    expect(screen.getByText("No transfers logged yet")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Compare services" }).getAttribute("href")).toBe(
      "/remittance"
    );
  });

  it("offers to try again when the list cannot be read", () => {
    state.result = { ...state.result, isError: true };

    renderPage();

    expect(screen.getByRole("alert").textContent).toContain("We could not load your transfers");
  });
});

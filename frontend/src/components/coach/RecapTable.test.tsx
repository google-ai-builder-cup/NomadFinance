// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import RecapTable from "@/components/coach/RecapTable";
import { loadNamespace } from "@/lib/i18n";

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(cleanup);

const SLOTS = {
  destination_country: "SG",
  job_type: "domestic_worker",
  departure_date: "2026-12-31",
  monthly_salary: { amount: 650, currency: "SGD", period: "month" },
  dependents: 4,
  remittance_target: { amount: 500, currency: "SGD", period: "month" },
  recruitment_fee_paid: { amount: 300000, currency: "INR", period: "once" },
  debt_outstanding: { amount: 0, currency: "INR", period: "once" },
  savings: { amount: 1200, currency: "SGD", period: "once" },
  bank_or_wallet: "bank_account",
};

describe("RecapTable", () => {
  it("is a table of the answers, each row a question and its answer", () => {
    render(<RecapTable slots={SLOTS} busy={false} onChange={vi.fn()} />);

    const table = screen.getByRole("table", { name: "Your answers, one row for each question" });
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((cell) => cell.textContent)
    ).toEqual(["Question", "Your answer", "Change an answer"]);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(10);
    const pay = rows[3] as HTMLElement;
    expect(within(pay).getByRole("rowheader").textContent).toBe("Your pay");
    expect(within(pay).getByRole("cell", { name: "650 SGD per month" })).toBeTruthy();
    expect(within(rows[7] as HTMLElement).getByRole("cell", { name: "None (0)" })).toBeTruthy();
    expect(screen.getByText("December 31, 2026")).toBeTruthy();
  });

  it("names the answer on each Change button, and sends a sentence that names it", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<RecapTable slots={SLOTS} busy={false} onChange={onChange} />);

    await user.click(screen.getByRole("button", { name: "Change: Your pay" }));

    expect(onChange).toHaveBeenCalledWith("I want to change my answer about: Your pay.");
  });

  it("cannot be changed while a turn is running", () => {
    render(<RecapTable slots={SLOTS} busy onChange={vi.fn()} />);

    for (const button of screen.getAllByRole("button")) {
      expect((button as HTMLButtonElement).disabled).toBe(true);
    }
  });
});

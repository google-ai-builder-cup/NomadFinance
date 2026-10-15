// @vitest-environment jsdom
// The link from the Coach's plan into Remittance X-Ray (NF-FC-021): the form opens with the
// corridor and the amount filled in, and the comparison runs once.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import RemittanceCompare from "@/pages/remittance/RemittanceCompare";

const compare = vi.hoisted(() => ({ mutate: vi.fn() }));

vi.mock("@/hooks/useRemittance", () => ({
  useCompareRemittance: () => ({
    mutate: compare.mutate,
    data: undefined,
    isPending: false,
    isError: false,
    error: null,
    variables: undefined,
  }),
  useLogTransfer: () => ({ mutate: vi.fn(), isPending: false, variables: undefined }),
}));
vi.mock("@/hooks/useUser", () => ({
  useUserProfile: () => ({
    isPending: false,
    data: { host_country: "SG", home_country: "PH" },
  }),
}));

beforeEach(() => compare.mutate.mockClear());
afterEach(cleanup);

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <RemittanceCompare />
    </MemoryRouter>
  );
}

const amountField = () => document.getElementById("remittance-amount") as HTMLInputElement;
const chosenCorridor = () =>
  screen
    .getAllByRole("radio")
    .filter((radio) => radio.getAttribute("aria-checked") === "true")
    .map((radio) => radio.textContent);

describe("opened from a plan", () => {
  it("shows the amount and runs the comparison once for the corridor in the link", () => {
    renderAt("/remittance?corridor=AU-IN&amount=900");

    expect(amountField().value).toBe("900");
    expect(compare.mutate).toHaveBeenCalledTimes(1);
    expect(compare.mutate).toHaveBeenCalledWith({ corridor_id: "AU-IN", amount: 900 });
  });

  it("starts on the corridor of the link, not the one of the profile", () => {
    renderAt("/remittance?corridor=AU-IN&amount=900");

    expect(chosenCorridor()).toHaveLength(1);
    expect(chosenCorridor()[0]).toContain("AUD→INR");
  });

  it("does not run it again when the page renders again", () => {
    const view = renderAt("/remittance?corridor=AU-IN&amount=900");

    view.rerender(
      <MemoryRouter initialEntries={["/remittance?corridor=AU-IN&amount=900"]}>
        <RemittanceCompare />
      </MemoryRouter>
    );

    expect(compare.mutate).toHaveBeenCalledTimes(1);
  });
});

describe("an amount typed in the form (SGD, 65 to 6,450)", () => {
  function typeAndSubmit(text: string) {
    renderAt("/remittance");
    fireEvent.change(amountField(), { target: { value: text } });
    fireEvent.submit(amountField().closest("form") as HTMLFormElement);
  }

  it.each([
    ["645,10", 645.1],
    ["645.100", 645.1],
    ["645.5", 645.5],
    ["1,530", 1530],
    ["1.530,50", 1530.5],
    ["1,530.50", 1530.5],
  ])("compares %j as %d", (text, amount) => {
    typeAndSubmit(text);

    expect(compare.mutate).toHaveBeenCalledWith({ corridor_id: "SG-PH", amount });
    expect(document.getElementById("remittance-amount-error")).toBeNull();
  });

  it.each(["5,10", "5.400", "6.450"])("reads %j as a small amount, not as thousands", (text) => {
    typeAndSubmit(text);

    expect(compare.mutate).not.toHaveBeenCalled();
    expect(document.getElementById("remittance-amount-error")?.textContent).toContain(
      "Enter at least"
    );
  });
});

describe("opened as usual", () => {
  it.each([
    ["with no query", "/remittance"],
    ["with a corridor that does not exist", "/remittance?corridor=XX-YY&amount=900"],
    ["with an amount that is not valid", "/remittance?corridor=AU-IN&amount=abc"],
  ])("waits for the worker, %s", (_label, url) => {
    renderAt(url);

    expect(amountField().value).toBe("");
    expect(compare.mutate).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /compare/i })).toBeTruthy();
  });
});

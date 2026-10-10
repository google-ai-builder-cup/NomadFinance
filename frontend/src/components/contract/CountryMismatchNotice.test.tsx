// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import CountryMismatchNotice from "@/components/contract/CountryMismatchNotice";

vi.mock("@/hooks/useI18n", () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, string>) =>
      values ? `${key} ${values.detected}/${values.used}` : key,
  }),
}));

afterEach(cleanup);

describe("CountryMismatchNotice", () => {
  it("names both countries and checks again for the one the contract shows", () => {
    const onRecheck = vi.fn();
    render(<CountryMismatchNotice detected="KR" used="SG" onRecheck={onRecheck} />);

    expect(screen.getByText(/countryMismatch\.body South Korea\/Singapore/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /countryMismatch\.action/ }));

    expect(onRecheck).toHaveBeenCalledWith("KR");
  });

  it("cannot be pressed twice while the check runs", () => {
    render(<CountryMismatchNotice detected="KR" used="SG" onRecheck={vi.fn()} pending />);

    const button = screen.getByRole("button", { name: "contract.report.countryMismatch.working" });

    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it("says when the check could not be run again", () => {
    render(<CountryMismatchNotice detected="AU" used="SG" onRecheck={vi.fn()} failed />);

    expect(screen.getByRole("alert").textContent).toBe("contract.report.countryMismatch.failed");
  });
});

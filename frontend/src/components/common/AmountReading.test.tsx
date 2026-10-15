// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/lib/i18n";
import AmountReading from "@/components/common/AmountReading";

afterEach(cleanup);

describe("AmountReading", () => {
  it.each([
    ["5.400", "5.40"],
    ["5,400", "5,400"],
  ])("says how %j, which could be read two ways, was read", (text, shown) => {
    render(<AmountReading text={text} currency="SGD" />);

    expect(screen.getByRole("status").textContent).toContain("We read this as");
    expect(screen.getByRole("status").textContent).toContain(shown);
  });

  it.each(["5.4", "5,40", "500", "1.500.000", ""])(
    "says nothing for %j, which has one reading",
    (text) => {
      render(<AmountReading text={text} currency="SGD" />);

      expect(screen.queryByRole("status")).toBeNull();
    }
  );

  it("says nothing in a currency with no minor unit, where 42.000 can only be 42,000", () => {
    render(<AmountReading text="42.000" currency="JPY" />);

    expect(screen.queryByRole("status")).toBeNull();
  });
});

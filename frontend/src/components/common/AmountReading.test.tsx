// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/lib/i18n";
import AmountReading from "@/components/common/AmountReading";

afterEach(cleanup);

describe("AmountReading", () => {
  it("says how an amount that could be read two ways was read", () => {
    render(<AmountReading text="1.500" currency="SGD" />);

    expect(screen.getByRole("status").textContent).toContain("We read this as");
    expect(screen.getByRole("status").textContent).toContain("1,500");
  });

  it.each(["1.5", "1,500", "500", ""])("says nothing for %j, which has one reading", (text) => {
    render(<AmountReading text={text} currency="SGD" />);

    expect(screen.queryByRole("status")).toBeNull();
  });
});

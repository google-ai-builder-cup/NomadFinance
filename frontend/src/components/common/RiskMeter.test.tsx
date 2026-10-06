// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import RiskMeter from "@/components/common/RiskMeter";
import type { Severity } from "@/utils/risk";

afterEach(cleanup);

const CASES: [Severity, number, string, string][] = [
  ["low", 1, "Low risk", "bg-safe"],
  ["medium", 2, "Medium risk", "bg-caution"],
  ["high", 3, "High risk", "bg-danger"],
];

describe("RiskMeter", () => {
  it.each(CASES)("reads out %s as position %i of 3", (severity, position, label) => {
    render(<RiskMeter severity={severity} label={label} meterLabel="Scam risk" />);

    const meter = screen.getByRole("meter", { name: "Scam risk" });
    expect(meter.getAttribute("aria-valuenow")).toBe(String(position));
    expect(meter.getAttribute("aria-valuemin")).toBe("1");
    expect(meter.getAttribute("aria-valuemax")).toBe("3");
    expect(meter.getAttribute("aria-valuetext")).toBe(label);
  });

  it.each(CASES)("fills %i segments in one colour for %s", (severity, position, label, fill) => {
    render(<RiskMeter severity={severity} label={label} meterLabel="Scam risk" />);

    const segments = Array.from(screen.getByRole("meter").children);
    expect(segments).toHaveLength(3);
    expect(segments.filter((segment) => segment.className.includes(fill))).toHaveLength(position);
    expect(segments.filter((segment) => segment.className.includes("bg-muted"))).toHaveLength(
      3 - position
    );
  });

  it("always shows the level in words next to an icon, so colour is never the only signal", () => {
    const { container } = render(
      <RiskMeter severity="high" label="High risk" meterLabel="Scam risk" />
    );

    expect(screen.getByText("High risk")).toBeTruthy();
    expect(container.querySelector("svg[aria-hidden='true']")).toBeTruthy();
  });

  it("hides the decorative segments from a screen reader", () => {
    render(<RiskMeter severity="medium" label="Medium risk" meterLabel="Scam risk" />);

    expect(
      Array.from(screen.getByRole("meter").children).every(
        (segment) => segment.getAttribute("aria-hidden") === "true"
      )
    ).toBe(true);
  });

  it("uses no physical left or right classes", () => {
    const { container } = render(
      <RiskMeter severity="low" label="Low risk" meterLabel="Scam risk" />
    );

    expect(container.innerHTML).not.toMatch(/\b(ml|mr|pl|pr)-\d|text-left|text-right/);
  });
});

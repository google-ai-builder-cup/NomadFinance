// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import RiskBadge, { type RiskLevel } from "@/components/common/RiskBadge";

afterEach(cleanup);

const LEVELS: [RiskLevel, string][] = [
  ["safe", "border-safe"],
  ["caution", "border-caution"],
  ["danger", "border-danger"],
  ["info", "border-info"],
];

describe("RiskBadge", () => {
  it.each(LEVELS)("shows %s in its own colour, in words, next to an icon", (level, colour) => {
    const { container } = render(<RiskBadge level={level}>Label</RiskBadge>);

    expect(screen.getByText("Label").className).toContain(colour);
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("uses a different icon for each level", () => {
    const icons = LEVELS.map(([level]) => {
      const { container, unmount } = render(<RiskBadge level={level}>x</RiskBadge>);
      const html = container.querySelector("svg")?.innerHTML;
      unmount();
      return html;
    });

    expect(new Set(icons).size).toBe(4);
  });
});

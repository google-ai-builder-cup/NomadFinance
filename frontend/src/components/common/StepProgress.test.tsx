// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import StepProgress from "@/components/common/StepProgress";

afterEach(cleanup);

const STEPS = [
  { id: "intro", label: "Intro" },
  { id: "income", label: "Income" },
  { id: "debt", label: "Debt" },
  { id: "plan", label: "Plan" },
];
const STATUS = { done: "completed", current: "current step", upcoming: "not started" };

function renderSteps(currentIndex: number) {
  return render(
    <StepProgress
      steps={STEPS}
      currentIndex={currentIndex}
      listLabel="Interview progress"
      progressLabel={`Step ${currentIndex + 1} of 4: ${STEPS[currentIndex].label}`}
      statusLabels={STATUS}
    />
  );
}

describe("StepProgress", () => {
  it("is a named navigation landmark holding an ordered list of every step", () => {
    renderSteps(1);

    const nav = screen.getByRole("navigation", { name: "Interview progress" });
    expect(within(nav).getAllByRole("listitem")).toHaveLength(4);
  });

  it("marks only the current step with aria-current", () => {
    renderSteps(2);

    const items = screen.getAllByRole("listitem");
    expect(items.map((item) => item.getAttribute("aria-current"))).toEqual([
      null,
      null,
      "step",
      null,
    ]);
  });

  it("says in words which steps are done, current and upcoming", () => {
    renderSteps(1);

    const items = screen.getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringContaining("completed"),
      expect.stringContaining("current step"),
      expect.stringContaining("not started"),
      expect.stringContaining("not started"),
    ]);
    expect(screen.getAllByText("completed")[0].className).toContain("sr-only");
  });

  it("shows a tick for a done step and the number for the others", () => {
    renderSteps(2);

    const [first, second, third, fourth] = screen.getAllByRole("listitem");
    expect(first.querySelector("svg")).toBeTruthy();
    expect(second.querySelector("svg")).toBeTruthy();
    expect(third.querySelector("svg")).toBeNull();
    expect(third.textContent).toContain("3");
    expect(fourth.textContent).toContain("4");
  });

  it("shows the position in words, built by the caller", () => {
    renderSteps(3);

    expect(screen.getByText("Step 4 of 4: Plan")).toBeTruthy();
  });

  it("keeps every step's name in the reading order, hidden only visually on a narrow screen", () => {
    renderSteps(1);

    for (const name of ["Intro", "Income", "Debt", "Plan"]) {
      const label = screen.getByText(name);
      // sr-only is "visually hidden", not display:none, so a screen reader still reads it.
      expect(label.className).toContain("sr-only");
      expect(label.className).toContain("sm:not-sr-only");
      expect(label.className).not.toMatch(/(^|\s)hidden(\s|$)/);
    }
  });

  it("draws the names outside the row's flow and mirrors them in right-to-left", () => {
    renderSteps(1);

    const label = screen.getByText("Income");
    expect(label.className).toContain("sm:absolute");
    expect(label.className).toContain("sm:-translate-x-1/2");
    expect(label.className).toContain("rtl:sm:translate-x-1/2");
  });

  it("uses no physical left or right classes", () => {
    const { container } = renderSteps(1);

    expect(container.innerHTML).not.toMatch(/\b(ml|mr|pl|pr)-\d|text-left|text-right/);
  });
});

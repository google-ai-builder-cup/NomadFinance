// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import TimelineItem from "@/components/common/TimelineItem";

afterEach(cleanup);

describe("TimelineItem", () => {
  it("is a list item with its title as a heading and its content below", () => {
    render(
      <ol>
        <TimelineItem title="Open a bank account" timeLabel="Week 1">
          Bring your passport.
        </TimelineItem>
      </ol>
    );

    expect(screen.getByRole("listitem")).toBeTruthy();
    expect(screen.getByRole("heading", { level: 3 }).textContent).toBe("Open a bank account");
    expect(screen.getByText("Week 1")).toBeTruthy();
    expect(screen.getByText("Bring your passport.")).toBeTruthy();
  });

  it("marks the current item with aria-current and no other", () => {
    render(
      <ol>
        <TimelineItem title="A" status="done" />
        <TimelineItem title="B" status="current" />
        <TimelineItem title="C" />
      </ol>
    );

    expect(
      screen.getAllByRole("listitem").map((item) => item.getAttribute("aria-current"))
    ).toEqual([null, "step", null]);
  });

  it("reads the status out loud, after the title, without showing it", () => {
    render(
      <ol>
        <TimelineItem title="Send money home" status="done" statusLabel="completed" />
      </ol>
    );

    expect(screen.getByText("(completed)").className).toContain("sr-only");
    expect(screen.getByRole("heading").textContent).toBe("Send money home (completed)");
  });

  it("shows a tick for done and a dot otherwise, unless an icon is given", () => {
    const { container, rerender } = render(
      <ol>
        <TimelineItem title="A" status="done" />
      </ol>
    );
    const doneIcon = container.querySelector("svg")?.getAttribute("class");
    rerender(
      <ol>
        <TimelineItem title="A" status="upcoming" />
      </ol>
    );
    const upcomingIcon = container.querySelector("svg")?.innerHTML;

    expect(doneIcon).toBeTruthy();
    expect(upcomingIcon).toContain("circle");
  });

  it("draws a connecting line below every item except the last", () => {
    const { container } = render(
      <ol>
        <TimelineItem title="A" />
        <TimelineItem title="B" isLast />
      </ol>
    );

    const [first, last] = Array.from(container.querySelectorAll("li"));
    // The marker is always there; the connector is the second hidden span.
    expect(first.querySelectorAll("span[aria-hidden='true']")).toHaveLength(2);
    expect(last.querySelectorAll("span[aria-hidden='true']")).toHaveLength(1);
  });

  it("puts the marker and the line on the start side, so it mirrors in right-to-left", () => {
    const { container } = render(
      <ol dir="rtl">
        <TimelineItem title="A" />
        <TimelineItem title="B" isLast />
      </ol>
    );

    expect(container.innerHTML).toContain("start-0");
    expect(container.innerHTML).toContain("ps-10");
    expect(container.innerHTML).not.toMatch(
      /\b(ml|mr|pl|pr)-\d|text-left|text-right|\bleft-|\bright-/
    );
  });
});

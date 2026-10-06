// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { Inbox } from "lucide-react";
import { afterEach, describe, expect, it } from "vitest";

import EmptyState from "@/components/common/EmptyState";

afterEach(cleanup);

describe("EmptyState", () => {
  it("shows the title as a level 2 heading by default, with its description", () => {
    render(<EmptyState icon={Inbox} title="No checks yet" description="Paste a message." />);

    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("No checks yet");
    expect(screen.getByText("Paste a message.")).toBeTruthy();
  });

  it("can use another heading level so the page's heading order stays right", () => {
    render(<EmptyState icon={Inbox} title="Nothing here" description="d" headingLevel={3} />);

    expect(screen.getByRole("heading", { level: 3 }).textContent).toBe("Nothing here");
    expect(screen.queryByRole("heading", { level: 2 })).toBeNull();
  });

  it("shows the action it is given", () => {
    render(
      <EmptyState
        icon={Inbox}
        title="t"
        description="d"
        action={<button type="button">Start</button>}
      />
    );

    expect(screen.getByRole("button", { name: "Start" })).toBeTruthy();
  });

  it("hides the decorative icon from a screen reader", () => {
    const { container } = render(<EmptyState icon={Inbox} title="t" description="d" />);

    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("shows an illustration instead of the icon tile when one is given", () => {
    const { container } = render(
      <EmptyState
        icon={Inbox}
        title="t"
        description="d"
        illustration={<img alt="" data-testid="art" />}
      />
    );

    expect(screen.getByTestId("art")).toBeTruthy();
    expect(container.querySelector("svg")).toBeNull();
  });
});

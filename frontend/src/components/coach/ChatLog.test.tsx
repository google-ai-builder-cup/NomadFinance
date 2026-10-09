// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

import ChatLog from "@/components/coach/ChatLog";
import { loadNamespace } from "@/lib/i18n";
import type { ChatLine } from "@/utils/coachChatState";

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(cleanup);

const LINES: ChatLine[] = [
  { id: "m_1", role: "coach", text: "Which country?" },
  { id: "m_2", role: "user", text: "Australia" },
];

/** jsdom has no layout, so the box's size is stated: 1000 px of text in a 300 px window. */
function sizeTheLog(scrollTop: number) {
  const log = screen.getByRole("log");
  Object.defineProperty(log, "scrollHeight", { configurable: true, value: 1000 });
  Object.defineProperty(log, "clientHeight", { configurable: true, value: 300 });
  log.scrollTop = scrollTop;
  fireEvent.scroll(log);
  return log;
}

describe("ChatLog", () => {
  it("is a named, focusable log that is not a live region", () => {
    render(<ChatLog lines={LINES} draft={null} announcement="" language="en" />);

    const log = screen.getByRole("log", { name: "Conversation with the coach" });

    expect(log.getAttribute("aria-live")).toBe("off");
    expect(log.getAttribute("tabindex")).toBe("0");
    expect(log.getAttribute("lang")).toBe("en");
  });

  it("is the anchor of the hidden speaker labels, so a long talk does not stretch the page", () => {
    // The labels are absolutely positioned. If the scroller is not a positioned box they are placed
    // against one outside it, below the visible part, and every message adds to the page's height
    // (found in NF-FC-023: a 20-line talk made a 2,000 px page).
    render(<ChatLog lines={LINES} draft={null} announcement="" language="en" />);

    expect(screen.getByRole("log").className).toMatch(/(^|\s)relative(\s|$)/);
    expect(screen.getByRole("log").className).toMatch(/overflow-y-auto/);
  });

  it("says who spoke before each line, for a screen reader", () => {
    render(<ChatLog lines={LINES} draft={null} announcement="" language="en" />);

    expect(screen.getByText("Coach:")).toBeTruthy();
    expect(screen.getByText("You said:")).toBeTruthy();
  });

  it("shows the reply that is arriving as a busy bubble, with the typing label", () => {
    render(<ChatLog lines={LINES} draft="Thank you" announcement="" language="en" />);

    expect(screen.getByText("Thank you")).toBeTruthy();
    expect(screen.getByText("The coach is typing")).toBeTruthy();
    expect(screen.getByRole("log").querySelector("[aria-busy='true']")).not.toBeNull();
  });

  it("says a finished reply once, in the status region and not in the log's own announcements", () => {
    const { rerender } = render(
      <ChatLog lines={LINES} draft={null} announcement="" language="en" />
    );
    expect(screen.getByRole("status").textContent).toBe("");

    rerender(<ChatLog lines={LINES} draft={null} announcement="Thank you." language="en" />);

    expect(screen.getByRole("status").textContent).toBe("Thank you.");
  });

  it("leaves the notice as the only alert when a line was not sent", () => {
    const failed: ChatLine[] = [
      ...LINES,
      { id: "local-1", role: "user", text: "4200", failed: true },
    ];

    render(
      <ChatLog
        lines={failed}
        draft={null}
        announcement=""
        language="en"
        footer={<div role="alert">The coach is busy. Try again.</div>}
      />
    );

    expect(screen.getByText("Not sent")).toBeTruthy(); // still shown beside the line
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("follows new content to the end while the worker is at the end", () => {
    const { rerender } = render(
      <ChatLog lines={LINES} draft={null} announcement="" language="en" />
    );
    const log = sizeTheLog(700);
    expect(screen.queryByRole("button", { name: "Latest message" })).toBeNull();

    rerender(<ChatLog lines={LINES} draft="Thank you" announcement="" language="en" />);

    expect(log.scrollTop).toBe(1000);
  });

  it("leaves a worker who scrolled up where they are, and offers the way back", async () => {
    const { rerender } = render(
      <ChatLog lines={LINES} draft={null} announcement="" language="en" />
    );
    const log = sizeTheLog(100);
    const jump = screen.getByRole("button", { name: "Latest message" });

    rerender(<ChatLog lines={LINES} draft="Thank you very much" announcement="" language="en" />);
    expect(log.scrollTop).toBe(100);

    await userEvent.setup().click(jump);
    expect(log.scrollTop).toBe(1000);
    expect(screen.queryByRole("button", { name: "Latest message" })).toBeNull();
    // And it follows again.
    rerender(
      <ChatLog lines={LINES} draft="Thank you very much indeed" announcement="" language="en" />
    );
    expect(log.scrollTop).toBe(1000);
  });
});

// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ChatBubble from "@/components/common/ChatBubble";

afterEach(cleanup);

describe("ChatBubble", () => {
  it("puts an assistant message at the start of the line and a user message at the end", () => {
    const { container } = render(
      <>
        <ChatBubble role="assistant">Hello</ChatBubble>
        <ChatBubble role="user">Hi</ChatBubble>
      </>
    );

    const [assistant, user] = Array.from(container.querySelectorAll("[data-role]"));
    expect(assistant.className).toContain("justify-start");
    expect(user.className).toContain("justify-end");
  });

  it("tells a screen reader who spoke, without showing it", () => {
    render(
      <ChatBubble role="user" speakerLabel="You said:">
        I earn 1800 a month
      </ChatBubble>
    );

    const speaker = screen.getByText("You said:");
    expect(speaker.className).toContain("sr-only");
    expect(screen.getByText(/I earn 1800 a month/)).toBeTruthy();
  });

  it("shows typing dots and the typing label while nothing has arrived yet", () => {
    const { container } = render(<ChatBubble role="assistant" streaming typingLabel="Typing" />);

    expect(container.querySelector("[data-role]")?.getAttribute("aria-busy")).toBe("true");
    expect(screen.getByText("Typing").className).toContain("sr-only");
    expect(container.querySelectorAll('[aria-hidden="true"] > span')).toHaveLength(3);
  });

  it("shows the text so far with a hidden caret while it streams", () => {
    const { container } = render(
      <ChatBubble role="assistant" streaming>
        Let me ask about
      </ChatBubble>
    );

    expect(screen.getByText(/Let me ask about/)).toBeTruthy();
    expect(container.querySelector("span[aria-hidden='true']")).toBeTruthy();
  });

  it("is not busy once the message is complete", () => {
    const { container } = render(<ChatBubble role="assistant">Done</ChatBubble>);

    expect(container.querySelector("[data-role]")?.hasAttribute("aria-busy")).toBe(false);
  });

  it("offers a retry for a failed message, by mouse", async () => {
    const onRetry = vi.fn();
    render(
      <ChatBubble
        role="user"
        failed
        failedLabel="Not sent"
        retryLabel="Try again"
        onRetry={onRetry}
      >
        My message
      </ChatBubble>
    );

    expect(screen.getByRole("alert").textContent).toBe("Not sent");
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("can be retried from the keyboard alone: Tab to the button, then Enter", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <ChatBubble
        role="user"
        failed
        failedLabel="Not sent"
        retryLabel="Try again"
        onRetry={onRetry}
      >
        My message
      </ChatBubble>
    );

    await user.tab();
    expect(document.activeElement?.textContent).toBe("Try again");
    await user.keyboard("{Enter}");

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("has no retry button for a message that went through", () => {
    render(
      <ChatBubble role="user" retryLabel="Try again" onRetry={() => undefined}>
        Fine
      </ChatBubble>
    );

    expect(screen.queryByRole("button")).toBeNull();
  });

  it("uses only logical spacing and alignment, so it mirrors in right-to-left", () => {
    const { container } = render(
      <div dir="rtl">
        <ChatBubble role="assistant" timeLabel="10:42" failed failedLabel="x" retryLabel="y">
          text
        </ChatBubble>
      </div>
    );

    expect(container.innerHTML).not.toMatch(/\b(ml|mr|pl|pr)-\d|text-left|text-right/);
  });
});

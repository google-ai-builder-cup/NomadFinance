// @vitest-environment jsdom
// The review table, the way to start over, and the finished screen (NF-FC-023).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import CoachChat from "@/components/coach/CoachChat";
import { loadNamespace } from "@/lib/i18n";
import { replaySession, replayTurns, sessionFrom } from "@/mocks/coachTurns";
import { setupMockServer } from "@/mocks/server";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(cleanup);

const BACK_TO_INCOME = {
  bytes:
    'event: token\ndata: {"text":"Sure. What is your pay?"}\n\n' +
    'event: done\ndata: {"message_id":"m_030","stage":"income","next_slot":"monthly_salary","turn_count":12}\n\n',
};
const YES_THEN_PLAN = {
  bytes:
    'event: token\ndata: {"text":"Thank you. Your answers are saved."}\n\n' +
    'event: done\ndata: {"message_id":"m_030","stage":"plan","next_slot":null,"turn_count":12}\n\n',
};

function renderChat(
  session = sessionFrom("coach/session-03-review.json"),
  onRestart = vi.fn(),
  timing: Record<string, number> = {}
) {
  const view = render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <CoachChat
          session={session}
          onRestart={onRestart}
          timing={{ retryDelayMs: 0, ...timing }}
        />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return { ...view, onRestart };
}

describe("the review", () => {
  it("shows the saved answers as a table under the conversation, not inside its scrolling box", () => {
    renderChat();

    const table = screen.getByRole("table", { name: "Your answers, one row for each question" });
    expect(screen.getByRole("log").contains(table)).toBe(false);
    expect(within(table).getByRole("cell", { name: "4,200 AUD per month" })).toBeTruthy();
    expect(within(table).getByRole("cell", { name: "Australia" })).toBeTruthy();
    expect(within(table).getByRole("cell", { name: "Care worker" })).toBeTruthy();
  });

  it("sends the row's change as the worker's own answer, and the table goes when the stage moves", async () => {
    const sent = replayTurns(BACK_TO_INCOME);
    const user = userEvent.setup();
    renderChat();

    await user.click(screen.getByRole("button", { name: "Change: Your pay" }));

    await within(screen.getByRole("log")).findByText("Sure. What is your pay?");
    expect(sent[0]?.body.text).toBe("I want to change my answer about: Your pay.");
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("is not shown during the interview", () => {
    replayTurns("coach/turn-01-start.sse");
    renderChat(sessionFrom("coach/session-02-debt.json"));

    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("starting over", () => {
  it("is offered in the middle of the interview, and asks before it closes it", async () => {
    const user = userEvent.setup();
    const { onRestart } = renderChat(sessionFrom("coach/session-02-debt.json"));

    await user.click(screen.getByRole("button", { name: "New interview" }));
    expect(onRestart).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Yes, start over" }));

    expect(onRestart).toHaveBeenCalledTimes(1);
  });

  it("waits for the welcome-back banner to go, which offers the same choice", () => {
    renderChat(sessionFrom("coach/session-02-debt.json", { resumed: true }));

    expect(screen.queryByRole("button", { name: "New interview" })).toBeNull();
    expect(screen.getByRole("button", { name: "Start a new interview" })).toBeTruthy();
  });

  it("sits on the step line, so it takes no row of its own from the conversation", () => {
    renderChat(sessionFrom("coach/session-02-debt.json"));

    const steps = screen.getByRole("navigation", { name: "Interview progress" });
    expect(within(steps).getByRole("button", { name: "New interview" })).toBeTruthy();
  });
});

describe("the finished screen", () => {
  it("keeps the whole conversation in a box that can be read, below the score", async () => {
    replaySession();
    replayTurns(YES_THEN_PLAN);
    const user = userEvent.setup();
    renderChat();

    await user.click(screen.getByRole("button", { name: "Yes, that is right" }));

    await screen.findByRole("img", { name: /57 out of 100/ });
    const log = screen.getByRole("log");
    expect(screen.getByRole("heading", { name: "Your conversation with the coach" })).toBeTruthy();
    // Not squeezed to a few lines (it was `max-h-16`): the box has a height of its own.
    expect(log.parentElement?.parentElement?.className ?? "").not.toMatch(/max-h-16/);
    expect(log.parentElement?.parentElement?.className ?? "").toMatch(/h-\[min\(32rem,70dvh\)\]/);
    expect(within(log).getByText("Thank you. Your answers are saved.")).toBeTruthy();
  });

  it("offers a new interview next to the way home", async () => {
    replaySession();
    replayTurns(YES_THEN_PLAN);
    const user = userEvent.setup();
    const { onRestart } = renderChat();
    await user.click(screen.getByRole("button", { name: "Yes, that is right" }));
    await screen.findByRole("img", { name: /57 out of 100/ });

    expect(screen.getByRole("link", { name: "Back to home" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "New interview" }));
    await user.click(screen.getByRole("button", { name: "Yes, start over" }));

    expect(onRestart).toHaveBeenCalledTimes(1);
  });

  it("tells the page when it starts to flow, so the page stops fixing its own height", () => {
    const onFlowChange = vi.fn();
    const mount = (name: string) =>
      render(
        <QueryClientProvider client={new QueryClient()}>
          <MemoryRouter>
            <CoachChat
              session={sessionFrom(name)}
              onRestart={vi.fn()}
              onFlowChange={onFlowChange}
              timing={{ retryDelayMs: 0 }}
            />
          </MemoryRouter>
        </QueryClientProvider>
      );

    mount("coach/session-02-debt.json").unmount();
    expect(onFlowChange).toHaveBeenLastCalledWith(false);

    mount("coach/session-03-review.json").unmount();
    expect(onFlowChange).toHaveBeenLastCalledWith(true);

    mount("coach/session-04-plan-mid.json");
    expect(onFlowChange).toHaveBeenLastCalledWith(true);
  });
});

describe("what a screen reader is told", () => {
  const reply = (text: string, id: string) => ({
    bytes:
      `event: token
data: {"text":"${text}"}

` +
      `event: done
data: {"message_id":"${id}","stage":"debt","next_slot":"debt_outstanding","turn_count":6}

`,
  });

  it("says each finished coach message once, one after the other, never both and never a half", async () => {
    replayTurns(reply("First reply.", "m_100"), reply("Second reply.", "m_101"));
    const user = userEvent.setup();
    renderChat(sessionFrom("coach/session-02-debt.json"));
    const spoken = () => screen.getByRole("status").textContent;
    expect(spoken()).toBe("");

    await user.click(screen.getByRole("button", { name: "None (0)" }));
    await within(screen.getByRole("log")).findByText("First reply.");
    await waitFor(() => expect(spoken()).toBe("First reply."));

    await user.click(screen.getByRole("button", { name: "None (0)" }));
    await within(screen.getByRole("log")).findByText("Second reply.");
    await waitFor(() => expect(spoken()).toBe("Second reply."));
    // Both are in the conversation; only the latest is in the hidden copy.
    expect(screen.getByRole("log").textContent).toContain("First reply.");
  });

  it("takes the hidden copy away a few seconds after it was read, so browsing meets the reply once", async () => {
    replayTurns(reply("First reply.", "m_100"));
    const user = userEvent.setup();
    renderChat(sessionFrom("coach/session-02-debt.json"), vi.fn(), { announcementMs: 60 });

    await user.click(screen.getByRole("button", { name: "None (0)" }));

    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("First reply."));
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe(""));
    expect(screen.getByRole("log").textContent).toContain("First reply.");
  });

  it("does not make the conversation a live region, so a reply is not read word by word", () => {
    renderChat();

    expect(screen.getByRole("log").getAttribute("aria-live")).toBe("off");
    expect(screen.getAllByRole("status").every((el) => !el.closest("[role='log']"))).toBe(true);
  });
});

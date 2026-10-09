// @vitest-environment jsdom
// From the review to the plan (NF-FC-020): the worker says yes, the interview reaches `plan`, and the
// chat shows the preparedness score and the button that makes the plan.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import CoachChat from "@/components/coach/CoachChat";
import { loadNamespace } from "@/lib/i18n";
import { replayPlan, replaySession, replayTurns, sessionFrom } from "@/mocks/coachTurns";
import { setupMockServer } from "@/mocks/server";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(cleanup);

const YES_THEN_PLAN = {
  bytes:
    'event: token\ndata: {"text":"Thank you. Your answers are saved."}\n\n' +
    'event: done\ndata: {"message_id":"m_030","stage":"plan","next_slot":null,"turn_count":12}\n\n',
};

function renderChat(session = sessionFrom("coach/session-03-review.json")) {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <CoachChat session={session} onRestart={vi.fn()} timing={{ retryDelayMs: 0 }} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("after the answers are confirmed", () => {
  it("shows the score and the plan button in place of the answer box", async () => {
    const read = replaySession();
    replayTurns(YES_THEN_PLAN);
    const user = userEvent.setup();
    renderChat();

    await user.click(screen.getByRole("button", { name: "Yes, that is right" }));

    expect(
      await screen.findByRole("img", { name: "Preparedness score: 57 out of 100, Getting ready" })
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Make my 90-day plan" })).toBeTruthy();
    expect(screen.queryByRole("group", { name: "Your answer" })).toBeNull();
    expect(screen.getByText("All your answers are in")).toBeTruthy();
    expect(read.requests).toBe(1); // the score is read once the stage is `plan`, not before
  });

  it("does not ask for the score during the interview", async () => {
    const read = replaySession();
    replayTurns("coach/turn-01-start.sse");

    renderChat(sessionFrom("coach/sessions-create-01-new.json"));
    await within(screen.getByRole("log")).findByText(/Which country are you going to work in\?/);

    expect(read.requests).toBe(0);
    expect(screen.queryByRole("button", { name: "Make my 90-day plan" })).toBeNull();
  });

  it("makes the plan from the button and shows its summary", async () => {
    replaySession();
    replayTurns(YES_THEN_PLAN);
    const made = replayPlan();
    const user = userEvent.setup();
    renderChat();
    await user.click(screen.getByRole("button", { name: "Yes, that is right" }));
    await screen.findByRole("img", { name: /57 out of 100/ });

    await user.click(screen.getByRole("button", { name: "Make my 90-day plan" }));

    await screen.findByText("Your plan is ready");
    expect(made.sent).toEqual([{ sessionId: "s_03", language: "en" }]);
    expect(screen.getByRole("link", { name: "Back to home" }).getAttribute("href")).toBe(
      "/dashboard"
    );
  });

  it("shows the score straight away for an interview that was already confirmed", async () => {
    replaySession();

    renderChat(sessionFrom("coach/session-04-plan-mid.json", { resumed: true }));

    expect(await screen.findByRole("img", { name: /57 out of 100/ })).toBeTruthy();
  });
});

// @vitest-environment jsdom
// The interview against the recorded streams of docs/mocks/coach/ (NF-FC-017): the real chat,
// hook, stream client and API client run, and only the backend's answers come from the mock files.
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import CoachChat from "@/components/coach/CoachChat";
import { replayTurns, sessionFrom } from "@/mocks/coachTurns";
import { server, setupMockServer } from "@/mocks/server";
import { loadNamespace } from "@/lib/i18n";
import type { CoachSessionStart } from "@/types/coach";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(cleanup);

const KEY_FORMAT = /^[A-Za-z0-9_-]{16,64}$/;
// The screen waits a second before it tries a dropped stream again; a test does not.
const FAST = { retryDelayMs: 0 };

function renderChat(session: CoachSessionStart, onRestart = vi.fn()) {
  render(
    <MemoryRouter>
      <CoachChat session={session} onRestart={onRestart} timing={FAST} />
    </MemoryRouter>
  );
  return onRestart;
}

const newSession = () => sessionFrom("coach/sessions-create-01-new.json");
const log = () => screen.getByRole("log");
const chip = (name: string) => screen.getByRole("button", { name });
const logText = () => log().textContent ?? "";
// The finished reply is also in a visually hidden status region (read out once), so a reply is
// looked for in the log itself.
const inLog = (text: RegExp) => within(log()).findByText(text);
// A failed answer says "Not sent" in an alert of its own; the notice is the one with the reason.
const notice = async (text: RegExp) =>
  (await screen.findByText(text, {}, { timeout: 3000 })).closest("[role='alert']") as HTMLElement;

describe("the opening", () => {
  it("lets the coach speak first, with no text, then offers the six countries", async () => {
    const sent = replayTurns("coach/turn-01-start.sse");

    renderChat(newSession());

    await inLog(/Which country are you going to work in\?/);
    expect(sent).toHaveLength(1);
    expect(sent[0].body).toEqual({ language: "en" });
    expect(sent[0].key).toMatch(KEY_FORMAT);
    const chips = within(screen.getByRole("group", { name: "Quick answers" }));
    for (const country of [
      "Singapore",
      "South Korea",
      "Malaysia",
      "Japan",
      "Hong Kong",
      "Australia",
    ]) {
      expect((chips.getByRole("button", { name: country }) as HTMLButtonElement).disabled).toBe(
        false
      );
    }
    expect(screen.getByText("Step 1 of 6: Basics")).toBeTruthy();
  });

  it("shows the transcript of a resumed interview and does not speak again", async () => {
    const sent = replayTurns("coach/turn-02-answer.sse");
    const session = sessionFrom("coach/session-02-debt.json", { resumed: true });

    renderChat(session);

    expect(logText()).toContain("नमस्ते! मैं आपका पैसों का साथी हूँ।");
    expect(sent).toHaveLength(0);
    expect(screen.getByText("Step 4 of 6: Debt")).toBeTruthy();
  });
});

describe("a turn", () => {
  it("sends the chip's words, shows them, and streams the next question in", async () => {
    const sent = replayTurns("coach/turn-01-start.sse", "coach/turn-02-answer.sse");
    const user = userEvent.setup();
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);

    await user.click(chip("Australia"));

    await inLog(/What kind of work will you do\?/);
    expect(sent[1].body).toEqual({ text: "Australia", language: "en" });
    expect(sent[1].key).toMatch(KEY_FORMAT);
    expect(sent[1].key).not.toBe(sent[0].key);
    expect(logText()).toContain("Australia");
    // The next question's helper has replaced the countries.
    expect(chip("Care worker")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Singapore" })).toBeNull();
  });

  it("brings focus to the answer panel when the helper it was on is replaced", async () => {
    replayTurns("coach/turn-01-start.sse", "coach/turn-02-answer.sse");
    const user = userEvent.setup();
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);

    await user.click(chip("Australia"));

    await inLog(/What kind of work will you do\?/);
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole("group", { name: "Your answer" }))
    );
  });

  it("does not take focus the worker put somewhere else", async () => {
    replayTurns("coach/turn-01-start.sse", "coach/turn-02-answer.sse");
    const user = userEvent.setup();
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);
    await user.click(chip("Australia"));
    // The worker moves on to the conversation while the reply is still arriving.
    log().focus();

    await inLog(/What kind of work will you do\?/);

    expect(document.activeElement).toBe(log());
  });

  it("shows the words before the turn is over, locks the chips, and announces the reply once at done", async () => {
    const encoder = new TextEncoder();
    let stream!: ReadableStreamDefaultController<Uint8Array>;
    server.use(
      http.post("*/api/v2/coach/sessions/:id/messages", () => {
        return new HttpResponse(
          new ReadableStream({
            start(controller) {
              stream = controller;
            },
          }),
          { headers: { "Content-Type": "text/event-stream" } }
        );
      })
    );
    renderChat(newSession());
    // The coach has been asked to speak; nothing has come back yet: three dots, no words.
    await waitFor(() => expect(stream).toBeDefined());
    expect(screen.getByText("The coach is typing")).toBeTruthy();
    expect(log().querySelector("[aria-busy='true']")).not.toBeNull();

    stream.enqueue(encoder.encode('event: token\ndata: {"text":"Hello! "}\n\n'));
    await waitFor(() => expect(logText()).toContain("Hello!"));
    stream.enqueue(encoder.encode('event: token\ndata: {"text":"Which country?"}\n\n'));
    await waitFor(() => expect(logText()).toContain("Hello! Which country?"));

    // Mid-stream: the chips cannot be used, and nothing is read out yet.
    expect((chip("Australia") as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("status").textContent).toBe("");
    expect(log().getAttribute("aria-live")).toBe("off");

    stream.enqueue(
      encoder.encode(
        'event: done\ndata: {"message_id":"m_001","stage":"intro","next_slot":"destination_country","turn_count":0}\n\n'
      )
    );
    stream.close();
    await waitFor(() => expect((chip("Australia") as HTMLButtonElement).disabled).toBe(false));
    expect(screen.getByRole("status").textContent).toBe("Hello! Which country?");
    expect(log().querySelector("[aria-busy='true']")).toBeNull();
  });

  it("moves the stepper when done says the stage changed", async () => {
    replayTurns("coach/turn-05-review.sse");
    const session = sessionFrom("coach/session-02-debt.json", {
      stage: "savings",
      next_slot: "bank_or_wallet",
    });
    const user = userEvent.setup();
    renderChat(session);
    expect(screen.getByText("Step 5 of 6: Savings")).toBeTruthy();

    await user.click(chip("Bank account"));

    await screen.findByText("Step 6 of 6: Review");
    expect(chip("Yes, that is right")).toBeTruthy();
    expect(chip("I want to change something")).toBeTruthy();
  });

  it("keeps the same question when the coach asks again, and stores nothing new", async () => {
    replayTurns("coach/turn-04-clarify.sse");
    const session = sessionFrom("coach/session-02-debt.json");
    const user = userEvent.setup();
    renderChat(session);

    await user.click(screen.getByRole("button", { name: "None (0)" }));

    await inLog(/क्या यह रुपये में है/);
    expect(screen.getByRole("button", { name: "None (0)" })).toBeTruthy();
    expect(screen.getByText("Step 4 of 6: Debt")).toBeTruthy();
  });

  it("ends in a confirmed state at the plan stage, with no answer box", async () => {
    replayTurns({
      bytes:
        'event: token\ndata: {"text":"Thank you. Your answers are saved."}\n\n' +
        'event: done\ndata: {"message_id":"m_030","stage":"plan","next_slot":null,"turn_count":12}\n\n',
    });
    const user = userEvent.setup();
    renderChat(sessionFrom("coach/session-03-review.json"));

    await user.click(chip("Yes, that is right"));

    await screen.findByText("All your answers are in");
    expect(screen.getByText("All questions answered")).toBeTruthy();
    expect(document.activeElement?.textContent).toContain("All your answers are in");
    expect(screen.queryByRole("group", { name: "Your answer" })).toBeNull();
    expect(screen.getByRole("link", { name: "Back to home" }).getAttribute("href")).toBe(
      "/dashboard"
    );
  });
});

describe("a stream that drops", () => {
  it("is tried again with the same key and shows the reply once, whole", async () => {
    const sent = replayTurns(
      "coach/turn-01-start.sse",
      "coach/turn-error-dropped.sse",
      "coach/turn-02-answer.sse"
    );
    const user = userEvent.setup();
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);

    await user.click(chip("Australia"));

    await inLog(/What kind of work will you do\?/);
    expect(sent).toHaveLength(3);
    expect(sent[2].key).toBe(sent[1].key);
    expect(sent[2].body).toEqual(sent[1].body);
    // The words of the dropped attempt were thrown away, not shown twice.
    expect(logText().match(/Australia, thank you\./g)).toHaveLength(1);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("after a second drop says so, marks the answer not sent, and Try again repeats it with the same key", async () => {
    const sent = replayTurns(
      "coach/turn-01-start.sse",
      "coach/turn-error-dropped.sse",
      "coach/turn-error-dropped.sse",
      "coach/turn-02-answer.sse"
    );
    const user = userEvent.setup();
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);

    await user.click(chip("Australia"));

    const alert = await notice(/The connection broke before the coach finished/);
    // The half reply is not on screen as if it were final, and the answer says it was not sent.
    expect(logText()).not.toContain("What kind of");
    expect(within(log()).getByText("Not sent")).toBeTruthy();

    await user.click(within(alert).getByRole("button", { name: "Try again" }));

    await inLog(/What kind of work will you do\?/);
    expect(sent).toHaveLength(4);
    expect(new Set(sent.slice(1).map((turn) => turn.key)).size).toBe(1);
    expect(screen.queryByText("Not sent")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    // The answer is in the log once, not once per attempt.
    expect(within(log()).getAllByText("Australia")).toHaveLength(1);
  });

  it("shows an error event the same way: the words are discarded and Try again is offered", async () => {
    replayTurns(
      "coach/turn-01-start.sse",
      "coach/turn-error-midstream.sse",
      "coach/turn-02-answer.sse"
    );
    const user = userEvent.setup();
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);

    await user.click(chip("Australia"));

    const alert = await notice(/The coach took too long to answer/);
    expect(logText()).not.toContain("Let me");
    // No automatic retry: the worker decides.
    await user.click(within(alert).getByRole("button", { name: "Try again" }));
    await inLog(/What kind of work will you do\?/);
  });
});

describe("a turn the server refuses", () => {
  it("offers a new interview when this one is over, and calls onRestart", async () => {
    replayTurns({ refusal: "coach/turn-error-session-not-active.json" });
    const user = userEvent.setup();
    const onRestart = renderChat(sessionFrom("coach/session-02-debt.json"));

    await user.click(screen.getByRole("button", { name: "None (0)" }));

    const alert = await notice(/This interview is finished/);
    expect(within(alert).queryByRole("button", { name: "Try again" })).toBeNull();
    await user.click(within(alert).getByRole("button", { name: "Start a new interview" }));
    expect(onRestart).toHaveBeenCalledTimes(1);
  });

  it("tells a worker who sent too fast, in plain words, and lets them try again", async () => {
    replayTurns({ refusal: "coach/turn-error-rate-limited.json" }, "coach/turn-02-answer.sse");
    const user = userEvent.setup();
    renderChat(
      sessionFrom("coach/session-01-new.json", {
        messages: [
          {
            id: "m_001",
            role: "coach",
            text: "Which country?",
            language: "en",
            at: "2026-10-20T08:00:00Z",
          },
        ],
      })
    );

    await user.click(chip("Australia"));

    const alert = await notice(/sending messages very fast/);
    expect(within(alert).getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("waits out a turn that is still running and then carries on, with the same key", async () => {
    const sent = replayTurns(
      { refusal: "coach/turn-error-in-progress.json" },
      "coach/turn-02-answer.sse"
    );
    const user = userEvent.setup();
    renderChat(
      sessionFrom("coach/session-01-new.json", {
        messages: [
          {
            id: "m_001",
            role: "coach",
            text: "Which country?",
            language: "en",
            at: "2026-10-20T08:00:00Z",
          },
        ],
      })
    );

    await user.click(chip("Australia"));

    await inLog(/What kind of work will you do\?/);
    expect(sent).toHaveLength(2);
    expect(sent[1].key).toBe(sent[0].key);
  });
});

describe("the answer box", () => {
  it("sends one turn at a time: a second tap while the reply arrives does nothing", async () => {
    const sent = replayTurns("coach/turn-02-answer.sse");
    const user = userEvent.setup();
    renderChat(
      sessionFrom("coach/session-01-new.json", {
        messages: [
          {
            id: "m_001",
            role: "coach",
            text: "Which country?",
            language: "en",
            at: "2026-10-20T08:00:00Z",
          },
        ],
      })
    );

    await user.dblClick(chip("Australia"));

    await inLog(/What kind of work will you do\?/);
    expect(sent).toHaveLength(1);
  });
});

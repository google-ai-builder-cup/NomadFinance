// @vitest-environment jsdom
// Changing the language while the interview is open (NF-FC-018): the coach carries on in the new
// one, with a turn that has no text, and the answers and the stage are not touched.
import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import CoachChat from "@/components/coach/CoachChat";
import { replayTurns, sessionFrom } from "@/mocks/coachTurns";
import { setupMockServer } from "@/mocks/server";
import i18n, { loadNamespace, setLanguage } from "@/lib/i18n";
import type { CoachSessionStart } from "@/types/coach";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(async () => {
  cleanup();
  await setLanguage("en");
});

const FAST = { retryDelayMs: 0 };
const KEY_FORMAT = /^[A-Za-z0-9_-]{16,64}$/;

function renderChat(session: CoachSessionStart) {
  render(
    <MemoryRouter>
      <CoachChat session={session} onRestart={vi.fn()} timing={FAST} />
    </MemoryRouter>
  );
}

const newSession = () => sessionFrom("coach/sessions-create-01-new.json");
const log = () => screen.getByRole("log");
const inLog = (text: RegExp) => within(log()).findByText(text);
const switchTo = (code: string) => act(async () => void (await setLanguage(code)));

describe("a language change during the interview", () => {
  it("sends a turn with no text and the new language, once the opening is over", async () => {
    const sent = replayTurns("coach/turn-01-start.sse", "coach/turn-08-language-switch.sse");
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);

    await switchTo("hi");

    await vi.waitFor(() => expect(sent).toHaveLength(2));
    expect(sent[1].body).toEqual({ language: "hi" });
    expect(sent[1].key).toMatch(KEY_FORMAT);
    expect(sent[1].key).not.toBe(sent[0].key);
  });

  it("keeps what the worker already answered and the step they are on", async () => {
    const sent = replayTurns(
      "coach/turn-01-start.sse",
      "coach/turn-02-answer.sse",
      "coach/turn-08-language-switch.sse"
    );
    const user = userEvent.setup();
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);
    await user.click(screen.getByRole("button", { name: "Australia" }));
    await inLog(/What kind of work will you do\?/);

    await switchTo("id");

    await vi.waitFor(() => expect(sent).toHaveLength(3));
    expect(sent[2].body).toEqual({ language: "id" });
    // The first answer is still in the conversation: nothing was cleared or asked again.
    expect(log().textContent).toContain("Australia");
    expect(log().textContent).toContain("What kind of work will you do?");
  });

  it("sends the next answer in the new language", async () => {
    const sent = replayTurns(
      "coach/turn-01-start.sse",
      "coach/turn-08-language-switch.sse",
      "coach/turn-02-answer.sse"
    );
    const user = userEvent.setup();
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);
    await switchTo("hi");
    await vi.waitFor(() => expect(sent).toHaveLength(2));
    await inLog(/अब मैं हिंदी में बात करूँगा/); // the switch turn is over

    // The next question is the agent's fee, with an amount field; type a free answer instead.
    await user.click(
      screen.getByRole("button", { name: i18n.t("input.typeInstead", { ns: "coach" }) })
    );
    await user.type(screen.getByRole("textbox"), "Nothing{Enter}");

    await vi.waitFor(() => expect(sent).toHaveLength(3));
    expect(sent[2].body.language).toBe("hi");
    expect(sent[2].body.text).toBeTruthy();
  });

  it("waits for a turn that is running, then switches once", async () => {
    const sent = replayTurns(
      "coach/turn-01-start.sse",
      "coach/turn-02-answer.sse",
      "coach/turn-08-language-switch.sse"
    );
    const user = userEvent.setup();
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);

    await user.click(screen.getByRole("button", { name: "Australia" }));
    await switchTo("hi"); // the answer's reply may still be arriving

    await vi.waitFor(() => expect(sent).toHaveLength(3));
    expect(sent.map((turn) => turn.body.language)).toEqual(["en", "en", "hi"]);
    expect(sent[2].body.text).toBeUndefined();
  });

  it("does nothing when the language is not changed, or changed back to the same one", async () => {
    const sent = replayTurns("coach/turn-01-start.sse", "coach/turn-08-language-switch.sse");
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);

    await switchTo("en");
    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(sent).toHaveLength(1);
    expect(i18n.resolvedLanguage).toBe("en");
  });

  it("does not pile a switch onto a turn that failed: the worker retries that one", async () => {
    const sent = replayTurns("coach/turn-01-start.sse", {
      refusal: "coach/turn-error-ai-busy.json",
    });
    const user = userEvent.setup();
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);
    await user.click(screen.getByRole("button", { name: "Australia" }));
    await screen.findByText(/The coach is busy right now/, {}, { timeout: 3000 });

    await switchTo("hi");
    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(sent).toHaveLength(2); // the opening and the failed answer; no switch on top of it
  });

  it("lets a retry of the failed turn go out as it was", async () => {
    const sent = replayTurns(
      "coach/turn-01-start.sse",
      { refusal: "coach/turn-error-ai-busy.json" },
      "coach/turn-02-answer.sse"
    );
    const user = userEvent.setup();
    renderChat(newSession());
    await inLog(/Which country are you going to work in\?/);
    await user.click(screen.getByRole("button", { name: "Australia" }));
    await screen.findByText(/The coach is busy right now/, {}, { timeout: 3000 });
    const retry = screen.getByRole("button", { name: "Try again" });
    await switchTo("hi");

    await user.click(retry);

    // The retry goes out as it was (the same turn, the same key); the language change that
    // waited behind the failure is sent after it.
    await vi.waitFor(() => expect(sent).toHaveLength(4));
    expect(sent[2].key).toBe(sent[1].key);
    expect(sent[2].body).toEqual(sent[1].body);
    expect(sent[3].body).toEqual({ language: "hi" });
  });
});

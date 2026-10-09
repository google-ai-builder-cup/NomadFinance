// @vitest-environment jsdom
// Coming back to an interview (NF-FC-019): the banner that says where it stopped, and what the
// worker typed and did not send, which a reload does not lose.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import CoachChat from "@/components/coach/CoachChat";
import { loadNamespace, setLanguage } from "@/lib/i18n";
import { memoryBackend, readEntry, saveEntry, setOutboxBackend } from "@/lib/coachOutboxStore";
import { replaySession, replayTurns, sessionFrom } from "@/mocks/coachTurns";
import { setupMockServer } from "@/mocks/server";
import type { CoachSessionStart } from "@/types/coach";
import { readDraft } from "@/utils/coachDraft";
import { createEntry } from "@/utils/coachOutbox";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
beforeEach(() => {
  setOutboxBackend(memoryBackend());
  localStorage.clear();
});
afterEach(async () => {
  cleanup();
  setOutboxBackend(null);
  await setLanguage("en");
});

const UID = "worker-1";
const hoursAgo = (hours: number) => new Date(Date.now() - hours * 3_600_000).toISOString();

// A Hindi-language interview in the debt stage, 13 messages in (`resumed` as the start route says).
const resumed = (changes: Partial<CoachSessionStart> = {}) =>
  sessionFrom("coach/session-02-debt.json", {
    resumed: true,
    last_active: hoursAgo(2),
    ...changes,
  });

function renderChat(session: CoachSessionStart, onRestart = vi.fn(), uid: string | null = UID) {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <CoachChat
          session={session}
          onRestart={onRestart}
          timing={{ retryDelayMs: 0 }}
          uid={uid ?? undefined}
        />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return onRestart;
}

// The banner waits for the look at what an earlier visit left waiting, so it appears a moment
// after the chat; "not shown" is judged after that moment has passed.
const banner = () => screen.findByRole("region", { name: "Welcome back" });
const noBanner = async () => {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 30));
  });
  expect(screen.queryByRole("region", { name: "Welcome back" })).toBeNull();
};
const button = (name: string) => screen.getByRole("button", { name });

describe("the resume banner", () => {
  it("says where the interview stopped, how long ago, and that the answers are saved", async () => {
    renderChat(resumed());

    expect((await banner()).textContent).toContain(
      "Step 4 of 6: Debt. You last answered 2 hours ago. Your answers are saved."
    );
  });

  it("leaves out the time when the last answer was under a minute ago", async () => {
    renderChat(resumed({ last_active: new Date().toISOString() }));

    expect((await banner()).textContent).toContain("Step 4 of 6: Debt. Your answers are saved.");
    expect((await banner()).textContent).not.toContain("last answered");
  });

  it("is in the worker's language", async () => {
    await setLanguage("hi");
    renderChat(resumed());

    const hindi = await screen.findByRole("region", { name: "आपका फिर से स्वागत है" });

    expect(hindi.textContent).toContain("चरण 4 / 6: कर्ज़");
    expect(hindi.textContent).toMatch(/घंटे/);
  });

  it("is not shown for a new interview", async () => {
    renderChat(sessionFrom("coach/sessions-create-01-new.json", { resumed: false }));

    await noBanner();
  });

  it("is not shown for an interview that was just started and has no messages yet", async () => {
    replayTurns("coach/turn-01-start.sse");
    renderChat(sessionFrom("coach/sessions-create-01-new.json", { resumed: true }));

    await noBanner();
  });

  it("is not shown once the answers are confirmed", async () => {
    replaySession();
    renderChat(resumed({ stage: "plan", next_slot: null }));

    await noBanner();
  });

  it("is not shown while an answer waits for a connection: that notice says it", async () => {
    await saveEntry({
      ...createEntry({
        request: {
          sessionId: "s_02",
          text: "None (0)",
          language: "en",
          idempotencyKey: "key-0123456789abcdef",
        },
        uid: UID,
        turnCount: 6,
        url: "http://localhost/api/v2/coach/sessions/s_02/messages",
        token: null,
        now: Date.now(),
      }),
      claim: { by: "sw", at: Date.now() },
    });

    renderChat(resumed());

    await screen.findByText(/No connection\. Your answer is saved on this phone/);
    await noBanner();
  });

  it("goes when the worker chooses to continue", async () => {
    const onRestart = renderChat(resumed());
    await banner();

    await userEvent.setup().click(button("Continue"));

    await noBanner();
    expect(onRestart).not.toHaveBeenCalled();
  });

  it("goes at the worker's first answer", async () => {
    replayTurns("coach/turn-02-answer.sse");
    renderChat(resumed());
    await banner();

    await userEvent.setup().click(button("None (0)"));

    await noBanner();
    await within(screen.getByRole("log")).findByText(/What kind of work will you do\?/);
  });

  it("asks before starting over, since the answers go with it, and lets the worker back out", async () => {
    const user = userEvent.setup();
    const onRestart = renderChat(resumed());
    await banner();

    await user.click(button("Start a new interview"));

    expect((await banner()).textContent).toContain("closes this one and its answers");
    expect(onRestart).not.toHaveBeenCalled();
    await user.click(button("No, keep going"));
    expect((await banner()).textContent).toContain("Your answers are saved.");
    expect(onRestart).not.toHaveBeenCalled();
  });

  it("starts over when confirmed, and wipes the draft and the waiting answer kept for the old one", async () => {
    const user = userEvent.setup();
    const onRestart = renderChat(resumed());
    await banner();
    await user.click(button("Type my own answer"));
    await user.type(screen.getByRole("textbox", { name: "Your answer" }), "about 3000");
    expect(readDraft(UID, "s_02", "debt:recruitment_fee_paid")["text.text"]).toBe("about 3000");
    await saveEntry(
      createEntry({
        request: {
          sessionId: "s_02",
          text: "x",
          language: "en",
          idempotencyKey: "key-0123456789abcdef",
        },
        uid: UID,
        turnCount: 6,
        url: "http://localhost/x",
        token: null,
        now: Date.now(),
      })
    );

    await user.click(button("Start a new interview"));
    await user.click(button("Yes, start over"));

    expect(onRestart).toHaveBeenCalledTimes(1);
    expect(readDraft(UID, "s_02", "debt:recruitment_fee_paid")).toEqual({});
    await waitFor(async () => expect(await readEntry("s_02")).toBeUndefined());
  });
});

describe("what the worker typed and did not send", () => {
  const question = "debt:recruitment_fee_paid";
  const answerBox = () =>
    screen.getByRole("textbox", { name: "Your answer" }) as HTMLTextAreaElement;

  it("is there again after the page is reloaded, in the answer box", async () => {
    const user = userEvent.setup();
    renderChat(resumed());
    await user.click(button("Type my own answer"));
    await user.type(answerBox(), "I paid the agent about 3000");
    cleanup();

    renderChat(resumed());

    // The box was open when the page went: it is open again, with the words in it.
    expect(answerBox().value).toBe("I paid the agent about 3000");
    expect(screen.queryByRole("button", { name: "Type my own answer" })).toBeNull();
  });

  it("is kept for a helper too: an amount, its currency and how often", async () => {
    const user = userEvent.setup();
    renderChat(resumed({ stage: "income", next_slot: "monthly_salary" }));
    await user.type(screen.getByLabelText("Amount"), "4200");
    await user.selectOptions(screen.getByLabelText("Currency"), "PHP");
    await user.click(button("Per week"));
    cleanup();

    renderChat(resumed({ stage: "income", next_slot: "monthly_salary" }));

    expect((screen.getByLabelText("Amount") as HTMLInputElement).value).toBe("4200");
    expect((screen.getByLabelText("Currency") as HTMLSelectElement).value).toBe("PHP");
    expect(button("Per week").getAttribute("aria-pressed")).toBe("true");
  });

  it("is forgotten once the answer is sent", async () => {
    replayTurns("coach/turn-02-answer.sse");
    const user = userEvent.setup();
    renderChat(resumed());
    await user.click(button("Type my own answer"));
    await user.type(answerBox(), "None");
    expect(readDraft(UID, "s_02", question)["text.text"]).toBe("None");

    await user.click(button("Send"));

    await within(screen.getByRole("log")).findByText(/What kind of work will you do\?/);
    expect(readDraft(UID, "s_02", question)["text.text"]).toBeUndefined();
    expect(localStorage.length).toBe(0);
  });

  it("does not follow the worker to another question: a new question starts empty", async () => {
    const user = userEvent.setup();
    renderChat(resumed());
    await user.click(button("Type my own answer"));
    await user.type(answerBox(), "about 3000");
    cleanup();

    renderChat(resumed({ stage: "savings", next_slot: "savings" }));

    expect(screen.queryByRole("textbox", { name: "Your answer" })).toBeNull();
    expect(button("Type my own answer")).toBeTruthy();
  });

  it("is not offered to another person on the same phone", async () => {
    const user = userEvent.setup();
    renderChat(resumed());
    await user.click(button("Type my own answer"));
    await user.type(answerBox(), "private words");
    cleanup();

    renderChat(resumed(), vi.fn(), "someone-else");

    expect(screen.queryByRole("textbox", { name: "Your answer" })).toBeNull();
  });

  it("is not kept at all when there is no signed-in person to keep it for", async () => {
    const user = userEvent.setup();
    renderChat(resumed(), vi.fn(), null);
    await user.click(button("Type my own answer"));
    await user.type(answerBox(), "nothing is stored");

    expect(localStorage.length).toBe(0);
  });
});

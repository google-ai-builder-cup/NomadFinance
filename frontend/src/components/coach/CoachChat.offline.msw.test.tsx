// @vitest-environment jsdom
// The Coach's offline queue (NF-FC-019) against the recorded streams: an answer sent with no
// connection waits on the phone and goes, once, with the same key, when the connection returns.
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import CoachChat from "@/components/coach/CoachChat";
import { loadNamespace } from "@/lib/i18n";
import {
  memoryBackend,
  readEntry,
  removeEntry,
  saveEntry,
  setOutboxBackend,
  type OutboxBackend,
} from "@/lib/coachOutboxStore";
import { replayTurns, sessionFrom } from "@/mocks/coachTurns";
import { server, setupMockServer } from "@/mocks/server";
import type { CoachSessionStart } from "@/types/coach";
import { createEntry, withClaim, type OutboxEntry } from "@/utils/coachOutbox";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
beforeEach(() => {
  setOutboxBackend(memoryBackend());
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  setOutboxBackend(null);
  vi.restoreAllMocks();
});

const UID = "worker-1";
// No wait before the second try of a dropped stream, and a quick look when another sender has it.
const FAST = { retryDelayMs: 0, recheckMs: 20, storageMs: 50 };

// An interview with a transcript, asking for the recruitment fee: "None (0)" is one tap.
const session = () => sessionFrom("coach/session-02-debt.json");

function renderChat(start: CoachChatSession = session(), uid: string | null = UID) {
  return render(
    <MemoryRouter>
      <CoachChat session={start} onRestart={vi.fn()} timing={FAST} uid={uid ?? undefined} />
    </MemoryRouter>
  );
}
type CoachChatSession = CoachSessionStart;

const log = () => screen.getByRole("log");
const chip = (name: string) => screen.getByRole("button", { name }) as HTMLButtonElement;
const inLog = (text: RegExp) => within(log()).findByText(text, {}, { timeout: 3000 });
const waitingNotice = () => screen.findByText(/No connection\. Your answer is saved on this phone/);
const reconnect = () => act(() => void window.dispatchEvent(new Event("online")));

/** Every request fails as it does with no connection; the keys it saw are recorded. */
function noConnection(): (string | null)[] {
  const keys: (string | null)[] = [];
  server.use(
    http.post("*/api/v2/coach/sessions/:id/messages", ({ request }) => {
      keys.push(request.headers.get("Idempotency-Key"));
      return HttpResponse.error();
    })
  );
  return keys;
}

function waitingEntry(overrides: Partial<OutboxEntry> = {}): OutboxEntry {
  return {
    ...createEntry({
      request: {
        sessionId: session().id,
        text: "None (0)",
        language: "en",
        idempotencyKey: "key-0123456789abcdef",
      },
      uid: UID,
      turnCount: session().turn_count,
      url: "http://localhost/api/v2/coach/sessions/s_02/messages",
      token: null,
      now: Date.now(),
    }),
    ...overrides,
  };
}

describe("an answer sent with no connection", () => {
  it("is kept, shown as waiting, and the panel is locked", async () => {
    const attempts = noConnection();
    renderChat();

    await userEvent.setup().click(chip("None (0)"));

    await waitingNotice();
    expect(within(log()).getByText("Waiting for signal")).toBeTruthy();
    expect(within(log()).getByText("None (0)")).toBeTruthy();
    // Not a failure: nothing is wrong with the answer.
    expect(screen.queryByText("Not sent")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(chip("None (0)").disabled).toBe(true);
    expect(await readEntry(session().id)).toMatchObject({
      text: "None (0)",
      language: "en",
      uid: UID,
      idempotencyKey: attempts[0],
      turnCount: session().turn_count,
      claim: null,
      rejected: null,
    });
  });

  it("is sent once, with the same key, when the connection returns", async () => {
    const attempts = noConnection();
    renderChat();
    await userEvent.setup().click(chip("None (0)"));
    await waitingNotice();
    const sent = replayTurns("coach/turn-02-answer.sse");

    reconnect();

    await inLog(/What kind of work will you do\?/);
    expect(sent).toHaveLength(1);
    expect(sent[0].key).toBe(attempts[0]);
    expect(sent[0].body).toEqual({ text: "None (0)", language: "en" });
    expect(screen.queryByText("Waiting for signal")).toBeNull();
    expect(screen.queryByText(/No connection/)).toBeNull();
    expect(await readEntry(session().id)).toBeUndefined();
    // The panel is open again, with the next question's helper.
    expect(chip("Care worker").disabled).toBe(false);
  });

  it("stays waiting, with the same key, when the connection comes and goes", async () => {
    const attempts = noConnection();
    renderChat();
    await userEvent.setup().click(chip("None (0)"));
    await waitingNotice();

    reconnect();

    await waitFor(() => expect(attempts).toHaveLength(2));
    await waitingNotice();
    expect(attempts[1]).toBe(attempts[0]);
    expect(within(log()).getByText("Waiting for signal")).toBeTruthy();
    expect(await readEntry(session().id)).toMatchObject({ idempotencyKey: attempts[0] });
  });

  it("is sent at once by Send now, without waiting for the connection to be noticed", async () => {
    const attempts = noConnection();
    const user = userEvent.setup();
    renderChat();
    await user.click(chip("None (0)"));
    await waitingNotice();
    const sent = replayTurns("coach/turn-02-answer.sse");

    await user.click(screen.getByRole("button", { name: "Send now" }));

    await inLog(/What kind of work will you do\?/);
    expect(sent).toHaveLength(1);
    expect(sent[0].key).toBe(attempts[0]);
  });

  it("cannot be followed by a second answer while it waits", async () => {
    noConnection();
    renderChat();
    await userEvent.setup().click(chip("None (0)"));
    await waitingNotice();
    const sent = replayTurns("coach/turn-02-answer.sse");

    await userEvent.setup().click(chip("None (0)"));

    expect(sent).toHaveLength(0);
  });

  it("is kept when the stream broke while the device was offline", async () => {
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    replayTurns({ bytes: 'event: token\ndata: {"text":"Thanks"}\n\n' });
    renderChat();

    await userEvent.setup().click(chip("None (0)"));

    await waitingNotice();
    expect(await readEntry(session().id)).toMatchObject({ text: "None (0)" });
  });

  it("is not kept when the server answers, even with an error", async () => {
    replayTurns({ refusal: "coach/turn-error-ai-busy.json" });
    renderChat();

    await userEvent.setup().click(chip("None (0)"));

    await screen.findByText(/The coach is busy right now/);
    expect(screen.queryByText(/No connection/)).toBeNull();
    expect(await readEntry(session().id)).toBeUndefined();
  });

  it("waits in memory, and still goes, when there is no signed-in person to keep it for", async () => {
    const attempts = noConnection();
    renderChat(session(), null);
    await userEvent.setup().click(chip("None (0)"));
    await waitingNotice();
    const sent = replayTurns("coach/turn-02-answer.sse");

    expect(await readEntry(session().id)).toBeUndefined();
    reconnect();

    await inLog(/What kind of work will you do\?/);
    expect(sent[0].key).toBe(attempts[0]);
  });
});

describe("an answer left waiting by an earlier visit", () => {
  it("is shown as waiting after a reload, and sent once when the screen opens online", async () => {
    const attempts = noConnection();
    renderChat();
    await userEvent.setup().click(chip("None (0)"));
    await waitingNotice();
    cleanup();
    const sent = replayTurns("coach/turn-02-answer.sse");

    renderChat();

    await inLog(/What kind of work will you do\?/);
    expect(within(log()).getByText("None (0)")).toBeTruthy();
    expect(sent).toHaveLength(1);
    expect(sent[0].key).toBe(attempts[0]);
    expect(await readEntry(session().id)).toBeUndefined();
  });

  it("waits for the connection when the screen opens offline, then goes", async () => {
    await saveEntry(waitingEntry());
    const online = vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    const sent = replayTurns("coach/turn-02-answer.sse");

    renderChat();

    await waitingNotice();
    expect(within(log()).getByText("Waiting for signal")).toBeTruthy();
    expect(sent).toHaveLength(0);
    online.mockReturnValue(true);
    reconnect();
    await inLog(/What kind of work will you do\?/);
    expect(sent[0].key).toBe("key-0123456789abcdef");
  });

  it("is dropped when the server has already saved it: its transcript has it", async () => {
    await saveEntry(waitingEntry({ turnCount: 2 }));
    const sent = replayTurns("coach/turn-02-answer.sse");

    renderChat();

    await waitFor(async () => expect(await readEntry(session().id)).toBeUndefined());
    expect(sent).toHaveLength(0);
    expect(screen.queryByText("Waiting for signal")).toBeNull();
    expect(chip("None (0)").disabled).toBe(false);
  });

  it("is shown as not sent, with the reason, when the server refused it for good", async () => {
    await saveEntry(waitingEntry({ rejected: "session_not_active" }));
    const sent = replayTurns("coach/turn-02-answer.sse");

    renderChat();

    await screen.findByText("This interview is finished. You can start a new one.");
    expect(within(log()).getByText("Not sent")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Start a new interview" })).toBeTruthy();
    expect(sent).toHaveLength(0);
    await waitFor(async () => expect(await readEntry(session().id)).toBeUndefined());
  });

  it("is shown as not sent with the usual words for a refusal the worker has no code for", async () => {
    await saveEntry(waitingEntry({ rejected: "http_413" }));

    renderChat();

    await screen.findByText(/Something went wrong/i);
    expect(within(log()).getByText("Not sent")).toBeTruthy();
  });

  it("is ignored when it belongs to another person on the same phone", async () => {
    await saveEntry(waitingEntry({ uid: "someone-else" }));
    const sent = replayTurns("coach/turn-02-answer.sse");

    renderChat();

    await waitFor(() => expect(chip("None (0)").disabled).toBe(false));
    expect(screen.queryByText("Waiting for signal")).toBeNull();
    expect(sent).toHaveLength(0);
    expect(await readEntry(session().id)).toBeDefined();
  });

  it("is left to the service worker while it holds it, then confirmed by asking again", async () => {
    await saveEntry(withClaim(waitingEntry(), "sw", Date.now()));
    const sent = replayTurns("coach/turn-02-answer.sse");

    renderChat();

    await waitingNotice();
    // The worker is sending it: the screen sends nothing of its own.
    await new Promise((resolve) => setTimeout(resolve, 80));
    expect(sent).toHaveLength(0);
    // The worker finished and removed it: asking again replays the turn, so the reply appears.
    await removeEntry(session().id);
    await inLog(/What kind of work will you do\?/);
    expect(sent).toHaveLength(1);
    expect(sent[0].key).toBe("key-0123456789abcdef");
  });

  it("lets go of the answer it was sending when the screen is left", async () => {
    await saveEntry(waitingEntry());
    server.use(http.post("*/api/v2/coach/sessions/:id/messages", () => new Promise(() => {})));

    renderChat();
    await waitFor(async () =>
      expect((await readEntry(session().id))?.claim).toMatchObject({ by: "page" })
    );
    cleanup();

    await waitFor(async () => expect((await readEntry(session().id))?.claim).toBeNull());
  });
});

describe("storage that does not answer", () => {
  const hung: OutboxBackend = {
    get: () => new Promise(() => {}),
    put: () => new Promise(() => {}),
    delete: () => new Promise(() => {}),
    update: () => new Promise(() => {}),
  };

  it("does not keep the screen locked when it opens", async () => {
    setOutboxBackend(hung);
    renderChat();

    await waitFor(() => expect(chip("None (0)").disabled).toBe(false));
  });

  it("does not keep the answer from showing as waiting when it cannot be written down", async () => {
    setOutboxBackend(memoryBackend());
    noConnection();
    renderChat();
    await waitFor(() => expect(chip("None (0)").disabled).toBe(false));
    setOutboxBackend(hung);

    await userEvent.setup().click(chip("None (0)"));

    await waitingNotice();
    expect(within(log()).getByText("Waiting for signal")).toBeTruthy();
  });
});

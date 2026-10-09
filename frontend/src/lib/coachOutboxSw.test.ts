// @vitest-environment jsdom
// The service worker script (public/coach-outbox-sw.js) is plain JavaScript that no bundler touches,
// so it is loaded here as the browser would run it, against the same stand-in IndexedDB as the
// page's storage layer. That also checks that the two agree on the database and the entry.
import { readFileSync } from "node:fs";
import path from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  claimEntry,
  indexedDbBackend,
  readEntry,
  saveEntry,
  setOutboxBackend,
} from "@/lib/coachOutboxStore";
import { createFakeIndexedDb } from "@/mocks/fakeIndexedDb";
import {
  CLAIM_LEASE_MS,
  OUTBOX_MAX_AGE_MS,
  createEntry,
  type OutboxEntry,
} from "@/utils/coachOutbox";
import {
  OUTBOX_DB_NAME,
  OUTBOX_DB_VERSION,
  OUTBOX_STORE,
  OUTBOX_SYNC_TAG,
} from "@/utils/coachStorageKeys";

const SOURCE = readFileSync(path.resolve(__dirname, "../../public/coach-outbox-sw.js"), "utf8");
const NOW = Date.parse("2026-10-20T10:00:00Z");

type Handler = (event: { tag?: string; waitUntil: (work: Promise<unknown>) => void }) => void;

/** Runs the script as a worker would, and returns what a `sync` event does. */
function loadWorker(fetchStub: (url: string, init: RequestInit) => Promise<Response>) {
  const handlers = new Map<string, Handler>();
  const self = {
    addEventListener: (type: string, handler: Handler) => handlers.set(type, handler),
    skipWaiting: vi.fn(),
    indexedDB: globalThis.indexedDB,
    fetch: fetchStub,
  };
  new Function("self", SOURCE)(self);
  return {
    self,
    install: () => handlers.get("install")?.({ waitUntil: () => undefined }),
    /** Fires a sync event; resolves when the work ends, rejects if the browser should retry. */
    sync: (tag = OUTBOX_SYNC_TAG) => {
      let work: Promise<unknown> = Promise.resolve();
      handlers.get("sync")?.({ tag, waitUntil: (promise) => (work = promise) });
      return work;
    },
  };
}

const DONE_STREAM =
  'event: token\ndata: {"text":"Thanks."}\n\nevent: done\ndata: {"message_id":"m_9"}\n\n';
const stream = (body = DONE_STREAM) =>
  new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
const refusal = (status: number, code: string, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify({ code, message: "x", request_id: "r" }), { status, headers });

function entry(overrides: Partial<OutboxEntry> = {}): OutboxEntry {
  return {
    ...createEntry({
      request: {
        sessionId: "s_01",
        text: "4200 AUD per month",
        language: "hi",
        idempotencyKey: "key-0123456789abcdef",
      },
      uid: "worker-1",
      turnCount: 3,
      url: "https://api.example/api/v2/coach/sessions/s_01/messages",
      token: "token-1",
      now: Date.now(),
    }),
    token: "token-1",
    tokenExpiresAt: Date.now() + 3_600_000,
    ...overrides,
  };
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  vi.stubGlobal("indexedDB", createFakeIndexedDb());
  setOutboxBackend(indexedDbBackend());
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  setOutboxBackend(null);
});

describe("the worker's names", () => {
  it("are the ones the page uses", () => {
    expect(SOURCE).toContain(`const DB_NAME = "${OUTBOX_DB_NAME}";`);
    expect(SOURCE).toContain(`const DB_VERSION = ${OUTBOX_DB_VERSION};`);
    expect(SOURCE).toContain(`const STORE = "${OUTBOX_STORE}";`);
    expect(SOURCE).toContain(`const SYNC_TAG = "${OUTBOX_SYNC_TAG}";`);
  });

  it("takes over at once when installed", () => {
    const worker = loadWorker(vi.fn());

    worker.install();

    expect(worker.self.skipWaiting).toHaveBeenCalledTimes(1);
  });

  it("ignores a sync with another tag", async () => {
    const fetchStub = vi.fn();
    const worker = loadWorker(fetchStub);
    await saveEntry(entry());

    await worker.sync("something-else");

    expect(fetchStub).not.toHaveBeenCalled();
    expect(await readEntry("s_01")).toBeDefined();
  });
});

describe("a sync when the connection is back", () => {
  it("sends the answer with the same key, token and words, then removes it", async () => {
    const fetchStub = vi.fn(async () => stream());
    const worker = loadWorker(fetchStub);
    await saveEntry(entry());

    await worker.sync();

    expect(fetchStub).toHaveBeenCalledTimes(1);
    const [url, init] = fetchStub.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.example/api/v2/coach/sessions/s_01/messages");
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({
      Authorization: "Bearer token-1",
      "Idempotency-Key": "key-0123456789abcdef",
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    });
    expect(JSON.parse(init.body as string)).toEqual({ text: "4200 AUD per month", language: "hi" });
    expect(await readEntry("s_01")).toBeUndefined();
  });

  it("keeps the answer and asks the browser to try again when the stream ends without `done`", async () => {
    const worker = loadWorker(async () => stream('event: token\ndata: {"text":"Tha"}\n\n'));
    await saveEntry(entry());

    await expect(worker.sync()).rejects.toThrow(/still waiting/);

    const kept = await readEntry("s_01");
    expect(kept).toBeDefined();
    expect(kept?.claim).toBeNull();
  });

  it("keeps the answer and tries again when the stream says the turn failed", async () => {
    const worker = loadWorker(async () =>
      stream('event: error\ndata: {"code":"ai_bad_response","message":"x"}\n\n')
    );
    await saveEntry(entry());

    await expect(worker.sync()).rejects.toThrow();

    expect(await readEntry("s_01")).toBeDefined();
  });

  it("keeps the answer and tries again on a network error", async () => {
    const worker = loadWorker(async () => {
      throw new TypeError("Failed to fetch");
    });
    await saveEntry(entry());

    await expect(worker.sync()).rejects.toThrow();

    expect((await readEntry("s_01"))?.claim).toBeNull();
  });

  it.each([
    [429, "rate_limited"],
    [503, "ai_busy"],
    [409, "request_in_progress"],
    [409, "turn_in_progress"],
  ])("keeps the answer and tries again on %i %s", async (status, code) => {
    const worker = loadWorker(async () => refusal(status, code));
    await saveEntry(entry());

    await expect(worker.sync()).rejects.toThrow();

    expect(await readEntry("s_01")).toBeDefined();
  });

  it("leaves the answer for the screen, without a retry, when the token is refused", async () => {
    const worker = loadWorker(async () => refusal(401, "unauthenticated"));
    await saveEntry(entry());

    await worker.sync();

    const kept = await readEntry("s_01");
    expect(kept?.claim).toBeNull();
    expect(kept?.rejected).toBeNull();
  });

  it.each([
    [409, "session_not_active"],
    [404, "not_found"],
    [422, "validation_failed"],
  ])(
    "marks the answer as refused for good on %i %s, for the screen to show",
    async (status, code) => {
      const worker = loadWorker(async () => refusal(status, code));
      await saveEntry(entry());

      await worker.sync();

      const kept = await readEntry("s_01");
      expect(kept?.rejected).toBe(code);
      expect(kept?.claim).toBeNull();
    }
  );

  it("names a refusal that has no code by its status", async () => {
    const worker = loadWorker(async () => new Response("<html>", { status: 413 }));
    await saveEntry(entry());

    await worker.sync();

    expect((await readEntry("s_01"))?.rejected).toBe("http_413");
  });
});

describe("what the worker does not send", () => {
  it("does not send with a token that has lapsed or is about to: the screen does it later", async () => {
    const fetchStub = vi.fn(async () => stream());
    const worker = loadWorker(fetchStub);
    await saveEntry(entry({ tokenExpiresAt: Date.now() + 30_000 }));

    await worker.sync();

    expect(fetchStub).not.toHaveBeenCalled();
    expect(await readEntry("s_01")).toBeDefined();
  });

  it("does not send with no token at all", async () => {
    const fetchStub = vi.fn(async () => stream());
    const worker = loadWorker(fetchStub);
    await saveEntry(entry({ token: null, tokenExpiresAt: null }));

    await worker.sync();

    expect(fetchStub).not.toHaveBeenCalled();
  });

  it("does not send an answer the server already refused for good", async () => {
    const fetchStub = vi.fn(async () => stream());
    const worker = loadWorker(fetchStub);
    await saveEntry(entry({ rejected: "session_not_active" }));

    await worker.sync();

    expect(fetchStub).not.toHaveBeenCalled();
  });

  it("does not send an answer the screen is sending, and asks to be run again", async () => {
    const fetchStub = vi.fn(async () => stream());
    const worker = loadWorker(fetchStub);
    await saveEntry(entry());
    await claimEntry("s_01", "page", Date.now());

    await expect(worker.sync()).rejects.toThrow();

    expect(fetchStub).not.toHaveBeenCalled();
  });

  it("takes over an answer whose sender died, once the lease has run out", async () => {
    const fetchStub = vi.fn(async () => stream());
    const worker = loadWorker(fetchStub);
    await saveEntry(entry({ claim: { by: "page", at: Date.now() - CLAIM_LEASE_MS } }));

    await worker.sync();

    expect(fetchStub).toHaveBeenCalledTimes(1);
    expect(await readEntry("s_01")).toBeUndefined();
  });

  it("drops an answer older than an interview can live, without sending it", async () => {
    const fetchStub = vi.fn(async () => stream());
    const worker = loadWorker(fetchStub);
    await saveEntry(entry({ queuedAt: Date.now() - OUTBOX_MAX_AGE_MS - 1 }));

    await worker.sync();

    expect(fetchStub).not.toHaveBeenCalled();
    expect(await readEntry("s_01")).toBeUndefined();
  });

  it("does nothing when there is nothing waiting", async () => {
    const fetchStub = vi.fn();
    const worker = loadWorker(fetchStub);

    await worker.sync();

    expect(fetchStub).not.toHaveBeenCalled();
  });
});

describe("two senders", () => {
  it("never both send: of the worker and the screen asking at once, exactly one gets the answer", async () => {
    const fetchStub = vi.fn(async () => stream());
    const worker = loadWorker(fetchStub);
    await saveEntry(entry());

    const [, fromPage] = await Promise.allSettled([
      worker.sync(),
      claimEntry("s_01", "page", Date.now()),
    ]);

    const workerSent = fetchStub.mock.calls.length === 1;
    const pageClaimed = fromPage.status === "fulfilled" && fromPage.value.status === "claimed";
    expect(workerSent).not.toBe(pageClaimed);
  });
});

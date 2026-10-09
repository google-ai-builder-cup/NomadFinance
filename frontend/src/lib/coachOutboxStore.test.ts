// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  claimEntry,
  indexedDbBackend,
  memoryBackend,
  prepareBackgroundSync,
  readEntry,
  releaseEntry,
  removeEntry,
  requestBackgroundSync,
  saveEntry,
  setOutboxBackend,
  type OutboxBackend,
} from "@/lib/coachOutboxStore";
import { createFakeIndexedDb } from "@/mocks/fakeIndexedDb";
import { CLAIM_LEASE_MS, createEntry, type OutboxEntry } from "@/utils/coachOutbox";

const NOW = Date.parse("2026-10-20T10:00:00Z");

function entry(id = "s_01"): OutboxEntry {
  return createEntry({
    request: {
      sessionId: id,
      text: "Care work",
      language: "en",
      idempotencyKey: "key-0123456789abcdef",
    },
    uid: "worker-1",
    turnCount: 2,
    url: "https://api.example/api/v2/coach/sessions/s_01/messages",
    token: null,
    now: NOW,
  });
}

afterEach(() => {
  setOutboxBackend(null);
  vi.unstubAllGlobals();
});

// The same rules must hold in memory and in IndexedDB (here a stand-in that runs one transaction
// at a time, as a browser does).
const BACKENDS: [string, () => OutboxBackend][] = [
  ["memory", memoryBackend],
  [
    "IndexedDB",
    () => {
      vi.stubGlobal("indexedDB", createFakeIndexedDb());
      return indexedDbBackend();
    },
  ],
];

describe.each(BACKENDS)("the waiting answer in %s", (_name, make) => {
  it("is saved, read back, and removed", async () => {
    setOutboxBackend(make());

    expect(await readEntry("s_01")).toBeUndefined();
    await saveEntry(entry());
    expect(await readEntry("s_01")).toEqual(entry());
    await removeEntry("s_01");
    expect(await readEntry("s_01")).toBeUndefined();
  });

  it("is taken by one sender, and the other is told it is busy", async () => {
    setOutboxBackend(make());
    await saveEntry(entry());

    const first = await claimEntry("s_01", "sw", NOW);
    const second = await claimEntry("s_01", "page", NOW + 1_000);

    expect(first).toMatchObject({ status: "claimed", entry: { claim: { by: "sw", at: NOW } } });
    expect(second).toEqual({ status: "busy" });
  });

  it("is taken by exactly one of two senders that ask at the same moment", async () => {
    setOutboxBackend(make());
    await saveEntry(entry());

    const results = await Promise.all([
      claimEntry("s_01", "page", NOW),
      claimEntry("s_01", "sw", NOW),
    ]);

    expect(results.filter((result) => result.status === "claimed")).toHaveLength(1);
    expect(results.filter((result) => result.status === "busy")).toHaveLength(1);
  });

  it("can be taken over once the lease has run out", async () => {
    setOutboxBackend(make());
    await saveEntry(entry());
    await claimEntry("s_01", "sw", NOW);

    const late = await claimEntry("s_01", "page", NOW + CLAIM_LEASE_MS);

    expect(late).toMatchObject({ status: "claimed", entry: { claim: { by: "page" } } });
  });

  it("can be taken again after it is released", async () => {
    setOutboxBackend(make());
    await saveEntry(entry());
    await claimEntry("s_01", "page", NOW);
    await releaseEntry("s_01");

    expect((await readEntry("s_01"))?.claim).toBeNull();
    expect((await claimEntry("s_01", "sw", NOW + 1)).status).toBe("claimed");
  });

  it("is `gone` when someone else has already sent it", async () => {
    setOutboxBackend(make());

    expect(await claimEntry("s_01", "page", NOW)).toEqual({ status: "gone" });
  });

  it("is overwritten, with the claim cleared, when it is kept again after a failed send", async () => {
    setOutboxBackend(make());
    await saveEntry(entry());
    await claimEntry("s_01", "page", NOW);

    await saveEntry(entry());

    expect((await readEntry("s_01"))?.claim).toBeNull();
  });
});

describe("choosing where to keep it", () => {
  it("falls back to memory where there is no IndexedDB", async () => {
    vi.stubGlobal("indexedDB", undefined);

    await saveEntry(entry());

    expect(await readEntry("s_01")).toEqual(entry());
  });

  it("falls back to memory when IndexedDB refuses, and the answer is still kept", async () => {
    vi.stubGlobal("indexedDB", {
      open: () => {
        throw new Error("The user denied permission to access the database.");
      },
    });

    await saveEntry(entry());

    expect(await readEntry("s_01")).toEqual(entry());
  });
});

// The worker is installed by the screen and woken by the browser; both ends are stood in for here.
describe("the service worker", () => {
  function stubServiceWorker(
    options: { sync?: "works" | "refuses" | "missing"; state?: string } = {}
  ) {
    const register = vi.fn(async () => undefined);
    const listeners: (() => void)[] = [];
    const worker = {
      state: options.state ?? "activated",
      addEventListener: (_type: string, listener: () => void) => listeners.push(listener),
      removeEventListener: () => undefined,
    };
    const registration = {
      installing: null,
      waiting: null,
      active: worker,
      ...(options.sync === "missing"
        ? {}
        : {
            sync: {
              register:
                options.sync === "refuses"
                  ? vi.fn(async () => {
                      throw new Error("Background Sync is disabled.");
                    })
                  : register,
            },
          }),
    };
    const registerWorker = vi.fn(async () => registration);
    vi.stubGlobal("navigator", { ...navigator, serviceWorker: { register: registerWorker } });
    return { registerWorker, register, worker, listeners };
  }

  it("is installed on its own scope, away from the app's own worker", async () => {
    const { registerWorker } = stubServiceWorker();

    prepareBackgroundSync();
    await vi.waitFor(() => expect(registerWorker).toHaveBeenCalledTimes(1));

    expect(registerWorker).toHaveBeenCalledWith("/coach-outbox-sw.js", {
      scope: "/coach-outbox-scope",
    });
  });

  it("asks the browser to wake it when the connection is back", async () => {
    const { register } = stubServiceWorker();

    expect(await requestBackgroundSync()).toBe(true);
    expect(register).toHaveBeenCalledWith("coach-outbox");
  });

  it("waits for a worker that is still installing", async () => {
    const { worker, listeners, register } = stubServiceWorker({ state: "installing" });

    const asked = requestBackgroundSync();
    await Promise.resolve();
    expect(register).not.toHaveBeenCalled();
    worker.state = "activated";
    listeners.forEach((listener) => listener());

    expect(await asked).toBe(true);
  });

  it("says no, without failing, where Background Sync does not exist", async () => {
    stubServiceWorker({ sync: "missing" });

    expect(await requestBackgroundSync()).toBe(false);
  });

  it("says no, without failing, where the browser has it switched off", async () => {
    stubServiceWorker({ sync: "refuses" });

    expect(await requestBackgroundSync()).toBe(false);
  });

  it("says no, without failing, where there are no service workers at all", async () => {
    vi.stubGlobal("navigator", {});

    expect(await requestBackgroundSync()).toBe(false);
    expect(() => prepareBackgroundSync()).not.toThrow();
  });

  it("says no, without failing, when installing the worker fails", async () => {
    vi.stubGlobal("navigator", {
      serviceWorker: {
        register: async () => {
          throw new Error("A bad HTTP response code (404) was received when fetching the script.");
        },
      },
    });

    expect(await requestBackgroundSync()).toBe(false);
  });
});

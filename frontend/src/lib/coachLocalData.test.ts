// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { clearCoachLocalData } from "@/lib/coachLocalData";
import { indexedDbBackend, readEntry, saveEntry, setOutboxBackend } from "@/lib/coachOutboxStore";
import { createFakeIndexedDb } from "@/mocks/fakeIndexedDb";
import { readDraft, writeDraft } from "@/utils/coachDraft";
import { createEntry } from "@/utils/coachOutbox";

afterEach(() => {
  setOutboxBackend(null);
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("clearCoachLocalData", () => {
  it("removes every draft and every waiting answer, and nothing else", async () => {
    vi.stubGlobal("indexedDB", createFakeIndexedDb());
    setOutboxBackend(indexedDbBackend());
    writeDraft("u1", "s1", "q", { "text.text": "my debt is 3000" });
    writeDraft("u2", "s2", "q", { "text.text": "another person" });
    localStorage.setItem("something-else", "kept");
    await saveEntry(
      createEntry({
        request: {
          sessionId: "s1",
          text: "Care work",
          language: "en",
          idempotencyKey: "k-0123456789abcdef",
        },
        uid: "u1",
        turnCount: 1,
        url: "https://api.example/x",
        token: "token-1",
        now: Date.now(),
      })
    );

    clearCoachLocalData();
    // The database is deleted on the next tick; a fresh connection finds it empty.
    await new Promise((resolve) => setTimeout(resolve, 0));
    setOutboxBackend(indexedDbBackend());

    expect(readDraft("u1", "s1", "q")).toEqual({});
    expect(readDraft("u2", "s2", "q")).toEqual({});
    expect(localStorage.getItem("something-else")).toBe("kept");
    expect(await readEntry("s1")).toBeUndefined();
  });

  it("does nothing, and does not throw, where there is no storage", () => {
    vi.stubGlobal("indexedDB", undefined);

    expect(() => clearCoachLocalData()).not.toThrow();
  });
});

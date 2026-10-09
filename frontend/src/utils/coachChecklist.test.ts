// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { readTicks, writeTicks } from "@/utils/coachChecklist";
import { CHECKLIST_KEY_PREFIX } from "@/utils/coachStorageKeys";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("the ticks of a plan's checklist", () => {
  it("are kept per person and per plan, as ids only", () => {
    writeTicks("alice", "plan1", new Set(["keep_documents", "track_spending"]));
    writeTicks("bob", "plan1", new Set(["open_pay_account"]));
    writeTicks("alice", "plan2", new Set(["x"]));

    expect([...readTicks("alice", "plan1")]).toEqual(["keep_documents", "track_spending"]);
    expect([...readTicks("bob", "plan1")]).toEqual(["open_pay_account"]);
    expect([...readTicks("alice", "plan2")]).toEqual(["x"]);
    expect(localStorage.getItem(`${CHECKLIST_KEY_PREFIX}alice.plan1`)).toBe(
      '["keep_documents","track_spending"]'
    );
  });

  it("start empty, and an emptied list leaves nothing behind", () => {
    expect(readTicks("alice", "none").size).toBe(0);
    writeTicks("alice", "p", new Set(["a"]));
    writeTicks("alice", "p", new Set());

    expect(localStorage.getItem(`${CHECKLIST_KEY_PREFIX}alice.p`)).toBeNull();
  });

  it("ignore anything stored that is not a list of ids", () => {
    localStorage.setItem(`${CHECKLIST_KEY_PREFIX}alice.p`, "{not json");
    expect(readTicks("alice", "p").size).toBe(0);
    localStorage.setItem(`${CHECKLIST_KEY_PREFIX}alice.p`, '{"a":1}');
    expect(readTicks("alice", "p").size).toBe(0);
    localStorage.setItem(`${CHECKLIST_KEY_PREFIX}alice.p`, '["ok", 5, null]');
    expect([...readTicks("alice", "p")]).toEqual(["ok"]);
  });

  it("never throw when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(readTicks("alice", "p").size).toBe(0);
    expect(() => writeTicks("alice", "p", new Set(["a"]))).not.toThrow();
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";

import { newIdempotencyKey } from "@/utils/idempotency";

// v2-conventions: 16 to 64 characters from A-Za-z0-9_-.
const ACCEPTED = /^[A-Za-z0-9_-]{16,64}$/;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("newIdempotencyKey", () => {
  it("makes a key the server accepts, a different one each time", () => {
    const keys = new Set(Array.from({ length: 50 }, () => newIdempotencyKey()));

    expect(keys.size).toBe(50);
    for (const key of keys) {
      expect(key).toMatch(ACCEPTED);
    }
  });

  it("still makes one on a page where randomUUID does not exist (plain http)", () => {
    vi.stubGlobal("crypto", { getRandomValues: globalThis.crypto.getRandomValues.bind(crypto) });

    const key = newIdempotencyKey();

    expect(key).toMatch(ACCEPTED);
    expect(newIdempotencyKey()).not.toBe(key);
  });
});

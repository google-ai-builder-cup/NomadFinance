import { describe, expect, it } from "vitest";

import type { CoachFailure, CoachTurnRequest } from "@/types/coach";
import {
  CLAIM_LEASE_MS,
  OUTBOX_MAX_AGE_MS,
  TOKEN_MARGIN_MS,
  createEntry,
  isClaimable,
  isExpired,
  shouldQueue,
  toRequest,
  tokenExpiry,
  tokenUsable,
  wasSaved,
  withClaim,
} from "@/utils/coachOutbox";

const NOW = Date.parse("2026-10-20T10:00:00Z");

const answer: CoachTurnRequest = {
  sessionId: "s_01",
  text: "Australia",
  language: "en",
  idempotencyKey: "key-0123456789abcdef",
};
const failure = (code: string): CoachFailure => ({ code, status: 0 });

// A token whose payload says it lapses at `exp` (seconds); signature and header are not read.
function tokenWith(exp: number): string {
  const payload = btoa(JSON.stringify({ exp })).replace(/\+/g, "-").replace(/\//g, "_");
  return `header.${payload}.signature`;
}

function entry(overrides: Partial<ReturnType<typeof createEntry>> = {}) {
  return {
    ...createEntry({
      request: answer,
      uid: "worker-1",
      turnCount: 3,
      url: "https://api.example/api/v2/coach/sessions/s_01/messages",
      token: tokenWith(NOW / 1000 + 3_600),
      now: NOW,
    }),
    ...overrides,
  };
}

describe("shouldQueue", () => {
  it("keeps an answer that never got a reply", () => {
    expect(shouldQueue(answer, failure("network"), true)).toBe(true);
    expect(shouldQueue(answer, failure("network"), false)).toBe(true);
  });

  it("keeps an answer whose stream broke only while the device was offline", () => {
    expect(shouldQueue(answer, failure("stream_dropped"), false)).toBe(true);
    expect(shouldQueue(answer, failure("stream_timeout"), false)).toBe(true);
    expect(shouldQueue(answer, failure("stream_dropped"), true)).toBe(false);
  });

  it("never keeps a turn the server refused or could not finish", () => {
    for (const code of ["validation_failed", "session_not_active", "ai_busy", "rate_limited"]) {
      expect(shouldQueue(answer, failure(code), false)).toBe(false);
    }
  });

  it("never keeps a turn without text: that is the coach speaking, not an answer", () => {
    expect(shouldQueue({ ...answer, text: undefined }, failure("network"), false)).toBe(false);
  });
});

describe("tokenExpiry", () => {
  it("reads the moment a token lapses", () => {
    expect(tokenExpiry(tokenWith(1_800_000_000))).toBe(1_800_000_000_000);
  });

  it("answers null for no token, a token with no expiry, or nonsense", () => {
    expect(tokenExpiry(null)).toBeNull();
    expect(tokenExpiry("not-a-token")).toBeNull();
    expect(tokenExpiry(`a.${btoa(JSON.stringify({ sub: "x" }))}.c`)).toBeNull();
  });
});

describe("an entry", () => {
  it("carries the same key and words, so sending it again repeats nothing", () => {
    expect(toRequest(entry())).toEqual(answer);
    expect(entry().id).toBe("s_01");
    expect(entry().claim).toBeNull();
    expect(entry().rejected).toBeNull();
  });

  it("is dropped after an interview could have expired", () => {
    expect(isExpired(entry(), NOW + OUTBOX_MAX_AGE_MS)).toBe(false);
    expect(isExpired(entry(), NOW + OUTBOX_MAX_AGE_MS + 1)).toBe(true);
  });

  it("is known to be saved once the server counts more answers than when it was queued", () => {
    expect(wasSaved(entry({ turnCount: 3 }), 3)).toBe(false);
    expect(wasSaved(entry({ turnCount: 3 }), 4)).toBe(true);
  });
});

describe("claiming", () => {
  it("is free when nobody holds it", () => {
    expect(isClaimable(entry(), NOW)).toBe(true);
  });

  it("is not free while a sender holds it, whichever sender", () => {
    const held = withClaim(entry(), "sw", NOW);
    expect(isClaimable(held, NOW + 1)).toBe(false);
    expect(isClaimable(withClaim(entry(), "page", NOW), NOW + CLAIM_LEASE_MS - 1)).toBe(false);
  });

  it("is free again once the lease ran out: a sender that long gone has died", () => {
    expect(isClaimable(withClaim(entry(), "sw", NOW), NOW + CLAIM_LEASE_MS)).toBe(true);
  });
});

describe("tokenUsable", () => {
  it("accepts a token with more than the margin left", () => {
    expect(tokenUsable(entry(), NOW)).toBe(true);
  });

  it("refuses a token about to lapse, one that has lapsed, and no token", () => {
    const soon = entry({ tokenExpiresAt: NOW + TOKEN_MARGIN_MS - 1 });
    expect(tokenUsable(soon, NOW)).toBe(false);
    expect(tokenUsable(entry({ tokenExpiresAt: NOW - 1 }), NOW)).toBe(false);
    expect(tokenUsable(entry({ token: null, tokenExpiresAt: null }), NOW)).toBe(false);
  });
});

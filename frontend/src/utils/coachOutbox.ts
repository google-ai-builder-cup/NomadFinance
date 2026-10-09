import type { CoachFailure, CoachTurnRequest } from "@/types/coach";
import type { LanguageCode } from "@/types/enums";

// The rules of the Coach's offline queue (NF-FC-019). Nothing here touches the network or the
// disk, so every rule can be tested alone.
//
// One answer waits at a time: the coach's next question depends on the answer, and the server
// replays only the latest turn for a key (docs/api/v2-coach.md), so an older key must never be
// sent again once another turn has been saved. The panel is locked while an answer waits.

/** An answer waiting longer than a session can live is dropped (14 days idle, then abandoned). */
export const OUTBOX_MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000;
/** How long a sender may hold an answer before another may take it over: the server treats a
 * turn running for more than 90 seconds as failed, so a sender that long gone has died. */
export const CLAIM_LEASE_MS = 90_000;
/** A token with less than this left is not worth sending: it could lapse on the way. */
export const TOKEN_MARGIN_MS = 60_000;

export type Claimant = "page" | "sw";

export interface OutboxEntry {
  /** The interview's id: a worker has one active interview and one waiting answer at a time. */
  id: string;
  uid: string;
  text: string;
  language: LanguageCode;
  idempotencyKey: string;
  /** The interview's `turn_count` when the answer was queued: more than this later means the
   * server did save it (it counts completed answers). */
  turnCount: number;
  /** Where to send it, complete: the service worker has no build settings to read. */
  url: string;
  /** The ID token to send it with, for the service worker; null when none could be had. */
  token: string | null;
  tokenExpiresAt: number | null;
  queuedAt: number;
  /** Who is sending it now. Taken and released in one step, so two senders never both send. */
  claim: { by: Claimant; at: number } | null;
  /** The server refused it for good (the interview ended, the text was refused): the code. The
   * screen shows it as an answer that was not sent. */
  rejected: string | null;
}

/**
 * Whether a turn that failed is kept to be sent when the connection returns: only an answer
 * (a turn without text is the coach speaking, not the worker), and only when the request never
 * got a reply, or the stream broke while the device was offline.
 */
export function shouldQueue(request: CoachTurnRequest, failure: CoachFailure, online: boolean) {
  if (request.text === undefined) {
    return false;
  }
  if (failure.code === "network") {
    return true;
  }
  return !online && (failure.code === "stream_dropped" || failure.code === "stream_timeout");
}

/** When an ID token stops working (the `exp` of its payload), or null if it cannot be read. */
export function tokenExpiry(token: string | null): number | null {
  if (token === null) {
    return null;
  }
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const { exp } = JSON.parse(atob(payload)) as { exp?: unknown };
    return typeof exp === "number" ? exp * 1000 : null;
  } catch {
    return null;
  }
}

export function createEntry(input: {
  request: CoachTurnRequest;
  uid: string;
  turnCount: number;
  url: string;
  token: string | null;
  now: number;
}): OutboxEntry {
  const { request, token } = input;
  return {
    id: request.sessionId,
    uid: input.uid,
    text: request.text ?? "",
    language: request.language,
    idempotencyKey: request.idempotencyKey,
    turnCount: input.turnCount,
    url: input.url,
    token,
    tokenExpiresAt: tokenExpiry(token),
    queuedAt: input.now,
    claim: null,
    rejected: null,
  };
}

/** The turn to send again: the same key and the same words, so the server repeats nothing. */
export function toRequest(entry: OutboxEntry): CoachTurnRequest {
  return {
    sessionId: entry.id,
    text: entry.text,
    language: entry.language,
    idempotencyKey: entry.idempotencyKey,
  };
}

export const isExpired = (entry: OutboxEntry, now: number): boolean =>
  now - entry.queuedAt > OUTBOX_MAX_AGE_MS;

/** The server saved this answer already (its transcript has it): sending it again is pointless. */
export const wasSaved = (entry: OutboxEntry, serverTurnCount: number): boolean =>
  serverTurnCount > entry.turnCount;

/** Free to take: nobody holds it, or whoever did has not finished within the lease. */
export const isClaimable = (entry: OutboxEntry, now: number): boolean =>
  entry.claim === null || now - entry.claim.at >= CLAIM_LEASE_MS;

export const withClaim = (entry: OutboxEntry, by: Claimant, now: number): OutboxEntry => ({
  ...entry,
  claim: { by, at: now },
});

/** Whether the service worker may send it: a token that still has time on it. */
export const tokenUsable = (entry: OutboxEntry, now: number): boolean =>
  entry.token !== null &&
  entry.tokenExpiresAt !== null &&
  entry.tokenExpiresAt - now >= TOKEN_MARGIN_MS;

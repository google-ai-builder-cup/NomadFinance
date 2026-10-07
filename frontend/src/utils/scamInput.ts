import type { ScamCheckInput } from "@/types/scam";

/** The backend refuses a longer message instead of cutting it (the payment request is often last). */
export const MAX_MESSAGE_CHARS = 4000;
/** Backend limit for a screenshot (`413 payload_too_large` above it). */
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
export const IMAGE_TYPES: Record<string, string[]> = {
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/webp": [".webp"],
};

export type MessageProblem = "empty" | "tooLong";

export type MessageCheck = { ok: true; text: string } | { ok: false; problem: MessageProblem };

/** Counted like the backend counts: after trimming, in characters not UTF-16 units. */
export function checkMessage(raw: string): MessageCheck {
  const text = raw.trim();
  if (text === "") {
    return { ok: false, problem: "empty" };
  }
  return [...text].length > MAX_MESSAGE_CHARS
    ? { ok: false, problem: "tooLong" }
    : { ok: true, text };
}

export function countChars(raw: string): number {
  return [...raw.trim()].length;
}

/** Whether an input is worth sending; the one gate every way in goes through. */
export function isSubmittable(input: ScamCheckInput): boolean {
  return input.kind === "screenshot" ? input.file.size > 0 : checkMessage(input.text).ok;
}

/**
 * The message a share arrived with. Apps put it in `text`, some in `title`, and a link they
 * share alone in `url` (or at the end of `text`). Parts that repeat another part are dropped.
 */
export function messageFromShare(params: URLSearchParams): string {
  const parts: string[] = [];
  for (const key of ["title", "text", "url"]) {
    const value = params.get(key)?.trim() ?? "";
    if (value !== "" && !parts.some((part) => part.includes(value))) {
      parts.push(value);
    }
  }
  return parts.join("\n");
}

const SHARE_KEY = "nomadfinance.sharedMessage";
// A shared phone: a message nobody opened must not greet the next person who opens the tab.
const SHARE_TTL_MS = 10 * 60 * 1000;

/**
 * Keeps a shared message for this tab, so it survives the sign-in a signed-out worker has to go
 * through first. Called before the router redirects, at start-up.
 */
export function stashSharedMessage(search: string, now = Date.now()): void {
  const message = messageFromShare(new URLSearchParams(search));
  if (message === "") {
    return;
  }
  try {
    sessionStorage.setItem(SHARE_KEY, JSON.stringify({ message, at: now }));
  } catch {
    // Private mode: the share still works while signed in, through the address.
  }
}

/** The kept message, if it is still fresh. Reading does not remove it: see `clearSharedMessage`. */
export function peekSharedMessage(now = Date.now()): string {
  try {
    const raw = sessionStorage.getItem(SHARE_KEY);
    if (raw === null) {
      return "";
    }
    const kept = JSON.parse(raw) as { message?: unknown; at?: unknown };
    const fresh = typeof kept.at === "number" && now - kept.at <= SHARE_TTL_MS;
    return fresh && typeof kept.message === "string" ? kept.message : "";
  } catch {
    return "";
  }
}

/** Removed once the check screen has the message, so it is never offered twice. */
export function clearSharedMessage(): void {
  try {
    sessionStorage.removeItem(SHARE_KEY);
  } catch {
    // Nothing stored.
  }
}

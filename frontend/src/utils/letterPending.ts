import type { LetterPendingReason } from "@/types/contract";

/**
 * What to tell the worker about a complaint letter that could not be written yet. Without a
 * reason (an older backend) the general "try again in a few minutes" is kept.
 */
export function letterPendingKey(reason: LetterPendingReason | null | undefined): string {
  return reason
    ? `contract.complaint.missing.reason.${reason}`
    : "contract.complaint.missing.stillPending";
}

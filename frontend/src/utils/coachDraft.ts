import { DRAFT_KEY_PREFIX } from "@/utils/coachStorageKeys";

// What the worker typed on the Coach screen and did not send (NF-FC-019), kept in this browser so
// a reload, a closed tab or a phone that restarted the page does not lose it. One draft per
// person, for one question of one interview: a new question starts without one.
//
// It is text the worker typed, so it stays on the phone, under the person's id, and is wiped on
// sign-out (lib/coachLocalData.ts). Nothing is sent to the server until the answer is.

export type DraftFields = Record<string, string>;

interface DraftRecord {
  sessionId: string;
  question: string;
  /** Field name to text. A field that is empty is not kept. */
  fields: DraftFields;
  savedAt: number;
}

/** A draft not touched for this long is not offered again: the interview itself is abandoned
 * after 14 days without an answer. */
const DRAFT_MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000;
/** An answer is at most 1,000 characters; a little more is kept so a long paste can still be
 * shortened by the worker, but a pasted book never fills the phone's storage. */
const MAX_FIELD_CHARS = 4_000;

const keyFor = (uid: string) => `${DRAFT_KEY_PREFIX}${uid}`;

function readRecord(uid: string): DraftRecord | null {
  try {
    const raw = localStorage.getItem(keyFor(uid));
    if (raw === null) {
      return null;
    }
    const record = JSON.parse(raw) as Partial<DraftRecord>;
    if (
      typeof record.sessionId !== "string" ||
      typeof record.question !== "string" ||
      typeof record.savedAt !== "number" ||
      typeof record.fields !== "object" ||
      record.fields === null
    ) {
      return null;
    }
    return record as DraftRecord;
  } catch {
    return null;
  }
}

/** The fields kept for this question of this interview, or none. */
export function readDraft(
  uid: string,
  sessionId: string,
  question: string,
  now = Date.now()
): DraftFields {
  const record = readRecord(uid);
  if (
    record === null ||
    record.sessionId !== sessionId ||
    record.question !== question ||
    now - record.savedAt > DRAFT_MAX_AGE_MS
  ) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(record.fields).filter(([, value]) => typeof value === "string")
  );
}

/** Keep these fields (merged into what is kept for this question). An empty text removes its
 * field, and a draft with no field left is removed altogether. */
export function writeDraft(
  uid: string,
  sessionId: string,
  question: string,
  patch: DraftFields,
  now = Date.now()
): void {
  const record = readRecord(uid);
  const fields: DraftFields =
    record !== null && record.sessionId === sessionId && record.question === question
      ? { ...record.fields }
      : {};
  for (const [name, value] of Object.entries(patch)) {
    if (value === "") {
      delete fields[name];
    } else {
      fields[name] = value.slice(0, MAX_FIELD_CHARS);
    }
  }
  try {
    if (Object.keys(fields).length === 0) {
      localStorage.removeItem(keyFor(uid));
    } else {
      const next: DraftRecord = { sessionId, question, fields, savedAt: now };
      localStorage.setItem(keyFor(uid), JSON.stringify(next));
    }
  } catch {
    // Storage is full or blocked: the worker keeps typing, only the safety net is missing.
  }
}

export function clearDraft(uid: string): void {
  try {
    localStorage.removeItem(keyFor(uid));
  } catch {
    // Nothing stored, or storage is blocked.
  }
}

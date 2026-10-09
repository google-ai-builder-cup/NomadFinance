import { CHECKLIST_KEY_PREFIX } from "@/utils/coachStorageKeys";

// The ticks of a plan's checklist are kept on this phone, under the worker's id and the plan's id
// (`docs/api/v2-coach.md`: "the ticks are kept on the phone, not here"). Only ids are stored, never
// the text, and signing out wipes them with the rest of what the Coach keeps here.

const keyFor = (uid: string, planId: string) => `${CHECKLIST_KEY_PREFIX}${uid}.${planId}`;

export function readTicks(uid: string, planId: string): ReadonlySet<string> {
  try {
    const raw = localStorage.getItem(keyFor(uid, planId));
    const parsed: unknown = raw === null ? [] : JSON.parse(raw);
    return new Set(
      Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === "string") : []
    );
  } catch {
    return new Set();
  }
}

export function writeTicks(uid: string, planId: string, ticks: ReadonlySet<string>): void {
  try {
    if (ticks.size === 0) {
      localStorage.removeItem(keyFor(uid, planId));
    } else {
      localStorage.setItem(keyFor(uid, planId), JSON.stringify([...ticks]));
    }
  } catch {
    // Storage is full or blocked: the tick still shows until the page is left.
  }
}

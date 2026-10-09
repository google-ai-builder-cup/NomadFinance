import { DRAFT_KEY_PREFIX, OUTBOX_DB_NAME } from "@/utils/coachStorageKeys";

/**
 * Wipe what the Coach keeps on this phone: the drafts and any answer still waiting for a
 * connection (with the token it carries). Called on sign-out, since a phone is often shared and
 * the next person must not find the last one's words, and after an account is deleted. Small and
 * standing alone so the main bundle does not pull in the Coach to do it.
 */
export function clearCoachLocalData(): void {
  try {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(DRAFT_KEY_PREFIX)) {
        localStorage.removeItem(key);
      }
    }
  } catch {
    // Storage is blocked: there is nothing of ours in it.
  }
  try {
    // The page's open connection closes itself when asked (`versionchange`) and the service
    // worker's after every use, so the deletion does not wait on them.
    indexedDB.deleteDatabase(OUTBOX_DB_NAME);
  } catch {
    // No IndexedDB here.
  }
}

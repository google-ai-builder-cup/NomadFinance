// Kept free of imports: the push code that uses these is in the main bundle, and anything this
// file pulled in would be downloaded by every worker, also those a module is switched off for.

/**
 * A path inside this app, or null. A push carries its link as plain data, so it is checked before
 * it is followed: one leading slash only, because `//host` and `/\host` are another site's address
 * to a browser, and no control character.
 */
export function safeAppPath(link: unknown): string | null {
  if (typeof link !== "string" || link.length === 0 || link.length > 300) {
    return null;
  }
  if (!link.startsWith("/") || link.startsWith("//") || link.startsWith("/\\")) {
    return null;
  }
  // eslint-disable-next-line no-control-regex -- a control character has no place in a link
  return /[\u0000-\u001f\u007f]/.test(link) ? null : link;
}

/** The link of a Coach check-in reminder: `/coach/checkin/{planId}?m=30` (backend `checkin_job.py`). */
export function isCoachCheckinPath(link: string): boolean {
  return /^\/coach\/checkin\/[^/?#]+/.test(link);
}

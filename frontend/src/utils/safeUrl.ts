/**
 * A web address that is safe to put in a link, or null.
 *
 * Complaint channels and survey sources come from the server. Only `http:` and `https:` are
 * links worth following; anything else, `javascript:` above all, would run inside the app's
 * own page if it were ever put in an `href` (NF-P4-004).
 */
export function safeWebUrl(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  try {
    const url = new URL(value.trim());
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

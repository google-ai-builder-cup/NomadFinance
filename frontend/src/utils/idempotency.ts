/** A key for one request that must not run twice: 16 to 64 characters of A-Za-z0-9_- (v2-conventions). */
export function newIdempotencyKey(): string {
  if (typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // `randomUUID` exists only on secure pages (https and localhost); a plain-http preview lacks it.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

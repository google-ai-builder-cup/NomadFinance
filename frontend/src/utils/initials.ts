/** Two characters to stand for a person on an avatar: the start of their name or email, or the
 * leading digits of a phone number. "?" when there is nothing to show. */
export function initialsOf(identity: string): string {
  const letters = identity.replace(/[^\p{L}\p{N}]/gu, "");
  return (letters.slice(0, 2) || "?").toUpperCase();
}

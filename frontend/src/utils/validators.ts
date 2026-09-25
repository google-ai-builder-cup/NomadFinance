/**
 * Build an E.164 number ("+6581234567") from a dial code and a locally typed number.
 * Returns null when the digits can't be a valid mobile number.
 */
export function toE164(dialCode: string, localNumber: string): string | null {
  // People type numbers the way they see them at home: spaces, dashes, and a leading
  // trunk "0" (e.g. MY 012-345 6789, PH 0917 123 4567) that must be dropped.
  const digits = localNumber.replace(/[\s\-().]/g, "").replace(/^0+/, "");
  if (!/^\d{6,12}$/.test(digits)) {
    return null;
  }
  return `${dialCode}${digits}`;
}

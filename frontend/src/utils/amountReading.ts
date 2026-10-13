import { toAsciiDigits } from "@/utils/digits";

/**
 * The number a typed amount is read as, when it could be read two ways: one dot with exactly three
 * digits after it (`1.500`, `645.505`). The forms read that dot as a thousands separator, the way
 * Indonesian and European keyboards write it, so `1.5` typed as `1.500` becomes 1,500. Null for any
 * other text, which has one reading.
 */
export function dottedThousands(text: string): number | null {
  const raw = toAsciiDigits(text).replace(/[\s']/g, "");
  if (!/^\d{1,3}\.\d{3}$/.test(raw)) {
    return null;
  }
  // `0.500` is half, not five hundred: a first group of zero is not thousands.
  return raw.startsWith("0") ? null : Number(raw.replace(".", ""));
}

import { toAsciiDigits } from "@/utils/digits";

export type TypedAmount = { ok: true; normalized: string } | { ok: false; problem: "invalid" };

// A thousands mark sits only between groups of three digits and the first group has no leading
// zero (`0,500` is half). The comma also takes the Indian grouping, `1,50,000`.
const GROUPED = {
  ",": /^[1-9]\d{0,2}(?:,\d{3})+$|^[1-9]\d?(?:,\d{2})+,\d{3}$/,
  ".": /^[1-9]\d{0,2}(?:\.\d{3})+$/,
} as const;

const INVALID: TypedAmount = { ok: false, problem: "invalid" };

// \s also covers the no-break space some keyboards put in grouped numbers; the digits of a
// Hindi, Nepali or Bengali keyboard are read as 0 to 9.
const compact = (text: string): string => toAsciiDigits(text).replace(/[\s']/g, "");

const withoutMarks = (text: string): string => text.replace(/[.,]/g, "");

// Zeros at the end of a fraction add nothing, so `5.400` is 5.4 and `645.50` is 645.5.
function withFraction(whole: string, fraction: string): TypedAmount {
  const digits = fraction.replace(/0+$/, "");
  return { ok: true, normalized: digits === "" ? whole : `${whole}.${digits}` };
}

/**
 * Turn what a worker typed into a plain number string ("6450.5"), or say it is not one. The marks
 * are read by where they sit, not by which keyboard the worker has:
 * - both marks ("1,530.50", "1.530,50"): the last one is the decimal point, the other groups thousands;
 * - one mark repeated ("1,530,000", "1.530.000"): thousands;
 * - one comma before exactly three digits ("5,400"): thousands, before one or two ("5,10"): decimal;
 * - one dot ("5.400", "645.5"): the decimal point, whatever follows it.
 *
 * Decimals are the one thing the text cannot settle: how many a currency takes is up to the caller.
 * With `wholeUnits` (a currency with no minor unit, such as the yen) a dot or comma before exactly
 * three digits is thousands, since there is no fraction it could be.
 */
export function readTypedAmount(text: string, wholeUnits: boolean): TypedAmount {
  const raw = compact(text);
  if (!/^\d+(?:[.,]\d+)*$/.test(raw)) {
    return INVALID;
  }
  const lastMark = Math.max(raw.lastIndexOf("."), raw.lastIndexOf(","));
  if (lastMark < 0) {
    return { ok: true, normalized: raw };
  }
  const mark = raw[lastMark] as keyof typeof GROUPED;
  const other = mark === "." ? "," : ".";
  const whole = raw.slice(0, lastMark);
  const fraction = raw.slice(lastMark + 1);
  const repeated = raw.split(mark).length > 2;

  if (GROUPED[mark].test(raw) && (mark === "," || repeated || wholeUnits)) {
    return { ok: true, normalized: withoutMarks(raw) };
  }
  if (raw.includes(other)) {
    return GROUPED[other].test(whole) ? withFraction(withoutMarks(whole), fraction) : INVALID;
  }
  if (repeated || (mark === "," && fraction.length > 2 && whole !== "0")) {
    return INVALID;
  }
  return withFraction(whole, fraction);
}

/**
 * The number a typed amount is read as, when another keyboard would read the same text another way:
 * one mark before exactly three digits (`5.400`, `5,400`). Here a dot is a decimal point (5.4) and
 * a comma is thousands (5,400), so a worker who writes it the other way round would send a
 * different amount than they meant, and the forms say how it was read. Null for any other text,
 * which has one reading, and for a currency with no minor unit, where the mark can only be thousands.
 */
export function ambiguousReading(text: string, decimals: number): number | null {
  const raw = compact(text);
  if (decimals === 0 || !/^[1-9]\d{0,2}[.,]\d{3}$/.test(raw)) {
    return null;
  }
  const typed = readTypedAmount(raw, false);
  return typed.ok ? Number(typed.normalized) : null;
}

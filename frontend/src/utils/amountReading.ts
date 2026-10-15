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

export type TypedAmount =
  { ok: true; normalized: string } | { ok: false; problem: "invalid" | "decimalComma" };

/**
 * Turn what a worker typed into a plain number string ("6450.5"), or say why it is not one.
 *
 * A comma is only ever a thousands separator ("6,450") and a dot is the decimal point ("645.50"),
 * except a dot before exactly three digits ("6.450"), which is read as thousands. A comma before one
 * or two digits ("5,10") is refused rather than guessed: it reads as 5.10 on one keyboard and as
 * 510 on another, and a wrong guess sends a different amount. For a currency without a minor unit
 * every separator is a thousands separator.
 */
export function readTypedAmount(text: string, wholeUnits: boolean): TypedAmount {
  // \s also covers the no-break space some keyboards put in grouped numbers; the digits of a
  // Hindi, Nepali or Bengali keyboard are read as 0 to 9.
  const raw = toAsciiDigits(text).replace(/[\s']/g, "");
  if (wholeUnits && /^\d+([.,]\d{3})*$/.test(raw)) {
    return { ok: true, normalized: raw.replace(/[.,]/g, "") };
  }
  if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(raw)) {
    return { ok: true, normalized: raw.replace(/,/g, "") };
  }
  if (/^[1-9]\d{0,2}(\.\d{3})+$/.test(raw)) {
    return { ok: true, normalized: raw.replace(/\./g, "") };
  }
  if (/^\d+(\.\d+)?$/.test(raw)) {
    return { ok: true, normalized: raw };
  }
  // The yen has no decimals to point a dot at, so its "invalid" wording fits better.
  const commaDecimal = !wholeUnits && /^\d[\d.,]*,\d{1,2}$/.test(raw);
  return { ok: false, problem: commaDecimal ? "decimalComma" : "invalid" };
}

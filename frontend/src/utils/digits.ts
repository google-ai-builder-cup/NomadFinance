// The first digit (zero) of each block of decimal digits that a keyboard of the app's languages
// types: Hindi and Nepali (Devanagari), Bengali, and the Arabic-Indic and Persian sets a phone
// offers beside them, plus full-width digits from an East Asian keyboard. Tagalog and Indonesian
// type the ASCII digits already.
const BLOCK_ZEROS = [
  0x0660, // Arabic-Indic
  0x06f0, // Extended Arabic-Indic (Persian, Urdu)
  0x0966, // Devanagari: Hindi, Nepali
  0x09e6, // Bengali
  0x0a66, // Gurmukhi
  0x0ae6, // Gujarati
  0x0b66, // Odia
  0x0be6, // Tamil
  0x0c66, // Telugu
  0x0ce6, // Kannada
  0x0d66, // Malayalam
  0xff10, // Full-width
] as const;

/**
 * Digits of any of those scripts written as 0 to 9, so a number typed on a Hindi or Bengali
 * keyboard reads the same as one typed on an English one. The Arabic decimal and thousands marks
 * become "." and ",". Everything else is left alone: a letter is still a letter.
 */
export function toAsciiDigits(text: string): string {
  return text
    .replace(/\p{Nd}/gu, (character) => {
      const code = character.codePointAt(0) ?? 0;
      const zero = BLOCK_ZEROS.find((start) => code >= start && code <= start + 9);
      return zero === undefined ? character : String(code - zero);
    })
    .replace(/٫/g, ".")
    .replace(/٬/g, ",");
}

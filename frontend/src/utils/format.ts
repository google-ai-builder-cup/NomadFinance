/**
 * Country name in the given UI language, from the browser's own locale data, so country
 * lists need no translation keys. Falls back to the ISO code if the browser can't name it.
 */
export function countryName(code: string, language: string): string {
  try {
    // "short" gives "Hong Kong" instead of "Hong Kong SAR China".
    return new Intl.DisplayNames([language], { type: "region", style: "short" }).of(code) ?? code;
  } catch {
    return code;
  }
}

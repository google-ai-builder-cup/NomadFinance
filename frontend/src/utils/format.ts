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

/** Currency name in the given UI language ("Philippine peso"), from the browser's locale data. */
export function currencyName(code: string, language: string): string {
  try {
    return new Intl.DisplayNames([language], { type: "currency" }).of(code) ?? code;
  } catch {
    return code;
  }
}

/** Language name in the given UI language, from the browser's own locale data (NF-P2-013). */
export function languageName(code: string, language: string): string {
  try {
    return new Intl.DisplayNames([language], { type: "language" }).of(code) ?? code;
  } catch {
    return code;
  }
}

/**
 * An amount with its currency in the given UI language ("SGD 645", "₱44,615.20", "¥42,000"),
 * with `maximumFractionDigits` decimals unless the amount is whole. Falls back to "645 SGD" if the browser can't
 * format the currency.
 */
export function formatMoney(
  amount: number,
  currency: string,
  language: string,
  maximumFractionDigits = 2
): string {
  try {
    return new Intl.NumberFormat(language, {
      style: "currency",
      currency,
      maximumFractionDigits,
      // Whole amounts stay short ("A$500"); others show every decimal ("₱44,615.20").
      minimumFractionDigits: Number.isInteger(amount) ? 0 : maximumFractionDigits,
    }).format(amount);
  } catch {
    return `${amount} ${currency}`;
  }
}

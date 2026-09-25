export interface SupportedLanguage {
  code: string;
  /** Name in the language's own script, for the selector — not translated. */
  nativeName: string;
}

// Order drives the language selector's option order.
export const SUPPORTED_LANGUAGES: SupportedLanguage[] = [
  { code: "en", nativeName: "English" },
  { code: "hi", nativeName: "हिन्दी" },
  { code: "tl", nativeName: "Tagalog" },
  { code: "id", nativeName: "Bahasa Indonesia" },
  { code: "ne", nativeName: "नेपाली" },
  { code: "bn", nativeName: "বাংলা" },
];

export const DEFAULT_LANGUAGE = "en";

// The language chosen on signed-out pages (sign-in), remembered on this device only.
// Signed-in users follow users/{uid}.preferred_language instead (LanguageSync), so this
// never holds a profile's language. Renamed from "nomadfinance.language", which used to
// cache every change, including the signed-in user's.
export const DEVICE_LANGUAGE_KEY = "nomadfinance.deviceLanguage";

export function getDeviceLanguage(): string {
  try {
    const stored = localStorage.getItem(DEVICE_LANGUAGE_KEY);
    return SUPPORTED_LANGUAGES.some((language) => language.code === stored) && stored
      ? stored
      : DEFAULT_LANGUAGE;
  } catch {
    // Storage can be blocked (private mode, strict privacy settings).
    return DEFAULT_LANGUAGE;
  }
}

export function setDeviceLanguage(code: string): void {
  try {
    localStorage.setItem(DEVICE_LANGUAGE_KEY, code);
  } catch {
    // Not remembered on this device; the choice still applies until reload.
  }
}

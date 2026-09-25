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

// A signed-in user's quick switch from the header, for this browser tab only: kept across
// reloads, cleared on sign-out (LanguageSync). It never changes preferred_language, which
// also drives reports, notifications and SMS and is set only in onboarding and the profile page.
const SESSION_LANGUAGE_KEY = "nomadfinance.sessionLanguage";

export function getSessionLanguage(): string | null {
  try {
    const stored = sessionStorage.getItem(SESSION_LANGUAGE_KEY);
    return SUPPORTED_LANGUAGES.some((language) => language.code === stored) ? stored : null;
  } catch {
    return null;
  }
}

export function setSessionLanguage(code: string): void {
  try {
    sessionStorage.setItem(SESSION_LANGUAGE_KEY, code);
  } catch {
    // Not kept across reloads; the switch still applies until then.
  }
}

export function clearSessionLanguage(): void {
  try {
    sessionStorage.removeItem(SESSION_LANGUAGE_KEY);
  } catch {
    // Nothing stored.
  }
}

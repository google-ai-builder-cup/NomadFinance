import i18next from "i18next";
import { initReactI18next } from "react-i18next";

import en from "@/i18n/en.json";
import { DEFAULT_LANGUAGE } from "@/lib/languages";

// Only English ships with the first download: the other five files are 40 to 70 KB each
// and a worker needs one of them at most. Each is its own chunk, fetched when that language
// is first chosen (and precached by the service worker, so it also works offline).
const LOADERS: Readonly<Record<string, () => Promise<{ default: Record<string, unknown> }>>> = {
  hi: () => import("@/i18n/hi.json"),
  tl: () => import("@/i18n/tl.json"),
  id: () => import("@/i18n/id.json"),
  ne: () => import("@/i18n/ne.json"),
  bn: () => import("@/i18n/bn.json"),
};

void i18next.use(initReactI18next).init({
  resources: { en: { translation: en } },
  // Always start in English; LanguageSync switches to the signed-in user's language.
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  interpolation: { escapeValue: false },
});

/**
 * Switch the UI language, fetching its strings first. If the fetch fails (no signal and the
 * file was never cached) the UI stays in its current language rather than showing keys.
 */
export async function setLanguage(code: string): Promise<void> {
  const load = LOADERS[code];
  if (load !== undefined && !i18next.hasResourceBundle(code, "translation")) {
    try {
      i18next.addResourceBundle(code, "translation", (await load()).default);
    } catch {
      return;
    }
  }
  await i18next.changeLanguage(code);
}

export default i18next;

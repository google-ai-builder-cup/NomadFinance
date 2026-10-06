import i18next from "i18next";
import { initReactI18next } from "react-i18next";

import en from "@/i18n/en.json";
import { DEFAULT_LANGUAGE } from "@/lib/languages";

// The shared strings (nav, auth, errors ...) live in the default "translation" namespace; each
// module owns one more namespace of its own (`coach`, `scam`), kept in src/i18n/<namespace>/.
// English is the source of truth for all of them: scripts/check-i18n.mjs fails CI when another
// language lacks a key.
export type LazyNamespace = "coach" | "scam";
type Namespace = "translation" | LazyNamespace;
type Loader = () => Promise<{ default: Record<string, unknown> }>;

// Only English "translation" ships with the first download: the other five files are 40 to 70 KB
// each and a worker needs one of them at most. Every other file is its own chunk, fetched when
// it is first needed (and precached by the service worker, so it also works offline).
const LOADERS: Readonly<Record<Namespace, Readonly<Record<string, Loader>>>> = {
  translation: {
    hi: () => import("@/i18n/hi.json"),
    tl: () => import("@/i18n/tl.json"),
    id: () => import("@/i18n/id.json"),
    ne: () => import("@/i18n/ne.json"),
    bn: () => import("@/i18n/bn.json"),
  },
  coach: {
    en: () => import("@/i18n/coach/en.json"),
    hi: () => import("@/i18n/coach/hi.json"),
    tl: () => import("@/i18n/coach/tl.json"),
    id: () => import("@/i18n/coach/id.json"),
    ne: () => import("@/i18n/coach/ne.json"),
    bn: () => import("@/i18n/coach/bn.json"),
  },
  scam: {
    en: () => import("@/i18n/scam/en.json"),
    hi: () => import("@/i18n/scam/hi.json"),
    tl: () => import("@/i18n/scam/tl.json"),
    id: () => import("@/i18n/scam/id.json"),
    ne: () => import("@/i18n/scam/ne.json"),
    bn: () => import("@/i18n/scam/bn.json"),
  },
};

// The module namespaces a page has asked for. A language switch fetches these and no others, so
// a worker who never opens the coach never downloads its strings, in any language.
const activeNamespaces = new Set<LazyNamespace>();

void i18next.use(initReactI18next).init({
  resources: { en: { translation: en } },
  // Always start in English; LanguageSync switches to the signed-in user's language.
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  // A module's t() still finds the shared strings (common.retry, errors.*) without a prefix.
  fallbackNS: "translation",
  interpolation: { escapeValue: false },
});

async function loadBundle(language: string, namespace: Namespace): Promise<void> {
  const load = LOADERS[namespace][language];
  if (load !== undefined && !i18next.hasResourceBundle(language, namespace)) {
    i18next.addResourceBundle(language, namespace, (await load()).default);
  }
}

/**
 * Fetch a module's strings for the current language, once. Call it where the module's code is
 * fetched (its lazy route), so the strings arrive with the page and the page shows its skeleton
 * until both are there. English is always fetched too, as the fallback for a missing key.
 *
 * Rejects only when the English strings cannot be fetched. Another language's file failing
 * (no signal, never cached) leaves that module in English instead of showing keys.
 */
export async function loadNamespace(namespace: LazyNamespace): Promise<void> {
  // Registered first, so a language switch that starts while this runs fetches it too.
  activeNamespaces.add(namespace);
  await loadBundle(DEFAULT_LANGUAGE, namespace);
  const language = i18next.resolvedLanguage ?? DEFAULT_LANGUAGE;
  await loadBundle(language, namespace).catch(() => undefined);
}

/**
 * Switch the UI language, fetching its strings first: the shared file, and the file of each
 * module namespace that is in use. If the shared file cannot be fetched the UI stays in its
 * current language rather than showing keys. A module file that cannot be fetched only leaves
 * that module in English.
 */
export async function setLanguage(code: string): Promise<void> {
  try {
    await loadBundle(code, "translation");
  } catch {
    return;
  }
  await Promise.allSettled([...activeNamespaces].map((namespace) => loadBundle(code, namespace)));
  await i18next.changeLanguage(code);
}

export default i18next;

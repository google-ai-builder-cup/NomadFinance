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

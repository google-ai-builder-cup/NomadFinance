import i18next from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import bn from "@/i18n/bn.json";
import en from "@/i18n/en.json";
import hi from "@/i18n/hi.json";
import id from "@/i18n/id.json";
import ne from "@/i18n/ne.json";
import tl from "@/i18n/tl.json";
import { DEFAULT_LANGUAGE } from "@/lib/languages";

void i18next
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      hi: { translation: hi },
      tl: { translation: tl },
      id: { translation: id },
      ne: { translation: ne },
      bn: { translation: bn },
    },
    fallbackLng: DEFAULT_LANGUAGE,
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "nomadfinance.language",
    },
  });

export default i18next;

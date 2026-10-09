import { useTranslation } from "react-i18next";

import { isLanguageCode, type LanguageCode } from "@/types/enums";

/** The language the app is shown in right now (the header's switcher, the profile, or the
 * browser), falling back to English. The Coach speaks it too. */
export function useUiLanguage(): LanguageCode {
  const { i18n } = useTranslation();
  return isLanguageCode(i18n.resolvedLanguage) ? i18n.resolvedLanguage : "en";
}

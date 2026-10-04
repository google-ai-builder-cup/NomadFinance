import { Languages } from "lucide-react";
import type { ChangeEvent } from "react";

import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";
import i18n, { setLanguage } from "@/lib/i18n";
import { setSessionLanguage, SUPPORTED_LANGUAGES } from "@/lib/languages";

export default function LanguageSelector() {
  const { t } = useI18n();
  const { user } = useAuth();

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const code = event.target.value;
    void setLanguage(code);
    // A quick switch only: preferred_language (reports, notifications, SMS) changes in
    // onboarding and on the profile page, never here. Signed out, nothing is stored, so the
    // sign-in page opens in English next time. See LanguageSync for how it applies.
    if (user !== null) {
      setSessionLanguage(code);
    }
  }

  return (
    <label className="relative flex items-center">
      <span className="sr-only">{t("layout.languageLabel")}</span>
      <Languages
        className="pointer-events-none absolute left-2 h-4 w-4 text-muted-foreground"
        aria-hidden="true"
      />
      {/* Icon-only below sm (NF-P2-023: the header has no room for every control's full text
          there); the native picker still lists every language's own name when opened. */}
      <select
        value={i18n.resolvedLanguage}
        onChange={handleChange}
        aria-label={t("layout.languageLabel")}
        className="h-9 w-9 cursor-pointer appearance-none overflow-hidden rounded-md border border-input bg-background py-2 pl-8 pr-3 text-sm text-transparent shadow-sm [@media(pointer:coarse)]:text-base hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring sm:w-auto sm:text-foreground sm:hover:text-accent-foreground"
      >
        {SUPPORTED_LANGUAGES.map((language) => (
          <option key={language.code} value={language.code}>
            {language.nativeName}
          </option>
        ))}
      </select>
    </label>
  );
}

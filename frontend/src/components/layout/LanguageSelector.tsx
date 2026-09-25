import { Languages } from "lucide-react";
import type { ChangeEvent } from "react";

import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { SUPPORTED_LANGUAGES } from "@/lib/languages";

export default function LanguageSelector() {
  const { t } = useI18n();

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    void i18n.changeLanguage(event.target.value);
  }

  return (
    <label className="relative flex items-center">
      <span className="sr-only">{t("layout.languageLabel")}</span>
      <Languages
        className="pointer-events-none absolute left-2 h-4 w-4 text-muted-foreground"
        aria-hidden="true"
      />
      <select
        value={i18n.resolvedLanguage}
        onChange={handleChange}
        aria-label={t("layout.languageLabel")}
        className="h-9 cursor-pointer appearance-none rounded-md border border-input bg-background py-2 pl-8 pr-3 text-sm shadow-sm hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
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

import { useI18n } from "@/hooks/useI18n";
import { SUPPORTED_LANGUAGES } from "@/lib/languages";
import type { LanguageCode } from "@/types/enums";

export interface ReportLanguageSwitcherProps {
  /** The language the report is shown in. */
  value: LanguageCode;
  onChange: (language: LanguageCode) => void;
  /** True while a language is loading, so a second choice cannot start a second translation. */
  disabled?: boolean;
}

/**
 * Chooses the language of the Contract Health Report (NF-P2-012). Only the report changes:
 * neither the app language nor the profile's `preferred_language` does (D-40).
 */
export default function ReportLanguageSwitcher({
  value,
  onChange,
  disabled = false,
}: ReportLanguageSwitcherProps) {
  const { t } = useI18n();

  return (
    <div className="space-y-1.5">
      <label htmlFor="contract-report-view-language" className="text-sm font-medium">
        {t("contract.report.language")}
      </label>
      <select
        id="contract-report-view-language"
        value={value}
        onChange={(event) => onChange(event.target.value as LanguageCode)}
        aria-describedby="contract-report-view-language-hint"
        disabled={disabled}
        className="h-11 w-full rounded-md border border-input bg-background px-3 text-base shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50 sm:w-64"
      >
        {SUPPORTED_LANGUAGES.map(({ code, nativeName }) => (
          <option key={code} value={code}>
            {nativeName}
          </option>
        ))}
      </select>
      <p id="contract-report-view-language-hint" className="text-xs text-muted-foreground">
        {t("contract.report.languageHint")}
      </p>
    </div>
  );
}

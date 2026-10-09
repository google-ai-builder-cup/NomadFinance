import { Languages } from "lucide-react";
import type { ChangeEvent } from "react";

import { useI18n } from "@/hooks/useI18n";
import { useUiLanguage } from "@/hooks/useUiLanguage";
import { setLanguage } from "@/lib/i18n";
import { setSessionLanguage, SUPPORTED_LANGUAGES } from "@/lib/languages";

/**
 * The coach's language, on the coach screen itself. It is the app's language: choosing one here
 * changes the whole app, and the interview carries on in it (`useCoachChat` sends the switch), with
 * the answers and the stage kept. It does what the header's selector does, so the two always agree;
 * this one is in front of the worker, with its words spelled out, where the header's is an icon.
 */
export default function LanguageSwitch() {
  const { t } = useI18n("coach");
  const language = useUiLanguage();

  function change(event: ChangeEvent<HTMLSelectElement>) {
    const code = event.target.value;
    void setLanguage(code);
    // The same quick switch as the header: for this tab only, never the saved preference. The
    // coach is only reachable signed in, so there is always a worker to remember it for.
    setSessionLanguage(code);
  }

  return (
    <label className="ml-auto flex shrink-0 items-center gap-1.5 text-sm font-medium">
      <Languages className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
      <span className="sr-only sm:not-sr-only sm:text-muted-foreground">{t("language.label")}</span>
      <select
        value={language}
        onChange={change}
        className="h-10 max-w-[9.5rem] cursor-pointer rounded-xl border border-input bg-card px-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring [@media(pointer:coarse)]:text-base"
      >
        {SUPPORTED_LANGUAGES.map(({ code, nativeName }) => (
          <option key={code} value={code}>
            {nativeName}
          </option>
        ))}
      </select>
    </label>
  );
}

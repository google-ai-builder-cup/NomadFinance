import { Moon, Sun } from "lucide-react";
import type { ChangeEvent } from "react";
import { useState } from "react";

import { useI18n } from "@/hooks/useI18n";
import { applyTheme, getStoredTheme, setStoredTheme, THEMES, type Theme } from "@/lib/theme";

export default function ThemeToggle() {
  const { t } = useI18n();
  const [theme, setTheme] = useState<Theme>(getStoredTheme);

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const next = event.target.value as Theme;
    setTheme(next);
    setStoredTheme(next);
    applyTheme(next);
  }

  return (
    <label className="relative flex items-center">
      <span className="sr-only">{t("layout.themeLabel")}</span>
      {theme === "dark" ? (
        <Moon
          className="pointer-events-none absolute left-3.5 h-4 w-4 text-muted-foreground sm:left-3"
          aria-hidden="true"
        />
      ) : (
        <Sun
          className="pointer-events-none absolute left-3.5 h-4 w-4 text-muted-foreground sm:left-3"
          aria-hidden="true"
        />
      )}
      {/* Icon-only below sm (the header has no room for four full controls there): a fixed
          width and transparent text keep the box compact without hiding the native picker,
          which still lists every option's real label when opened. */}
      <select
        value={theme}
        onChange={handleChange}
        aria-label={t("layout.themeLabel")}
        className="h-11 w-11 cursor-pointer appearance-none overflow-hidden rounded-xl border border-input bg-card py-2 pl-8 pr-3 text-sm font-medium text-transparent shadow-sm sm:h-10 [@media(pointer:coarse)]:text-base hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring sm:w-auto sm:text-foreground sm:hover:text-accent-foreground"
      >
        {THEMES.map((option) => (
          <option key={option} value={option}>
            {t(`layout.theme.${option}`)}
          </option>
        ))}
      </select>
    </label>
  );
}

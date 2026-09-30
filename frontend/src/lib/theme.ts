export type Theme = "light" | "dark" | "system";

export const THEMES: Theme[] = ["light", "dark", "system"];
export const DEFAULT_THEME: Theme = "system";

// A display preference, not personal data, so it is kept across sessions (unlike the
// header's language quick switch, which is deliberately per-tab: see lib/languages.ts).
const THEME_KEY = "nomadfinance.theme";

export function getStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    return (THEMES as string[]).includes(stored ?? "") ? (stored as Theme) : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

export function setStoredTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Not kept across reloads; the choice still applies until then.
  }
}

/** "system" resolved against the OS/browser preference, read fresh each time it is needed. */
export function resolveTheme(theme: Theme): "light" | "dark" {
  if (theme !== "system") {
    return theme;
  }
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

/** Adds or removes the `.dark` class `tailwind.config.ts`'s `darkMode: ["class"]` reads. */
export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", resolveTheme(theme) === "dark");
}

import { useEffect } from "react";

import { applyTheme, getStoredTheme } from "@/lib/theme";

/**
 * Keeps the `.dark` class current while the app is open. Mounted once, next to the router.
 *
 * The very first paint is handled by a small inline script in `index.html` (so there is no
 * flash of the wrong theme before React loads); `ThemeToggle` applies a chosen theme itself,
 * immediately, when the worker picks one. The only thing left for this to do is keep "system"
 * live: re-apply if the OS or browser's own light/dark setting changes while the app is open.
 */
export default function ThemeSync() {
  useEffect(() => {
    applyTheme(getStoredTheme());

    function onSystemChange() {
      if (getStoredTheme() === "system") {
        applyTheme("system");
      }
    }
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", onSystemChange);
    return () => media.removeEventListener("change", onSystemChange);
  }, []);

  return null;
}

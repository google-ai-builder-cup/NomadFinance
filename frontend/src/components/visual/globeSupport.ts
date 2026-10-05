interface NavigatorHints extends Navigator {
  deviceMemory?: number;
  connection?: { saveData?: boolean };
}

/** Whether this device should run the animated globe: motion allowed, no data saver, and enough
 * memory and cores. Everything else keeps the static poster, which has the same composition. */
export function canRunGlobe(): boolean {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return false;
  }
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
    return false;
  }
  const nav = navigator as NavigatorHints;
  if (nav.connection?.saveData) {
    return false;
  }
  if ((nav.deviceMemory ?? 8) < 4 || (nav.hardwareConcurrency ?? 8) < 4) {
    return false;
  }
  return document.createElement("canvas").getContext("2d") !== null;
}

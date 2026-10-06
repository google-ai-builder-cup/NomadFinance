import { useTranslation } from "react-i18next";

import type { LazyNamespace } from "@/lib/i18n";

/** `t` for the shared strings, or for a module's own namespace (shared keys still resolve). */
export function useI18n(namespace?: LazyNamespace): { t: ReturnType<typeof useTranslation>["t"] } {
  const { t } = useTranslation(namespace);
  return { t };
}

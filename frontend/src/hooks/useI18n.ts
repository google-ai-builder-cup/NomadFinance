import { translate } from "@/lib/i18n";

// Shaped like react-i18next's useTranslation() so NF-P1-011 can swap the internals.
export function useI18n(): { t: typeof translate } {
  return { t: translate };
}

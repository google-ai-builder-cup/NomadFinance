import { useTranslation } from "react-i18next";

export function useI18n(): { t: ReturnType<typeof useTranslation>["t"] } {
  const { t } = useTranslation();
  return { t };
}

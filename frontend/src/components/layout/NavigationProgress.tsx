import { useNavigation } from "react-router-dom";

import { useI18n } from "@/hooks/useI18n";

/**
 * A thin bar at the top while the next page's code downloads. Pages load on demand
 * (NF-P4-003), and on a slow connection the old page would otherwise just sit there after a
 * tap with no sign that anything is happening.
 */
export default function NavigationProgress() {
  const { t } = useI18n();
  const navigation = useNavigation();

  if (navigation.state === "idle") {
    return null;
  }
  return (
    <div
      role="progressbar"
      aria-label={t("common.loading")}
      className="fixed inset-x-0 top-0 z-50 h-1 animate-pulse bg-primary"
    />
  );
}

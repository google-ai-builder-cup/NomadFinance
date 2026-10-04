import LoadingSpinner from "@/components/common/LoadingSpinner";
import { useI18n } from "@/hooks/useI18n";

/** What the router shows while the first page's code downloads. */
export default function RouteLoading() {
  const { t } = useI18n();
  return <LoadingSpinner label={t("common.loading")} fullScreen />;
}

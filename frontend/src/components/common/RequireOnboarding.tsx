import { Navigate, Outlet } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useUserProfile } from "@/hooks/useUser";
import { isOnboarded } from "@/services/userService";

/**
 * Layout route inside ProtectedRoute: signed-in users who haven't finished onboarding
 * are sent to /onboarding before they can reach any app page.
 */
export default function RequireOnboarding() {
  const { t } = useI18n();
  const profile = useUserProfile();

  if (profile.isPending) {
    return <LoadingSpinner label={t("common.loading")} fullScreen />;
  }
  if (profile.isError) {
    return (
      <div
        role="alert"
        className="mx-auto flex min-h-screen max-w-sm flex-col items-center justify-center gap-4 px-4 text-center"
      >
        <p className="text-sm text-muted-foreground">{t("onboarding.loadError")}</p>
        <Button onClick={() => void profile.refetch()}>{t("common.retry")}</Button>
      </div>
    );
  }
  if (!isOnboarded(profile.data)) {
    return <Navigate to="/onboarding" replace />;
  }
  return <Outlet />;
}

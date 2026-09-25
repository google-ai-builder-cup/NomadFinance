import { Navigate, Outlet, useLocation } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";

/**
 * Layout route that only renders its children for a signed-in user.
 * Signed-out users go to /sign-in and come back to the page they asked for.
 */
export default function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();
  const { t } = useI18n();

  // Without this wait, a returning user would flash through /sign-in on every reload.
  if (loading) {
    return <LoadingSpinner label={t("common.loading")} fullScreen />;
  }
  if (!user) {
    return <Navigate to="/sign-in" replace state={{ from: location }} />;
  }
  return <Outlet />;
}

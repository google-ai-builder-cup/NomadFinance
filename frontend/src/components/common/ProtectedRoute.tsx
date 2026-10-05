import { Navigate, Outlet } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";

/**
 * Layout route that only renders its children for a signed-in user.
 * Signed-out users go to the landing page, from where they sign in. This covers signing out
 * (the page they were on is guarded, so this is where they end up), an expired session and a
 * link to a page that needs an account.
 */
export default function ProtectedRoute() {
  const { user, loading } = useAuth();
  const { t } = useI18n();

  // Without this wait, a returning user would flash through /sign-in on every reload.
  if (loading) {
    return <LoadingSpinner label={t("common.loading")} fullScreen />;
  }
  if (!user) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

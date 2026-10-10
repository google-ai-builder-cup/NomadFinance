import { useEffect } from "react";
import { useLocation, useNavigate, useRouteError } from "react-router-dom";

import ErrorFallback from "@/components/common/ErrorFallback";
import { trackCrash } from "@/lib/analytics";
import { isChunkLoadError } from "@/utils/chunkError";

export interface RouteErrorProps {
  /** True for the top-level route, where no app shell is left around the error. */
  fullScreen?: boolean;
}

/**
 * `errorElement` for the router. Without it React Router shows its own developer error page
 * when a page crashes; the root ErrorBoundary never sees errors inside routes.
 */
export default function RouteError({ fullScreen = false }: RouteErrorProps) {
  const error = useRouteError();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    trackCrash(error, location.pathname);
  }, [error, location.pathname]);

  // Navigating to the same address clears the router's error and renders the page again,
  // without a full reload, so the header, navigation and signed-in state stay as they are. A page
  // whose code file is gone (a new release since this tab opened) fails the same way until the
  // page is loaded again, so that one gets a real reload.
  function retry() {
    if (isChunkLoadError(error)) {
      window.location.reload();
      return;
    }
    navigate(location, { replace: true });
  }

  return <ErrorFallback onRetry={retry} fullScreen={fullScreen} />;
}

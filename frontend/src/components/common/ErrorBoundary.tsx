import { Component, type ReactNode } from "react";

import ErrorFallback from "@/components/common/ErrorFallback";
import { trackCrash } from "@/lib/analytics";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

function reload(): void {
  window.location.reload();
}

/**
 * Last line of defence around the whole app, so a crash shows a way out instead of a blank
 * page. Errors inside pages are caught earlier by the router (RouteError); this catches the
 * rest (providers, LanguageSync). A class because React has no hook for catching render errors.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: unknown): void {
    trackCrash(error, window.location.pathname);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      // A full reload, not a re-render: at this level the app's own state may be what broke,
      // and a reload also picks up a newer deployed version.
      return <ErrorFallback onRetry={reload} fullScreen />;
    }
    return this.props.children;
  }
}

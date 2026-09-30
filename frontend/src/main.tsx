import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";

import ErrorBoundary from "@/components/common/ErrorBoundary";
import LanguageSync from "@/components/common/LanguageSync";
import ThemeSync from "@/components/common/ThemeSync";
import Toaster from "@/components/common/Toast";
import InstallPrompt from "@/components/layout/InstallPrompt";
import AuthProvider from "@/hooks/useAuth";
import { toast } from "@/hooks/useToast";
import { queryClient } from "@/lib/queryClient";
import { router } from "@/router";

import "@/lib/i18n";
import "@/styles/globals.css";

// People keep the installed app open for days; without a periodic check they would only
// hear about a new version after closing it completely.
const UPDATE_CHECK_INTERVAL_MS = 60 * 60 * 1000;

// registerType "prompt": a new version waits until the person chooses to load it, so a form
// they are filling in is never swapped out under them.
if ("serviceWorker" in navigator) {
  const updateServiceWorker = registerSW({
    immediate: true,
    onNeedRefresh() {
      toast({
        id: "app-update",
        messageKey: "pwa.updateAvailable",
        duration: null,
        action: { labelKey: "pwa.refresh", onClick: () => void updateServiceWorker(true) },
      });
    },
    onRegisteredSW(_url, registration) {
      if (registration !== undefined) {
        window.setInterval(() => {
          // Offline, the check fails; the next one runs an hour later anyway.
          registration.update().catch(() => undefined);
        }, UPDATE_CHECK_INTERVAL_MS);
      }
    },
  });
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <LanguageSync />
          <ThemeSync />
          <RouterProvider router={router} future={{ v7_startTransition: true }} />
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
    <Toaster />
    {/* Outside the router so the install offer also reaches signed-out visitors. */}
    <InstallPrompt />
  </React.StrictMode>
);

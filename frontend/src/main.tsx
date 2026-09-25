import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";

import LanguageSync from "@/components/common/LanguageSync";
import AuthProvider from "@/hooks/useAuth";
import { queryClient } from "@/lib/queryClient";
import { router } from "@/router";

import "@/lib/i18n";
import "@/styles/globals.css";

// autoUpdate: the new service worker takes over silently on the next load,
// no "update available" prompt yet — that needs the toast system (NF-P1-026).
if ("serviceWorker" in navigator) {
  registerSW({ immediate: true });
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <LanguageSync />
        <RouterProvider router={router} future={{ v7_startTransition: true }} />
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>
);

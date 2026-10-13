import type { ComponentType } from "react";
import { createBrowserRouter, type RouteObject } from "react-router-dom";

import ProtectedRoute from "@/components/common/ProtectedRoute";
import RouteError from "@/components/common/RouteError";
import RouteLoading from "@/components/common/RouteLoading";
import { PILLAR_ITEMS } from "@/components/layout/navItems";
import Landing from "@/pages/Landing";
import NotFound from "@/pages/NotFound";
import SignIn from "@/pages/SignIn";

type PageModule = { default: ComponentType };

// Everything behind sign-in loads on demand (NF-P4-003): the Firebase data SDK, the map,
// push messaging and charts used to be in the one file every visitor downloaded first. The
// router fetches every matched route's module in parallel, so a deep link does not wait
// through a chain of downloads. Landing and sign-in stay in the first download because
// they are the pages a new visitor opens.
function page(load: () => Promise<PageModule>): Pick<RouteObject, "lazy"> {
  return { lazy: async () => ({ Component: (await load()).default }) };
}

// Each pillar route shows ComingSoon until its own task swaps in the real page element.
// Every pillar's primary route is its overview page, same as Remittance (`/remittance`,
// compare) and Radar (`/radar`, the heatmap) — the Financial Identity Builder's is its
// dashboard (NF-P3-017), with logging activity (NF-P3-016) moved to its own `/identity/log`.
const PILLAR_PAGES: Readonly<Record<string, () => Promise<PageModule>>> = {
  "/contract": () => import("@/pages/contract/ContractUpload"),
  "/radar": () => import("@/pages/radar/RadarHeatmap"),
  "/remittance": () => import("@/pages/remittance/RemittanceCompare"),
  "/identity": () => import("@/pages/fib/FIBDashboard"),
};

const pillarRoutes: RouteObject[] = PILLAR_ITEMS.map((pillar) => ({
  path: pillar.to,
  ...page(
    PILLAR_PAGES[pillar.to] ??
      (async () => {
        const { default: ComingSoon } = await import("@/pages/ComingSoon");
        return { default: () => <ComingSoon pillar={pillar} /> };
      })
  ),
}));

export const router = createBrowserRouter([
  {
    // Catches a crash in any page outside the app shell (landing, sign-in, onboarding).
    errorElement: <RouteError fullScreen />,
    // Shown while the first pages' modules download, instead of a blank screen.
    HydrateFallback: RouteLoading,
    children: [
      { path: "/", element: <Landing /> },
      { path: "/sign-in", element: <SignIn /> },
      {
        element: <ProtectedRoute />,
        children: [
          { path: "/onboarding", ...page(() => import("@/pages/Onboarding")) },
          {
            // Every app page needs a finished profile (NF-P1-022).
            ...page(() => import("@/components/common/RequireOnboarding")),
            children: [
              {
                ...page(() => import("@/components/layout/AppShell")),
                children: [
                  {
                    // Inside the shell, so a crashed page keeps the header and navigation.
                    errorElement: <RouteError />,
                    children: [
                      { path: "/dashboard", ...page(() => import("@/pages/Dashboard")) },
                      { path: "/profile", ...page(() => import("@/pages/Profile")) },
                      {
                        path: "/contract/history",
                        ...page(() => import("@/pages/contract/ContractList")),
                      },
                      {
                        path: "/contract/:contractId",
                        ...page(() => import("@/pages/contract/ContractReport")),
                      },
                      {
                        path: "/radar/heatmap",
                        ...page(() => import("@/pages/radar/RadarHeatmap")),
                      },
                      {
                        path: "/remittance/history",
                        ...page(() => import("@/pages/remittance/RemittanceHistory")),
                      },
                      { path: "/radar/report", ...page(() => import("@/pages/radar/RadarReport")) },
                      {
                        path: "/radar/entity/:slug",
                        ...page(() => import("@/pages/radar/RadarEntity")),
                      },
                      { path: "/radar/alerts", ...page(() => import("@/pages/radar/RadarAlerts")) },
                      {
                        path: "/identity/log",
                        ...page(() => import("@/pages/fib/FIBLogActivity")),
                      },
                      {
                        path: "/identity/export",
                        ...page(() => import("@/pages/fib/FIBExportReport")),
                      },
                      ...pillarRoutes,
                      // The two Future Scope modules (NF-F0-006). Each route module holds its own
                      // flag guard, so a user the flag is off for downloads nothing of the module.
                      { path: "/coach", ...page(() => import("@/pages/coach/CoachRoute")) },
                      {
                        path: "/coach/plan/:planId",
                        ...page(() => import("@/pages/coach/CoachPlanRoute")),
                      },
                      {
                        path: "/coach/checkin/:planId",
                        ...page(() => import("@/pages/coach/CoachCheckinRoute")),
                      },
                      {
                        path: "/scam-check",
                        ...page(() => import("@/pages/scam/ScamCheckRoute")),
                      },
                      {
                        path: "/scam-check/history",
                        ...page(() => import("@/pages/scam/ScamHistoryRoute")),
                      },
                      {
                        path: "/scam-check/history/:id",
                        ...page(() => import("@/pages/scam/ScamCheckDetailRoute")),
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

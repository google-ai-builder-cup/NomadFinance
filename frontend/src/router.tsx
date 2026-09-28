import { createBrowserRouter } from "react-router-dom";

import ProtectedRoute from "@/components/common/ProtectedRoute";
import RequireOnboarding from "@/components/common/RequireOnboarding";
import RouteError from "@/components/common/RouteError";
import AppShell from "@/components/layout/AppShell";
import { PILLAR_ITEMS } from "@/components/layout/navItems";
import ComingSoon from "@/pages/ComingSoon";
import ContractUpload from "@/pages/contract/ContractUpload";
import Dashboard from "@/pages/Dashboard";
import Landing from "@/pages/Landing";
import NotFound from "@/pages/NotFound";
import Onboarding from "@/pages/Onboarding";
import Profile from "@/pages/Profile";
import RemittanceCompare from "@/pages/remittance/RemittanceCompare";
import SignIn from "@/pages/SignIn";

// Each pillar route shows ComingSoon until its own task swaps in the real page element.
// Contract Shield (NF-P2-009) and Remittance X-Ray (NF-P2-018) have theirs; the rest wait their turn.
const PILLAR_PAGES: Readonly<Record<string, JSX.Element>> = {
  "/contract": <ContractUpload />,
  "/remittance": <RemittanceCompare />,
};

const pillarRoutes = PILLAR_ITEMS.map((pillar) => ({
  path: pillar.to,
  element: PILLAR_PAGES[pillar.to] ?? <ComingSoon pillar={pillar} />,
}));

export const router = createBrowserRouter([
  {
    // Catches a crash in any page outside the app shell (landing, sign-in, onboarding).
    errorElement: <RouteError fullScreen />,
    children: [
      { path: "/", element: <Landing /> },
      { path: "/sign-in", element: <SignIn /> },
      {
        element: <ProtectedRoute />,
        children: [
          { path: "/onboarding", element: <Onboarding /> },
          {
            // Every app page needs a finished profile (NF-P1-022).
            element: <RequireOnboarding />,
            children: [
              {
                element: <AppShell />,
                children: [
                  {
                    // Inside the shell, so a crashed page keeps the header and navigation.
                    errorElement: <RouteError />,
                    children: [
                      { path: "/dashboard", element: <Dashboard /> },
                      { path: "/profile", element: <Profile /> },
                      ...pillarRoutes,
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

import { createBrowserRouter } from "react-router-dom";

import ProtectedRoute from "@/components/common/ProtectedRoute";
import RequireOnboarding from "@/components/common/RequireOnboarding";
import AppShell from "@/components/layout/AppShell";
import { PILLAR_ITEMS } from "@/components/layout/navItems";
import ComingSoon from "@/pages/ComingSoon";
import Dashboard from "@/pages/Dashboard";
import Landing from "@/pages/Landing";
import NotFound from "@/pages/NotFound";
import Onboarding from "@/pages/Onboarding";
import SignIn from "@/pages/SignIn";

// Each pillar route shows ComingSoon until its own task swaps in the real page element.
const pillarRoutes = PILLAR_ITEMS.map((pillar) => ({
  path: pillar.to,
  element: <ComingSoon pillar={pillar} />,
}));

export const router = createBrowserRouter([
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
            children: [{ path: "/dashboard", element: <Dashboard /> }, ...pillarRoutes],
          },
        ],
      },
    ],
  },
  { path: "*", element: <NotFound /> },
]);

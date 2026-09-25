import { createBrowserRouter, Navigate } from "react-router-dom";

import ProtectedRoute from "@/components/common/ProtectedRoute";
import AppShell from "@/components/layout/AppShell";
import { PILLAR_ITEMS } from "@/components/layout/navItems";
import ComingSoon from "@/pages/ComingSoon";
import Dashboard from "@/pages/Dashboard";
import NotFound from "@/pages/NotFound";
import SignIn from "@/pages/SignIn";

// Each pillar route shows ComingSoon until its own task swaps in the real page element.
const pillarRoutes = PILLAR_ITEMS.map((pillar) => ({
  path: pillar.to,
  element: <ComingSoon pillar={pillar} />,
}));

export const router = createBrowserRouter([
  // TODO(Aditya): replace this redirect with the landing page NF-P1-021
  { path: "/", element: <Navigate to="/dashboard" replace /> },
  { path: "/sign-in", element: <SignIn /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [{ path: "/dashboard", element: <Dashboard /> }, ...pillarRoutes],
      },
    ],
  },
  { path: "*", element: <NotFound /> },
]);

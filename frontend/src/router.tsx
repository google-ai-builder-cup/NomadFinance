import { createBrowserRouter } from "react-router-dom";

import App from "@/App";
import ProtectedRoute from "@/components/common/ProtectedRoute";
import Dashboard from "@/pages/Dashboard";
import SignIn from "@/pages/SignIn";

// Minimal tree for sign-in (NF-P1-009). The app shell, landing page and pillar pages
// are added by NF-P1-010 and later tasks; new signed-in pages go under ProtectedRoute.
export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
  },
  {
    path: "/sign-in",
    element: <SignIn />,
  },
  {
    element: <ProtectedRoute />,
    children: [{ path: "/dashboard", element: <Dashboard /> }],
  },
]);

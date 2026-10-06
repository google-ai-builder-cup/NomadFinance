import { lazy } from "react";

import FlagRoute from "@/components/common/FlagRoute";

// The page is lazy inside the guard rather than through the router's own `lazy`: the router
// fetches a matched route's module before any guard has run, and a user the `coach` flag is
// off for must not download the page. This small module is what the router loads.
const CoachHome = lazy(() => import("@/pages/coach/CoachHome"));

/** The `/coach` route: the page for users the flag is on for, a redirect for everyone else. */
export default function CoachRoute() {
  return (
    <FlagRoute flag="coach">
      <CoachHome />
    </FlagRoute>
  );
}

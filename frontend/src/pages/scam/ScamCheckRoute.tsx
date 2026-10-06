import { lazy } from "react";

import FlagRoute from "@/components/common/FlagRoute";

// Lazy inside the guard for the same reason as the coach route: see pages/coach/CoachRoute.tsx.
const ScamCheckHome = lazy(() => import("@/pages/scam/ScamCheckHome"));

/** The `/scam-check` route: the page for users the flag is on for, a redirect for everyone else. */
export default function ScamCheckRoute() {
  return (
    <FlagRoute flag="scam">
      <ScamCheckHome />
    </FlagRoute>
  );
}

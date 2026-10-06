import { lazy } from "react";

import FlagRoute from "@/components/common/FlagRoute";
import { loadNamespace } from "@/lib/i18n";

// Lazy inside the guard for the same reason as the coach route: see pages/coach/CoachRoute.tsx.
const ScamCheckHome = lazy(async () => {
  const [page] = await Promise.all([import("@/pages/scam/ScamCheckHome"), loadNamespace("scam")]);
  return page;
});

/** The `/scam-check` route: the page for users the flag is on for, a redirect for everyone else. */
export default function ScamCheckRoute() {
  return (
    <FlagRoute flag="scam">
      <ScamCheckHome />
    </FlagRoute>
  );
}

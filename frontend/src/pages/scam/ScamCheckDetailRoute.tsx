import { lazy } from "react";

import FlagRoute from "@/components/common/FlagRoute";
import { loadNamespace } from "@/lib/i18n";

// Lazy inside the guard, as in ScamCheckRoute: a user the flag is off for downloads none of it.
const ScamCheckDetail = lazy(async () => {
  const [page] = await Promise.all([import("@/pages/scam/ScamCheckDetail"), loadNamespace("scam")]);
  return page;
});

/** The `/scam-check/history/:id` route: one stored check, for users the flag is on for. */
export default function ScamCheckDetailRoute() {
  return (
    <FlagRoute flag="scam">
      <ScamCheckDetail />
    </FlagRoute>
  );
}

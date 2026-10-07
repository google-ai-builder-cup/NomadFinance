import { lazy } from "react";

import FlagRoute from "@/components/common/FlagRoute";
import { loadNamespace } from "@/lib/i18n";

// Lazy inside the guard, as in ScamCheckRoute: a user the flag is off for downloads none of it.
const ScamHistory = lazy(async () => {
  const [page] = await Promise.all([import("@/pages/scam/ScamHistory"), loadNamespace("scam")]);
  return page;
});

/** The `/scam-check/history` route: the list for users the flag is on for, a redirect otherwise. */
export default function ScamHistoryRoute() {
  return (
    <FlagRoute flag="scam">
      <ScamHistory />
    </FlagRoute>
  );
}

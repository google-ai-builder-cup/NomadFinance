import { lazy } from "react";

import FlagRoute from "@/components/common/FlagRoute";
import { loadNamespace } from "@/lib/i18n";

// Like `/coach/plan/:planId`: the page is lazy inside the flag guard, so a worker the `coach` flag
// is off for downloads nothing of it, and the Coach's strings come with the page.
const CoachCheckinPage = lazy(async () => {
  const [page] = await Promise.all([
    import("@/pages/coach/CoachCheckinPage"),
    loadNamespace("coach"),
  ]);
  return page;
});

/** The `/coach/checkin/:planId` route: the check-in for users the flag is on for, a redirect for the rest. */
export default function CoachCheckinRoute() {
  return (
    <FlagRoute flag="coach">
      <CoachCheckinPage />
    </FlagRoute>
  );
}

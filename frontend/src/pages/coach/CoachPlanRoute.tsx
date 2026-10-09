import { lazy } from "react";

import FlagRoute from "@/components/common/FlagRoute";
import { loadNamespace } from "@/lib/i18n";

// Like `/coach`: the page is lazy inside the flag guard, so a worker the `coach` flag is off for
// downloads nothing of it, and the Coach's strings come with the page.
const CoachPlanPage = lazy(async () => {
  const [page] = await Promise.all([import("@/pages/coach/CoachPlanPage"), loadNamespace("coach")]);
  return page;
});

/** The `/coach/plan/:planId` route: the plan page for users the flag is on for, a redirect for the rest. */
export default function CoachPlanRoute() {
  return (
    <FlagRoute flag="coach">
      <CoachPlanPage />
    </FlagRoute>
  );
}

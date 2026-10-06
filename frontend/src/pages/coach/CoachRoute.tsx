import { lazy } from "react";

import FlagRoute from "@/components/common/FlagRoute";
import { loadNamespace } from "@/lib/i18n";

// The page is lazy inside the guard rather than through the router's own `lazy`: the router
// fetches a matched route's module before any guard has run, and a user the `coach` flag is
// off for must not download the page. This small module is what the router loads.
// The coach's strings are fetched with the page, so neither is downloaded for anyone else.
const CoachHome = lazy(async () => {
  const [page] = await Promise.all([import("@/pages/coach/CoachHome"), loadNamespace("coach")]);
  return page;
});

/** The `/coach` route: the page for users the flag is on for, a redirect for everyone else. */
export default function CoachRoute() {
  return (
    <FlagRoute flag="coach">
      <CoachHome />
    </FlagRoute>
  );
}

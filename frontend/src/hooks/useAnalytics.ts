import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { PILLAR_ITEMS } from "@/components/layout/navItems";
import { useUserProfile } from "@/hooks/useUser";
import {
  type PillarId,
  setAnalyticsUserProperties,
  trackPageView,
  trackPillarUsed,
} from "@/lib/analytics";

// "/remittance" -> "remittance": the route path is the pillar id, so a new pillar in
// PILLAR_ITEMS is counted without touching this file.
function pillarAt(pathname: string): PillarId | null {
  const pillar = PILLAR_ITEMS.find(({ to }) => pathname === to || pathname.startsWith(`${to}/`));
  return pillar ? (pillar.to.slice(1) as PillarId) : null;
}

/** Reports page views, pillar visits and the signed-in user's profile facts. Mount it once. */
export function useAnalytics(): void {
  const { pathname } = useLocation();
  const profile = useUserProfile().data;
  const pillar = pillarAt(pathname);

  useEffect(() => trackPageView(pathname), [pathname]);

  // Its own effect: moving between pages of the same pillar is one visit, not several.
  useEffect(() => {
    if (pillar !== null) {
      trackPillarUsed(pillar);
    }
  }, [pillar]);

  const { host_country, home_country, job_type, preferred_language } = profile ?? {};
  useEffect(() => {
    if (host_country && home_country && job_type && preferred_language) {
      setAnalyticsUserProperties({ host_country, home_country, job_type, preferred_language });
    }
  }, [host_country, home_country, job_type, preferred_language]);
}

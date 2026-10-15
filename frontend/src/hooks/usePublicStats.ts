import { useQuery } from "@tanstack/react-query";

import { getPublicStats } from "@/services/publicStatsService";
import { isApiConfigured } from "@/services/apiClient";

// The backend caches for five minutes, so asking sooner only returns the same numbers.
const FIVE_MINUTES = 5 * 60 * 1000;

/** Platform totals for the landing page. Off when no backend is configured; a failure is not
 * retried or shown, because the strip simply stays out and the page reads fine without it. */
export function usePublicStats() {
  return useQuery({
    queryKey: ["public-stats"],
    queryFn: getPublicStats,
    enabled: isApiConfigured,
    staleTime: FIVE_MINUTES,
    retry: false,
  });
}

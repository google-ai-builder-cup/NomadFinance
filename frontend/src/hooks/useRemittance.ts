import { useMutation, useQuery, type UseQueryResult } from "@tanstack/react-query";

import { trackRemittanceCompared } from "@/lib/analytics";
import { ApiError } from "@/services/apiClient";
import { compareRemittance, getRemittanceTrends } from "@/services/remittanceService";
import type { CorridorId } from "@/types/enums";
import type { RemittanceCompareRequest, RemittanceTrends, TrendDays } from "@/types/remittance";

/**
 * Compare the services of a corridor for one amount. A mutation, not a query: the worker
 * starts it with the form, and a new amount replaces the last answer.
 */
export function useCompareRemittance() {
  return useMutation({
    mutationFn: (request: RemittanceCompareRequest) => compareRemittance(request),
    onSuccess: (comparison) => trackRemittanceCompared(comparison.corridor_id),
    // The page shows the error next to the form.
    meta: { inlineError: true },
  });
}

/**
 * A corridor's rate history and best day to send, for the trend chart (NF-P2-020). A query,
 * not a mutation: it loads on its own once a corridor is known, and a new period (`days`)
 * just switches the cache key, so flipping back to one already seen is instant.
 *
 * A 404 (no history stored yet for the corridor) is not retried: the chart's own empty state
 * handles it, same as `compareFailure` does for the comparison form.
 */
export function useRemittanceTrends(
  corridorId: CorridorId | null,
  days: TrendDays
): UseQueryResult<RemittanceTrends> {
  return useQuery({
    queryKey: ["remittanceTrends", corridorId, days] as const,
    queryFn: () => getRemittanceTrends(corridorId as CorridorId, days),
    enabled: corridorId !== null,
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.status === 404) && failureCount < 1,
  });
}

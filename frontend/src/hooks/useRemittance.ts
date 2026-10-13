import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { useAuth } from "@/hooks/useAuth";
import { trackRemittanceCompared } from "@/lib/analytics";
import { ApiError } from "@/services/apiClient";
import {
  compareRemittance,
  getRemittanceSavings,
  getRemittanceTrends,
  listLoggedTransfers,
  logTransfer,
  recommendRemittance,
} from "@/services/remittanceService";
import type { CorridorId } from "@/types/enums";
import type {
  LoggedTransfer,
  RemittanceCompareRequest,
  RemittanceComparison,
  RemittanceRecommendRequest,
  RemittanceSavings,
  RemittanceTrends,
  TrendDays,
} from "@/types/remittance";

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

/**
 * What the best service, instead of the worst, would have been worth over the last `months`
 * (NF-P2-022, NF-P2-023's "you would have saved $X" hero moment). A query, cached per
 * corridor, amount and period.
 *
 * A 404 (no prices or no history stored yet) is not retried: the callout's own empty state
 * handles it, same as `useRemittanceTrends`.
 */
export interface LogTransferArgs {
  comparison: RemittanceComparison;
  rpwId: number;
}

/**
 * Log the service the worker actually used for this comparison (NF-P3-016's "I used this"
 * action), the missing link the design doc calls "auto from Pillar 1" into the Financial
 * Identity Builder. A mutation, not tied to the comparison query: a retry would store the
 * same transfer twice, so a failed attempt needs a fresh click, not an automatic one.
 */
export function useLogTransfer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ comparison, rpwId }: LogTransferArgs) =>
      logTransfer({ comparison, rpw_id: rpwId }),
    // The history lists what was just logged the next time it is opened.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["loggedTransfers"] }),
    retry: false,
  });
}

/** The worker's logged transfers, newest first (`/remittance/history`). */
export function useLoggedTransfers(): UseQueryResult<LoggedTransfer[]> {
  const { user } = useAuth();
  const uid = user?.uid;
  return useQuery({
    queryKey: ["loggedTransfers", uid] as const,
    queryFn: () => listLoggedTransfers(uid ?? ""),
    enabled: uid !== undefined,
    staleTime: 60_000,
  });
}

export function useRemittanceSavings(
  corridorId: CorridorId | null,
  amount: number | null,
  months: number
): UseQueryResult<RemittanceSavings> {
  return useQuery({
    queryKey: ["remittanceSavings", corridorId, amount, months] as const,
    queryFn: () => getRemittanceSavings(corridorId as CorridorId, amount as number, months),
    enabled: corridorId !== null && amount !== null,
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.status === 404) && failureCount < 1,
  });
}

/**
 * Ask for the recommendation (NF-P2-016) when the worker taps for it, not on every comparison:
 * it is the one Gemini call on the page. Shows its own error, never the global toast.
 */
export function useRecommendRemittance() {
  return useMutation({
    mutationFn: (body: RemittanceRecommendRequest) => recommendRemittance(body),
    retry: false,
    meta: { inlineError: true },
  });
}

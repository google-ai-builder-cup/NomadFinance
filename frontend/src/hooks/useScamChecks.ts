import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getCheck, listChecks, reportCheck } from "@/services/scamService";
import type { ScamReportRequest } from "@/types/scam";

/** Rows per page: the contract's own default. */
export const HISTORY_PAGE_SIZE = 20;

/** Every query about stored checks starts with this, so one invalidation refreshes them all. */
export const SCAM_CHECKS_KEY = ["scam", "checks"] as const;

/** The worker's checks, newest first, a page at a time. The cursor is the server's, tied to the
 * worker, so a page is only ever asked for through the one before it. */
export function useScamHistory() {
  return useInfiniteQuery({
    queryKey: [...SCAM_CHECKS_KEY, "list"],
    queryFn: ({ pageParam }) => listChecks(HISTORY_PAGE_SIZE, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
}

/** One stored check. Read live, so a contact reported since shows its current count. */
export function useScamCheck(id: string) {
  return useQuery({
    queryKey: [...SCAM_CHECKS_KEY, "detail", id],
    queryFn: () => getCheck(id),
  });
}

/**
 * Warn other workers about one check. A mutation that never retries by itself: the worker taps
 * Send, and a failed send is answered with a button, not a silent second report. (The server
 * reports a check once anyway, so a deliberate second tap is safe.)
 */
export function useReportCheck(checkId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ScamReportRequest) => reportCheck(checkId, body),
    retry: false,
    // The sheet shows the error beside its Send button.
    meta: { inlineError: true },
    // The history's "reported" marker and the stored check both change.
    onSuccess: () => client.invalidateQueries({ queryKey: SCAM_CHECKS_KEY }),
  });
}

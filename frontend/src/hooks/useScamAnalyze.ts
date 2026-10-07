import { useMutation, useQueryClient } from "@tanstack/react-query";

import { SCAM_CHECKS_KEY } from "@/hooks/useScamChecks";
import { analyzeScam } from "@/services/scamService";
import type { ScamCheckRequest } from "@/types/scam";

/**
 * Run one scam check. A mutation, not a query: the worker starts it, a repeat is the worker's
 * choice, and it must never retry by itself (a retry spends one of the 20 checks an hour).
 */
export function useScamAnalyze() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (request: ScamCheckRequest) => analyzeScam(request),
    retry: false,
    // The screen shows the error beside the form.
    meta: { inlineError: true },
    // The check is now the newest row of the history.
    onSuccess: () => client.invalidateQueries({ queryKey: SCAM_CHECKS_KEY }),
  });
}

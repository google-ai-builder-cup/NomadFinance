import { useMutation } from "@tanstack/react-query";

import { trackRemittanceCompared } from "@/lib/analytics";
import { compareRemittance } from "@/services/remittanceService";
import type { RemittanceCompareRequest } from "@/types/remittance";

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

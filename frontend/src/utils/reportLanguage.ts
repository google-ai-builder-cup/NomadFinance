import { ApiError } from "@/services/apiClient";
import { requestFailureKey } from "@/utils/pipelineProgress";

/**
 * i18n key for why the report could not be shown (NF-P2-011, NF-P2-012).
 *
 * A 409 from the switch means the contract's analysis is not current, so the fix is to check
 * the contract again, not to retry. Other API failures read like the analysis' own (busy,
 * too slow, offline). Anything else is a failed Firestore read.
 */
export function reportFailureKey(error: unknown): string {
  if (error instanceof ApiError) {
    return error.status === 409 ? "contract.report.switchOutOfDate" : requestFailureKey(error);
  }
  return "contract.result.reportLoadError";
}

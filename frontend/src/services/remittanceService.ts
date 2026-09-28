import { apiRequest } from "@/services/apiClient";
import type { RemittanceCompareRequest, RemittanceComparison } from "@/types/remittance";

/**
 * Every surveyed way to send `amount` along a corridor, ranked by what the recipient receives
 * (`POST /api/v1/remittance/compare`, NF-P2-014). No AI call; answers in well under a second.
 */
export async function compareRemittance(
  request: RemittanceCompareRequest
): Promise<RemittanceComparison> {
  const response = await apiRequest("/api/v1/remittance/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return (await response.json()) as RemittanceComparison;
}

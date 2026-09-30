import { apiRequest } from "@/services/apiClient";
import type { CorridorId } from "@/types/enums";
import type {
  RemittanceCompareRequest,
  RemittanceComparison,
  RemittanceTrends,
  TrendDays,
} from "@/types/remittance";

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

/**
 * A corridor's mid-market rate history, for the trend chart, and the weekday that is usually
 * best to send on (`GET /api/v1/remittance/trends`, NF-P2-015). No AI call.
 */
export async function getRemittanceTrends(
  corridorId: CorridorId,
  days: TrendDays
): Promise<RemittanceTrends> {
  const query = new URLSearchParams({ corridor_id: corridorId, days: String(days) });
  const response = await apiRequest(`/api/v1/remittance/trends?${query}`);
  return (await response.json()) as RemittanceTrends;
}

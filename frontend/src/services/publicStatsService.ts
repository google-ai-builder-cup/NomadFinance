import { ApiError, apiUrl } from "@/services/apiClient";
import type { PublicStats } from "@/types/publicStats";

/** The platform totals for the landing page. Public, so it sends no token (the visitor is not
 * signed in), which is why it does not go through `apiRequest`. */
export async function getPublicStats(): Promise<PublicStats> {
  let response: Response;
  try {
    response = await fetch(apiUrl("/api/v1/public/stats"));
  } catch {
    throw new ApiError(0, "Network error");
  }
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText);
  }
  return (await response.json()) as PublicStats;
}

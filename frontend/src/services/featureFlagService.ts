import { apiRequest } from "@/services/apiClient";
import { ALL_FLAGS_OFF, FEATURE_FLAGS, type FeatureFlags } from "@/types/flags";

/**
 * Read the answer of `GET /api/v2/flags`. Only the boolean `true` turns a module on, so a
 * missing key, a string or a number reads as off, the same rule the backend applies when it
 * reads the flag document. An answer that is not an object at all is everything off.
 */
export function parseFeatureFlags(body: unknown): FeatureFlags {
  if (typeof body !== "object" || body === null) {
    return ALL_FLAGS_OFF;
  }
  const record = body as Record<string, unknown>;
  return Object.fromEntries(
    FEATURE_FLAGS.map((flag) => [flag, record[flag] === true])
  ) as unknown as FeatureFlags;
}

/** Which modules are on for the signed-in user. The backend decides; the browser never sees the allow-lists. */
export async function getFeatureFlags(): Promise<FeatureFlags> {
  const response = await apiRequest("/api/v2/flags");
  return parseFeatureFlags(await response.json());
}

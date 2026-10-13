import { ApiError, apiRequest } from "@/services/apiClient";
import { timeoutSignal } from "@/utils/timeoutSignal";
import type {
  ScamAnalyzeResponse,
  ScamCheckDetail,
  ScamCheckList,
  ScamCheckRequest,
  ScamReportRequest,
  ScamReportResponse,
} from "@/types/scam";

// docs/api/v2-scam.md: a scam waits for the explainer, which has taken 15 to 40 s, so a slow
// answer is not a failure. The contract allows the client 60 s, but with Gemini rate-limited
// (retries on the verdict, then the explainer's fallback) the server has taken 73 s and still
// answered 200; at 60 s the screen gave up on a check that had worked. 90 s covers that.
export const ANALYZE_TIMEOUT_MS = 90_000;

/** The body for the one analyze route: JSON for a message, a form for a screenshot. */
export function buildAnalyzeInit({ input, language, corridorId }: ScamCheckRequest): RequestInit {
  if (input.kind === "screenshot") {
    // No Content-Type: the browser adds the multipart boundary itself.
    const form = new FormData();
    // The name is passed on purpose: a part without one is read as a text field, not a file.
    form.append("image", input.file, input.file.name || "screenshot");
    form.append("language", language);
    if (corridorId !== undefined) {
      form.append("corridor_id", corridorId);
    }
    return { method: "POST", body: form };
  }
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: input.text.trim(),
      language,
      ...(corridorId !== undefined && { corridor_id: corridorId }),
    }),
  };
}

/** Check one message or screenshot. Pasting, uploading and sharing all end up here. */
export async function analyzeScam(request: ScamCheckRequest): Promise<ScamAnalyzeResponse> {
  const signal = timeoutSignal(ANALYZE_TIMEOUT_MS);
  try {
    const response = await apiRequest("/api/v2/scam/analyze", {
      ...buildAnalyzeInit(request),
      signal,
    });
    return (await response.json()) as ScamAnalyzeResponse;
  } catch (error) {
    // apiClient reports any fetch failure as status 0; a spent timer is a slow answer instead.
    if (error instanceof ApiError && error.status === 0 && signal.aborted) {
      throw new ApiError(408, "timeout");
    }
    throw error;
  }
}

/** One page of the worker's history, newest first. `cursor` is the previous page's `next_cursor`. */
export async function listChecks(limit: number, cursor?: string): Promise<ScamCheckList> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor !== undefined) {
    query.set("cursor", cursor);
  }
  const response = await apiRequest(`/api/v2/scam/checks?${query}`);
  return (await response.json()) as ScamCheckList;
}

/** One stored check. A missing, expired or someone else's check is the same 404. */
export async function getCheck(id: string): Promise<ScamCheckDetail> {
  const response = await apiRequest(`/api/v2/scam/checks/${encodeURIComponent(id)}`);
  return (await response.json()) as ScamCheckDetail;
}

/** Report a scam to Exploitation Radar. 201 for a new report, 200 for one made before. */
export async function reportCheck(
  id: string,
  body: ScamReportRequest
): Promise<ScamReportResponse> {
  const response = await apiRequest(`/api/v2/scam/checks/${encodeURIComponent(id)}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return (await response.json()) as ScamReportResponse;
}

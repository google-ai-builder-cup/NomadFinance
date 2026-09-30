import { apiRequest } from "@/services/apiClient";
import type { RadarEvidenceResponse, RadarReportRequest, RadarReportResponse } from "@/types/radar";

/**
 * Send a report (`POST /api/v1/radar/report`). The backend screens it, works out the
 * violation type and stores it; usually 3 to 15 s because several AI steps run.
 */
export async function submitReport(body: RadarReportRequest): Promise<RadarReportResponse> {
  const response = await apiRequest("/api/v1/radar/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return (await response.json()) as RadarReportResponse;
}

/** Attach one photo or document to a report the worker just filed (at most 5 per report). */
export async function uploadEvidence(reportId: string, file: File): Promise<RadarEvidenceResponse> {
  const body = new FormData();
  body.append("file", file);
  const response = await apiRequest(`/api/v1/radar/report/${reportId}/evidence`, {
    method: "POST",
    body,
  });
  return (await response.json()) as RadarEvidenceResponse;
}

import { collection, getDocs, query, where } from "firebase/firestore";

import { appCheckHeader } from "@/lib/appCheck";
import { db } from "@/lib/firestore";
import { apiRequest } from "@/services/apiClient";
import type { CorridorId } from "@/types/enums";
import type {
  RadarEntityProfile,
  RadarEvidenceResponse,
  RadarReportRequest,
  RadarReportResponse,
  RadarReportSummary,
  RouteAlert,
} from "@/types/radar";

/**
 * Send a report (`POST /api/v1/radar/report`). The backend screens it, works out the
 * violation type and stores it; usually 3 to 15 s because several AI steps run.
 *
 * Carries an App Check token when one is configured here (NF-P3-025) — the one request this
 * app attaches it to, since this is the one public-facing submission form worth protecting
 * from scripted abuse. `appCheckHeader()` resolves to `{}` when it isn't configured, so this
 * is exactly today's request shape until a site key is wired through.
 */
export async function submitReport(body: RadarReportRequest): Promise<RadarReportResponse> {
  const response = await apiRequest("/api/v1/radar/report", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await appCheckHeader()) },
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

/**
 * Every business profile (`radar_entities`), straight from Firestore: signed-in users may
 * read it (firestore.rules) and it holds no personal data. The heatmap totals it per corridor.
 */
export async function listRadarEntities(): Promise<RadarEntityProfile[]> {
  const snapshot = await getDocs(collection(db, "radar_entities"));
  return snapshot.docs.map((entity) => ({
    ...(entity.data() as Omit<RadarEntityProfile, "slug">),
    slug: entity.id,
  }));
}

/**
 * The individual reports behind one entity's profile (`GET /api/v1/radar/entities/{slug}/reports`).
 * Unlike `radar_entities`, `radar_reports` is not client-readable (firestore.rules), so this
 * goes through the backend, which also strips `reporter_hash` and the classification internals.
 */
export async function getEntityReports(slug: string): Promise<RadarReportSummary[]> {
  const response = await apiRequest(`/api/v1/radar/entities/${slug}/reports`);
  return (await response.json()) as RadarReportSummary[];
}

/**
 * The alerts still active on these routes, newest first (`radar_alerts/{corridor}/current`,
 * readable by any signed-in user). Read directly rather than only through the worker's
 * notifications: a notification is written once, when an alert is created, so a worker who
 * joins or picks a route later would otherwise never see an alert that is still running.
 */
export async function listActiveRouteAlerts(
  corridors: readonly CorridorId[]
): Promise<RouteAlert[]> {
  const perRoute = await Promise.all(
    corridors.map(async (corridorId) => {
      const snapshot = await getDocs(
        query(
          collection(db, "radar_alerts", corridorId, "current"),
          where("status", "==", "active")
        )
      );
      return snapshot.docs.map(
        (alert) => ({ ...(alert.data() as Omit<RouteAlert, "id">), id: alert.id }) as RouteAlert
      );
    })
  );
  return perRoute.flat().sort((a, b) => b.created_at.toMillis() - a.created_at.toMillis());
}

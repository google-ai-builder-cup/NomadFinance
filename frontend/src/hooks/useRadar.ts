import { useMutation, useQuery } from "@tanstack/react-query";

import { listRadarEntities, submitReport, uploadEvidence } from "@/services/radarService";
import type { RadarReportRequest, RadarReportResponse } from "@/types/radar";

export interface SubmitReportArgs {
  report: RadarReportRequest;
  files: File[];
}

export interface SubmitReportResult {
  report: RadarReportResponse;
  attached: number;
  failed: number;
}

/**
 * Send the report, then its evidence one file at a time. Evidence is best effort: the report
 * is already stored (and counts) once the first call succeeds, so a failed photo is counted
 * for the confirmation screen instead of failing the whole submission.
 */
export function useSubmitReport() {
  return useMutation({
    mutationFn: async ({ report, files }: SubmitReportArgs): Promise<SubmitReportResult> => {
      const stored = await submitReport(report);
      let attached = 0;
      for (const file of files) {
        try {
          await uploadEvidence(stored.report_id, file);
          attached += 1;
        } catch {
          // Counted below; the reason (size, type, offline) is not actionable after the fact.
        }
      }
      return { report: stored, attached, failed: files.length - attached };
    },
    // The form shows the error next to its submit button.
    meta: { inlineError: true },
    // A repeat could store the same report twice.
    retry: false,
  });
}

/** Every business profile, for the heatmap. Aggregates change a few times a day at most. */
export function useRadarEntities() {
  return useQuery({
    queryKey: ["radar", "entities"],
    queryFn: listRadarEntities,
    staleTime: 60_000,
  });
}

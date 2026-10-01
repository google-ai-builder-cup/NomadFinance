import { useMutation, useQuery } from "@tanstack/react-query";

import { useContractParties } from "@/hooks/useContract";
import {
  getEntityReports,
  listActiveRouteAlerts,
  listRadarEntities,
  submitReport,
  uploadEvidence,
} from "@/services/radarService";
import type { CorridorId } from "@/types/enums";
import type { RadarEntityProfile, RadarReportRequest, RadarReportResponse } from "@/types/radar";
import { type FlaggedParty, findFlaggedParties } from "@/utils/flaggedParties";
import { findFlaggedEntity } from "@/utils/flaggedProviders";

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

export interface RadarEntityResult {
  /**
   * `null` both while loading and when no entity has this slug: the caller checks
   * `isPending`/`isError` first, same as any other query, before this means "not found".
   */
  entity: RadarEntityProfile | null;
  isPending: boolean;
  isError: boolean;
  refetch: () => void;
}

/**
 * One business profile, for the entity page. Shares `useRadarEntities`'s cache (the
 * heatmap's own query) instead of a separate fetch.
 */
export function useRadarEntity(slug: string): RadarEntityResult {
  const entities = useRadarEntities();
  return {
    entity: entities.data?.find((candidate) => candidate.slug === slug) ?? null,
    isPending: entities.isPending,
    isError: entities.isError,
    refetch: () => void entities.refetch(),
  };
}

/** Every report behind one entity's profile, newest first. */
export function useEntityReports(slug: string) {
  return useQuery({
    queryKey: ["radar", "entity", slug, "reports"],
    queryFn: () => getEntityReports(slug),
    staleTime: 60_000,
  });
}

/**
 * The flagged radar profile of a remittance provider, or null: not flagged, not found, still
 * loading, or the read failed. A warning is an extra, so it never blocks or breaks the
 * comparison it sits on. Shares `useRadarEntities`'s cache: one read for every badge on a page.
 */
export function useFlaggedProvider(firm: string): RadarEntityProfile | null {
  const entities = useRadarEntities();
  return findFlaggedEntity(firm, entities.data ?? []);
}

/**
 * The flagged radar profiles of the employer and agency a contract names (NF-P3-023): empty
 * while anything is loading, when nothing is flagged, or when a read fails. A warning is an
 * extra and never blocks or breaks the report it sits on.
 */
export function useFlaggedParties(contractId: string): FlaggedParty[] {
  const parties = useContractParties(contractId);
  const entities = useRadarEntities();
  return parties.data === undefined ? [] : findFlaggedParties(parties.data, entities.data ?? []);
}

/** The alerts still active on the worker's routes (`alertRoutes`), newest first. */
export function useRouteAlerts(corridors: readonly CorridorId[]) {
  return useQuery({
    queryKey: ["routeAlerts", [...corridors]] as const,
    queryFn: () => listActiveRouteAlerts(corridors),
    enabled: corridors.length > 0,
    staleTime: 60_000,
  });
}

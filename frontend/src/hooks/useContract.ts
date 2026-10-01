import { queryOptions, useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useAuth } from "@/hooks/useAuth";
import {
  analyzeContract,
  getContractParties,
  getContractReport,
  listRecentContracts,
  switchReportLanguage,
  uploadContract,
  watchContractProgress,
} from "@/services/contractService";
import { ApiError } from "@/services/apiClient";
import type {
  AnalyzeRequest,
  ContractAnalysis,
  ContractReport,
  Legibility,
} from "@/types/contract";
import type { LanguageCode } from "@/types/enums";
import { isRetryable } from "@/utils/errors";
import type { ContractProgressDoc } from "@/utils/pipelineProgress";

export interface UploadAndAnalyzeArgs {
  file: File;
  choices: AnalyzeRequest;
}

export interface UploadAndAnalyzeResult {
  contractId: string;
  legibility: Legibility;
  /** Null when legibility is `poor`: the worker is asked for a clearer photo, not analysed. */
  analysis: ContractAnalysis | null;
}

/**
 * The upload page's one call: read the file (step 1), then analyse it (steps 2 to 6) unless
 * the photo was too unclear to read. Mirrors the flow in the NF-P2-007 runbook exactly.
 *
 * `contractId` is set as soon as the upload returns, before the analysis finishes, so the
 * page can follow the analysis live (`useContractProgress`, NF-P2-010).
 */
export function useUploadAndAnalyzeContract() {
  const [contractId, setContractId] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: async ({
      file,
      choices,
    }: UploadAndAnalyzeArgs): Promise<UploadAndAnalyzeResult> => {
      setContractId(null);
      const uploaded = await uploadContract(file);
      setContractId(uploaded.contract_id);
      if (uploaded.legibility === "poor") {
        return {
          contractId: uploaded.contract_id,
          legibility: uploaded.legibility,
          analysis: null,
        };
      }
      const analysis = await analyzeContract(uploaded.contract_id, choices);
      return { contractId: uploaded.contract_id, legibility: uploaded.legibility, analysis };
    },
    // The upload page shows the error inline next to its submit button.
    meta: { inlineError: true },
  });
  return { ...mutation, contractId };
}

export interface RetryAnalysisArgs {
  contractId: string;
  choices: AnalyzeRequest;
}

/**
 * Run the analysis again on an uploaded contract, without uploading again. What the backend
 * already stored is reused (its cache), so a retry after a busy AI service is cheap.
 */
export function useRetryAnalysis() {
  return useMutation({
    mutationFn: ({ contractId, choices }: RetryAnalysisArgs) =>
      analyzeContract(contractId, choices),
    // The progress card shows the failure itself.
    meta: { inlineError: true },
  });
}

/**
 * The live contract document while it is analysed: `status`, `step`, `error` and, once
 * finished, the scores. Null before it exists, or when `contractId` is null (not listening).
 */
export function useContractProgress(contractId: string | null): ContractProgressDoc | null {
  const { user } = useAuth();
  const uid = user?.uid;
  // Kept with the contract it belongs to: a document of the previous contract is never shown
  // for the next one, without clearing state inside the effect.
  const [latest, setLatest] = useState<{ key: string; doc: ContractProgressDoc | null } | null>(
    null
  );
  const key = contractId && uid ? `${uid}/${contractId}` : null;

  useEffect(() => {
    if (!contractId || !uid) {
      return;
    }
    return watchContractProgress(uid, contractId, (doc) =>
      setLatest({ key: `${uid}/${contractId}`, doc })
    );
  }, [contractId, uid]);

  return key !== null && latest?.key === key ? latest.doc : null;
}

function reportKey(
  uid: string | undefined,
  contractId: string | null,
  language: LanguageCode | null
) {
  return ["contractReport", uid, contractId, language] as const;
}

export interface ReportQueryArgs {
  uid: string | undefined;
  contractId: string | null;
  language: LanguageCode | null;
  /** `report_languages` of the analysis: the languages already stored under `reports/`. */
  storedLanguages: readonly LanguageCode[];
}

/**
 * The backend already tries Gemini three times, so a failed backend answer is never repeated
 * by itself: the worker decides on another try. A failed Firestore read is retried once.
 */
export function retryReportLoad(failureCount: number, error: Error): boolean {
  return !(error instanceof ApiError) && failureCount < 1 && isRetryable(error);
}

/**
 * While a new language loads, the previous language of the same contract stays on screen
 * (`isPlaceholderData`), so the score does not vanish for the seconds a translation takes.
 * Only within one contract: another contract's report must never stand in for this one.
 */
export function reportPlaceholder(
  contractId: string | null,
  previous: ContractReport | null | undefined,
  previousQuery: { queryKey: readonly unknown[] } | undefined
): ContractReport | null | undefined {
  return previousQuery?.queryKey[2] === contractId ? previous : undefined;
}

/**
 * How one language of the report is loaded (NF-P2-011, NF-P2-012). A stored language is read
 * straight from Firestore. Any other is asked of the backend, which translates it once and
 * stores it, so the next visit finds it stored. Each language has its own cache key: going
 * back to one already seen makes no request.
 */
export function reportQueryOptions({
  uid,
  contractId,
  language,
  storedLanguages,
}: ReportQueryArgs) {
  const stored = language !== null && storedLanguages.includes(language);
  return queryOptions({
    queryKey: reportKey(uid, contractId, language),
    queryFn: () =>
      stored
        ? getContractReport(uid ?? "", contractId ?? "", language as LanguageCode)
        : switchReportLanguage(contractId ?? "", language as LanguageCode),
    enabled: uid !== undefined && contractId !== null && language !== null,
    // Reports are written once per language and never edited in place.
    staleTime: Infinity,
    placeholderData: (
      previous: ContractReport | null | undefined,
      previousQuery?: { queryKey: readonly unknown[] }
    ) => reportPlaceholder(contractId, previous, previousQuery),
    retry: retryReportLoad,
  });
}

/**
 * The finished report in one language, for the report card and its language switcher.
 * Enabled once analysis has produced a `contractId` and a language.
 */
export function useContractReport(
  contractId: string | null,
  language: LanguageCode | null,
  storedLanguages: readonly LanguageCode[] = []
) {
  const { user } = useAuth();
  return useQuery(reportQueryOptions({ uid: user?.uid, contractId, language, storedLanguages }));
}

/** The worker's most recent contracts, newest first, for the home dashboard (NF-P3-019). */
export function useRecentContracts(max: number) {
  const { user } = useAuth();
  const uid = user?.uid;
  return useQuery({
    queryKey: ["recentContracts", uid, max] as const,
    queryFn: () => listRecentContracts(uid ?? "", max),
    enabled: uid !== undefined,
    staleTime: 30_000,
  });
}

/** The employer and agency a contract names, for the Radar warnings (NF-P3-023). */
export function useContractParties(contractId: string | null) {
  const { user } = useAuth();
  const uid = user?.uid;
  return useQuery({
    queryKey: ["contractParties", uid, contractId] as const,
    queryFn: () => getContractParties(uid ?? "", contractId ?? ""),
    enabled: Boolean(uid && contractId),
  });
}

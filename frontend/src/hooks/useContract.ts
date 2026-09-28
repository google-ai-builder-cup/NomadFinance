import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useAuth } from "@/hooks/useAuth";
import { analyzeContract, uploadContract, watchContractProgress } from "@/services/contractService";
import type { AnalyzeRequest, ContractAnalysis, Legibility } from "@/types/contract";
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

import { useMutation } from "@tanstack/react-query";

import { analyzeContract, uploadContract } from "@/services/contractService";
import type { AnalyzeRequest, ContractAnalysis, Legibility } from "@/types/contract";

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
 */
export function useUploadAndAnalyzeContract() {
  return useMutation({
    mutationFn: async ({
      file,
      choices,
    }: UploadAndAnalyzeArgs): Promise<UploadAndAnalyzeResult> => {
      const uploaded = await uploadContract(file);
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
}

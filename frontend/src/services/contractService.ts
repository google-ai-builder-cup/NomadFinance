import { doc, onSnapshot, type Unsubscribe } from "firebase/firestore";

import { db } from "@/lib/firebase";
import { apiRequest } from "@/services/apiClient";
import type { AnalyzeRequest, ContractAnalysis, ContractUploadResponse } from "@/types/contract";
import type { ContractProgressDoc } from "@/utils/pipelineProgress";

/** Step 1: read and store the file (`POST /api/v1/contracts`). Usually 3 to 40 s. */
export async function uploadContract(file: File): Promise<ContractUploadResponse> {
  const body = new FormData();
  body.append("file", file);
  const response = await apiRequest("/api/v1/contracts", { method: "POST", body });
  return (await response.json()) as ContractUploadResponse;
}

/**
 * Steps 2 to 6: check the contract against its host country's labor law and store the
 * reports (`POST /api/v1/contracts/{id}/analyze`). Usually 30 s to 2 minutes.
 */
export async function analyzeContract(
  contractId: string,
  choices: AnalyzeRequest
): Promise<ContractAnalysis> {
  const response = await apiRequest(`/api/v1/contracts/${contractId}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(choices),
  });
  return (await response.json()) as ContractAnalysis;
}

/**
 * Follow `users/{uid}/contracts/{contractId}` live while it is analysed (NF-P2-010). The
 * backend updates `status` and `step` as each step starts; the owner may read the document.
 *
 * Returns:
 *   The function that stops listening.
 */
export function watchContractProgress(
  uid: string,
  contractId: string,
  onChange: (progress: ContractProgressDoc | null) => void
): Unsubscribe {
  return onSnapshot(
    doc(db, "users", uid, "contracts", contractId),
    (snapshot) => onChange(snapshot.exists() ? (snapshot.data() as ContractProgressDoc) : null),
    // Offline or a lost listener: keep the last progress shown; the analyze request still
    // decides the outcome.
    () => undefined
  );
}

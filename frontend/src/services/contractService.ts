import {
  collection,
  doc,
  getDoc,
  getDocs,
  limit,
  onSnapshot,
  orderBy,
  query,
  type Unsubscribe,
} from "firebase/firestore";

import { db } from "@/lib/firebase";
import { apiRequest } from "@/services/apiClient";
import type {
  AnalyzeRequest,
  ContractAnalysis,
  ContractParties,
  ContractReport,
  ContractSummary,
  ContractUploadResponse,
} from "@/types/contract";
import type { LanguageCode } from "@/types/enums";
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

/**
 * The finished report in one language (NF-P2-011): summary and clause-by-clause detail. Read
 * straight from Firestore, not the API: the analyze step (NF-P2-007) already stores
 * `reports/{language}` before it answers, and the owner may read it (firestore.rules). Null
 * when the report has not been written yet.
 */
export async function getContractReport(
  uid: string,
  contractId: string,
  language: LanguageCode
): Promise<ContractReport | null> {
  const snapshot = await getDoc(
    doc(db, "users", uid, "contracts", contractId, "reports", language)
  );
  return snapshot.exists() ? (snapshot.data() as ContractReport) : null;
}

/**
 * The report in another language (`POST /api/v1/contracts/{id}/reports/{language}`,
 * NF-P2-012). The backend returns the stored report at once, or translates the English one
 * (a few seconds), stores it under `reports/{language}` and returns it.
 */
export async function switchReportLanguage(
  contractId: string,
  language: LanguageCode
): Promise<ContractReport> {
  const response = await apiRequest(`/api/v1/contracts/${contractId}/reports/${language}`, {
    method: "POST",
  });
  return (await response.json()) as ContractReport;
}

/**
 * The worker's most recent contracts, newest first, for the home dashboard's recent-contracts
 * widget (NF-P3-019). Light fields only (never a `reports/{language}` document) — straight
 * from Firestore, same access as `getContractReport`.
 */
export async function listRecentContracts(uid: string, max: number): Promise<ContractSummary[]> {
  const snapshot = await getDocs(
    query(collection(db, "users", uid, "contracts"), orderBy("created_at", "desc"), limit(max))
  );
  return snapshot.docs.map(
    (document) => ({ id: document.id, ...document.data() }) as ContractSummary
  );
}

function nameOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value.trim() : null;
}

/**
 * The employer and agency the contract names (`extracted` on the contract document, written
 * by the detect step), for the Radar warnings on the report card (NF-P3-023). Read from
 * Firestore like the progress and the report: the owner may read it. Both null when the
 * document or the field is missing.
 */
export async function getContractParties(
  uid: string,
  contractId: string
): Promise<ContractParties> {
  const snapshot = await getDoc(doc(db, "users", uid, "contracts", contractId));
  const extracted = (snapshot.data()?.extracted ?? {}) as Record<string, unknown>;
  return {
    employer_name: nameOrNull(extracted.employer_name),
    agency_name: nameOrNull(extracted.agency_name),
  };
}

/** A stored contract, enough to reopen its report: what the pipeline wrote on the document. */
export type StoredContract = ContractProgressDoc & ContractSummary;

/**
 * One of the worker's contracts (`users/{uid}/contracts/{id}`), or null if it does not exist.
 * For the contract history (reopening a past report); the owner may read it.
 */
export async function getContract(uid: string, contractId: string): Promise<StoredContract | null> {
  const snapshot = await getDoc(doc(db, "users", uid, "contracts", contractId));
  return snapshot.exists() ? ({ id: snapshot.id, ...snapshot.data() } as StoredContract) : null;
}

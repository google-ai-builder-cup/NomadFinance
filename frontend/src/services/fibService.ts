import { collection, doc, getDoc, getDocs, query, where } from "firebase/firestore";

import { db } from "@/lib/firebase";
import { apiRequest } from "@/services/apiClient";
import type {
  BillEntry,
  BillLogRequest,
  BillLogResponse,
  BillScanResponse,
  ExportReportRequest,
  ExportReportResponse,
  FinancialProfile,
  IncomeEntry,
  IncomeLogRequest,
  IncomeLogResponse,
  SavingsEntry,
  SavingsLogRequest,
  SavingsLogResponse,
} from "@/types/fib";

/** Store one manual income entry (`POST /api/v1/fib/income`, NF-P3-010). No AI call. */
export async function logIncome(body: IncomeLogRequest): Promise<IncomeLogResponse> {
  const response = await apiRequest("/api/v1/fib/income", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return (await response.json()) as IncomeLogResponse;
}

/** Store one manual bill entry (`POST /api/v1/fib/bill`, NF-P3-010). No AI call. */
export async function logBill(body: BillLogRequest): Promise<BillLogResponse> {
  const response = await apiRequest("/api/v1/fib/bill", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return (await response.json()) as BillLogResponse;
}

/**
 * Read a bill photo or PDF with Gemini Vision and store it in one call
 * (`POST /api/v1/fib/bill/scan`, NF-P3-011). Usually a few seconds.
 */
export async function scanBill(file: File): Promise<BillScanResponse> {
  const body = new FormData();
  body.append("file", file);
  const response = await apiRequest("/api/v1/fib/bill/scan", { method: "POST", body });
  return (await response.json()) as BillScanResponse;
}

/** Store one savings entry (`POST /api/v1/fib/savings`, NF-P3-010). No AI call. */
export async function logSavings(body: SavingsLogRequest): Promise<SavingsLogResponse> {
  const response = await apiRequest("/api/v1/fib/savings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return (await response.json()) as SavingsLogResponse;
}

/**
 * `users/{uid}/financial_profile/current` (NF-P3-013's weekly recompute), straight from
 * Firestore: the owner may read it (firestore.rules) and the backend writes it, not this app.
 * Null when the cron has never found this worker enough activity to score (fib.md: it writes
 * nothing at all for a worker with no scoreable entries, not a zeroed document).
 */
export async function getFinancialProfile(uid: string): Promise<FinancialProfile | null> {
  const snapshot = await getDoc(doc(db, "users", uid, "financial_profile", "current"));
  return snapshot.exists() ? (snapshot.data() as FinancialProfile) : null;
}

async function listEntries<T>(
  uid: string,
  kind: "income" | "bills" | "savings",
  sinceIsoDate: string
): Promise<T[]> {
  const snapshot = await getDocs(
    query(collection(db, "users", uid, kind), where("entry_date", ">=", sinceIsoDate))
  );
  return snapshot.docs.map((document) => ({ id: document.id, ...document.data() }) as T);
}

/** Income entries on or after `sinceIsoDate` (`YYYY-MM-DD`), for the timeline dashboard
 * (NF-P3-017). Straight from Firestore, same access as `getFinancialProfile`. */
export function listIncomeEntries(uid: string, sinceIsoDate: string): Promise<IncomeEntry[]> {
  return listEntries<IncomeEntry>(uid, "income", sinceIsoDate);
}

/** Bill entries on or after `sinceIsoDate`, for the timeline dashboard. */
export function listBillEntries(uid: string, sinceIsoDate: string): Promise<BillEntry[]> {
  return listEntries<BillEntry>(uid, "bills", sinceIsoDate);
}

/** Savings entries on or after `sinceIsoDate`, for the timeline dashboard. */
export function listSavingsEntries(uid: string, sinceIsoDate: string): Promise<SavingsEntry[]> {
  return listEntries<SavingsEntry>(uid, "savings", sinceIsoDate);
}

/**
 * Render a fresh PDF of the current Financial Identity profile and get a signed link to it
 * (`POST /api/v1/fib/report/export`, NF-P3-014). Replaces any previous export. 404 when there
 * is no profile yet.
 */
export async function exportReport(body: ExportReportRequest): Promise<ExportReportResponse> {
  const response = await apiRequest("/api/v1/fib/report/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return (await response.json()) as ExportReportResponse;
}

/**
 * A fresh signed link to the worker's last exported PDF, without rendering it again
 * (`GET /api/v1/fib/report/export`). 404 when nothing has ever been exported.
 */
export async function getLatestReport(): Promise<ExportReportResponse> {
  const response = await apiRequest("/api/v1/fib/report/export");
  return (await response.json()) as ExportReportResponse;
}

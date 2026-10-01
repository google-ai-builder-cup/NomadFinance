import { apiRequest } from "@/services/apiClient";
import type {
  BillLogRequest,
  BillLogResponse,
  BillScanResponse,
  IncomeLogRequest,
  IncomeLogResponse,
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

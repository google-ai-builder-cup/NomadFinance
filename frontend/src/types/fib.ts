import type { Timestamp } from "firebase/firestore";

// Mirrors backend/app/schemas/fib.py exactly: field names and literals here must match the
// Pydantic models wire-for-wire.

export const INCOME_CATEGORIES = ["salary", "overtime", "bonus", "other_income"] as const;
export type IncomeCategory = (typeof INCOME_CATEGORIES)[number];

export const BILL_CATEGORIES = [
  "rent",
  "utilities",
  "phone_internet",
  "transport",
  "food",
  "medical",
  "other_expense",
] as const;
export type BillCategory = (typeof BILL_CATEGORIES)[number];

export const SAVINGS_DIRECTIONS = ["deposit", "withdrawal"] as const;
export type SavingsDirection = (typeof SAVINGS_DIRECTIONS)[number];

export const ACCOUNT_TYPES = ["cash", "bank", "mobile_wallet", "other"] as const;
export type AccountType = (typeof ACCOUNT_TYPES)[number];

export type CategorySource = "user" | "model";

export const MAX_NOTES_CHARS = 500;
export const MAX_VENDOR_CHARS = 200;
export const MAX_EMPLOYER_CHARS = 200;

/** Body of `POST /api/v1/fib/income`. */
export interface IncomeLogRequest {
  entry_date?: string | null;
  amount: number;
  currency: string;
  category: IncomeCategory;
  employer_name?: string | null;
  notes?: string | null;
}

/** Response of `POST /api/v1/fib/income`. */
export interface IncomeLogResponse {
  entry_id: string;
  entry_date: string;
  amount: number;
  currency: string;
  category: IncomeCategory;
  category_source: CategorySource;
  employer_name: string | null;
  verified: boolean;
  notes: string | null;
  created_at: string;
}

/** Body of `POST /api/v1/fib/bill`. Manual entry; a photo goes through `scanBill` instead. */
export interface BillLogRequest {
  entry_date?: string | null;
  amount: number;
  currency: string;
  vendor?: string | null;
  bill_date?: string | null;
  paid: boolean;
  category?: BillCategory | null;
  notes?: string | null;
}

/** Response of `POST /api/v1/fib/bill` and `POST /api/v1/fib/bill/scan`. */
export interface BillLogResponse {
  entry_id: string;
  entry_date: string;
  amount: number;
  currency: string;
  vendor: string | null;
  bill_date: string | null;
  paid: boolean;
  category: BillCategory | null;
  category_source: CategorySource | null;
  notes: string | null;
  created_at: string;
}

/** Response of `POST /api/v1/fib/bill/scan`: the entry Gemini Vision read and stored. */
export interface BillScanResponse extends BillLogResponse {
  image_path: string | null;
  confidence: number;
  paid_assumed: boolean;
}

/** Body of `POST /api/v1/fib/savings`. */
export interface SavingsLogRequest {
  entry_date?: string | null;
  amount: number;
  currency: string;
  direction: SavingsDirection;
  account_type?: AccountType | null;
  notes?: string | null;
}

/** Response of `POST /api/v1/fib/savings`. */
export interface SavingsLogResponse {
  entry_id: string;
  entry_date: string;
  amount: number;
  currency: string;
  direction: SavingsDirection;
  account_type: AccountType | null;
  notes: string | null;
  created_at: string;
}

// --- Read straight from Firestore (fib.md: "the owner reads all of these; only the backend
// writes them") for the dashboard, NF-P3-017. Shapes match what `FibRepository.save_entry`
// actually stores, not the log endpoints' JSON response: the id is the document id, not a
// field, and timestamps are Firestore `Timestamp`, not ISO strings.

export type EntrySource = "manual" | "remittance_log" | "bill_ocr" | "contract";

export interface IncomeEntry {
  id: string;
  entry_date: string;
  amount: number;
  currency: string;
  category: IncomeCategory;
  category_source: CategorySource;
  employer_name?: string;
  verified: boolean;
  source: EntrySource;
  created_at: Timestamp;
}

export interface BillEntry {
  id: string;
  entry_date: string;
  amount: number;
  currency: string;
  vendor?: string;
  bill_date?: string;
  paid: boolean;
  category?: BillCategory;
  category_source?: CategorySource;
  /** Set when the model categorized it (`/fib/categorize`); absent for a bill photo's guess. */
  category_confidence?: number | null;
  source: EntrySource;
  created_at: Timestamp;
}

export interface SavingsEntry {
  id: string;
  entry_date: string;
  amount: number;
  currency: string;
  direction: SavingsDirection;
  account_type?: AccountType;
  source: EntrySource;
  created_at: Timestamp;
}

export const METRIC_KEYS = [
  "income_stability",
  "savings_rate",
  "remittance_consistency",
  "bill_payment_reliability",
] as const;
export type MetricKey = (typeof METRIC_KEYS)[number];

/** One scored metric of `financial_profile/current`. `detail` varies by metric (see
 * `backend/app/services/fib/profile_metrics.py`); `score` is `null`, never 0, when there is
 * no data for it yet. */
export interface MetricResult {
  score: number | null;
  detail: Record<string, unknown>;
}

export interface VerifiedEmployment {
  employer_name: string;
  salary_amount: number;
  salary_currency: string;
  contract_ref: string;
}

/** `users/{uid}/financial_profile/current` (NF-P3-013's weekly recompute). Does not exist at
 * all for a worker with no scoreable activity in the last 12 months — the cron writes nothing,
 * rather than a zeroed-out document. */
export interface FinancialProfile {
  reporting_currency: string;
  period_start: string;
  period_end: string;
  months_of_data: number;
  entry_counts: Record<"income" | "transfers" | "bills" | "savings", number>;
  metrics: Record<MetricKey, MetricResult>;
  overall_score: number;
  narrative: { language: string; text: string; model: string };
  verified_employment?: VerifiedEmployment[];
  computed_at: Timestamp;
}

export const MAX_HOLDER_NAME_CHARS = 100;

/** Body of `POST /api/v1/fib/report/export`. */
export interface ExportReportRequest {
  holder_name?: string | null;
}

/** Response of both `POST` and `GET /api/v1/fib/report/export`: a link to the exported PDF.
 * `download_url` always sends `Content-Disposition: attachment` (NF-P3-014) — it downloads,
 * it does not render inline, so the frontend's own "preview" is built from `FinancialProfile`
 * data instead of this PDF's bytes. */
export interface ExportReportResponse {
  download_url: string;
  expires_at: string;
  created_at: string;
  language: string;
  filename: string;
}

/** One entry that `POST /api/v1/fib/categorize` gave a category. */
export interface CategorizedEntry {
  entry_id: string;
  entry_type: "income" | "bill";
  category: IncomeCategory | BillCategory;
  confidence: number;
}

/** Response of `POST /api/v1/fib/categorize`. */
export interface FibCategorizeResponse {
  categorized: CategorizedEntry[];
  /** Gemini gave no usable category; still pending, tried again on the next call. */
  skipped: number;
  /** Left for a later call because of the per-call limit. */
  remaining: number;
}

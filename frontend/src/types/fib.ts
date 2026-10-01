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

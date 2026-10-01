import type { CorridorId, LanguageCode } from "@/types/enums";

/** Body of `POST /api/v1/remittance/compare`. `amount` is in the corridor's sending currency. */
export interface RemittanceCompareRequest {
  corridor_id: CorridorId;
  amount: number;
}

/** The mid-market rate every amount is worked out with. */
export interface RateInfo {
  /** Currency pair, e.g. `SGD_PHP`. */
  pair: string;
  /** Units of the receiving currency for 1 unit sent. */
  rate: number;
  /** `survey`: no live rate was cached, so the survey's median rate was used. */
  source: "live" | "survey";
  provider: string | null;
  rate_date: string | null;
  fetched_at: string | null;
  /** Older than 6 hours, or from the survey: tell the worker it may be out of date. */
  stale: boolean;
}

/** Where the prices come from. `attribution` must be on screen wherever they are (World Bank). */
export interface SurveyInfo {
  /** Survey quarter, e.g. `2025_1Q`. */
  period: string;
  surveyed_from: string;
  surveyed_to: string;
  source_name: string;
  source_url: string;
  attribution: string;
}

/** One surveyed service, worked out for the requested amount. Key rows by `rpw_id`. */
export interface ProviderResult {
  rpw_id: number;
  firm: string;
  firm_type: string;
  payment_instrument: string;
  access_point: string;
  pickup_method: string;
  speed: string;
  /** 0 fastest to 5; sort the speed column by this, not by `speed`. */
  speed_order: number;
  network_coverage: string | null;
  note: string | null;
  payout_currency: string;
  /** False when the receiver is paid in another currency (USD): listed last, not ranked. */
  comparable: boolean;
  /** 1 = the recipient receives most; null when not comparable. */
  rank: number | null;
  /** The amount is outside the two surveyed amounts: the nearest survey point's prices. */
  estimated: boolean;
  fee: number;
  fx_margin_pct: number;
  rate_cost: number;
  total_cost: number;
  total_cost_pct: number;
  recipient_receives: number | null;
  lost_to_costs: number | null;
  less_than_best: number | null;
  /**
   * Workers reported it on the Exploitation Radar. It keeps its rank; advice passes over it.
   * Optional: a response from a backend older than the flag simply has none.
   */
  flagged?: boolean;
  flag_report_count?: number | null;
}

export interface ComparisonSummary {
  comparable_count: number;
  best_rpw_id: number;
  best_firm: string;
  best_recipient_receives: number;
  worst_rpw_id: number;
  worst_firm: string;
  worst_recipient_receives: number;
  /** Best minus worst, in the receiving currency. */
  extra_vs_worst: number;
  /** What the amount is worth with no costs at all. */
  mid_market_receives: number;
  median_total_cost_pct: number;
}

/** Response of `POST /api/v1/remittance/compare` (NF-P2-014). */
export interface RemittanceComparison {
  corridor_id: CorridorId;
  send_amount: number;
  send_currency: string;
  receive_currency: string;
  rate: RateInfo;
  survey: SurveyInfo;
  /** Ranked services first, then those that cannot be compared. */
  providers: ProviderResult[];
  summary: ComparisonSummary;
}

/** Periods `GET /remittance/trends` offers, in days. Matches the backend's `TrendDays`. */
export const TREND_DAYS = [30, 90, 180, 365] as const;
export type TrendDays = (typeof TREND_DAYS)[number];

export type Weekday = "monday" | "tuesday" | "wednesday" | "thursday" | "friday";

export interface TrendPoint {
  date: string;
  rate: number;
}

export interface TrendSummary {
  first: TrendPoint;
  latest: TrendPoint;
  /** Latest against first, in percent; above 0 means the recipient now gets more. */
  change_pct: number;
  low: TrendPoint;
  high: TrendPoint;
  average: number;
}

/** How one weekday compares with the rest of its own week, over the analysed weeks. */
export interface WeekdayStat {
  weekday: Weekday;
  advantage_pct: number;
  weeks: number;
  beat_share: number;
}

/** Response of `GET /remittance/trends` (NF-P2-015). */
export interface RemittanceTrends {
  corridor_id: CorridorId;
  pair: string;
  base_currency: string;
  quote_currency: string;
  days: TrendDays;
  /** One per market day in the period, oldest first. */
  points: TrendPoint[];
  summary: TrendSummary | null;
  /** Newest day stored, even if outside the period (a stalled cron shows here). */
  last_date: string;
  best_day: WeekdayStat | null;
  best_day_reason: "not_enough_history" | "no_clear_pattern" | null;
  weeks_analysed: number;
  /** All five weekdays, Monday first; empty when there is not enough history. */
  weekdays: WeekdayStat[];
  providers: string[];
}

// Free text on a logged transfer, matching the backend's MAX_NOTES_CHARS (remittance_log.py).
export const MAX_LOG_NOTES_CHARS = 500;

/**
 * Body of `POST /api/v1/remittance/log` (NF-P2-017). `comparison` is sent back exactly as
 * `/remittance/compare` returned it: every stored amount is read from its `rpw_id` provider
 * there, never typed freely by the client.
 */
export interface TransferLogRequest {
  comparison: RemittanceComparison;
  rpw_id: number;
  entry_date?: string | null;
  notes?: string | null;
}

/** Response of `POST /api/v1/remittance/log`: the stored transfer. */
export interface TransferLogResponse {
  transfer_id: string;
  corridor_id: CorridorId;
  provider_rpw_id: number;
  provider_name: string;
  send_amount: number;
  send_currency: string;
  receive_amount: number;
  receive_currency: string;
  fee: number;
  mid_market_rate: number;
  cost_pct: number;
  entry_date: string;
  notes: string | null;
}

// Full months `GET /remittance/savings` accepts, matching the backend's MIN_MONTHS/MAX_MONTHS.
export const MIN_SAVINGS_MONTHS = 1;
export const MAX_SAVINGS_MONTHS = 12;

/** What sending `amount` would have cost in one full calendar month, best vs worst service. */
export interface MonthlySavings {
  /** Calendar month, YYYY-MM. */
  month: string;
  average_rate: number;
  best_receives: number;
  worst_receives: number;
  /** best_receives minus worst_receives. */
  savings: number;
}

/** Response of `GET /remittance/savings` (NF-P2-022): the "you would have saved $X" figure. */
export interface RemittanceSavings {
  corridor_id: CorridorId;
  send_amount: number;
  send_currency: string;
  receive_currency: string;
  months_requested: number;
  /** Less than months_requested when the history does not go back that far. */
  months_used: number;
  best_rpw_id: number;
  best_firm: string;
  worst_rpw_id: number;
  worst_firm: string;
  total_best_receives: number;
  total_worst_receives: number;
  /** What sending with best_firm instead of worst_firm would have been worth over the period. */
  total_savings: number;
  /** Oldest first. */
  months: MonthlySavings[];
  survey: SurveyInfo;
}

/** Body of `POST /api/v1/remittance/recommend` (NF-P2-016). */
export interface RemittanceRecommendRequest {
  /** The unmodified response of `/remittance/compare`. */
  comparison: RemittanceComparison;
  /** The response of `/remittance/trends`, for the timing tip. */
  trend?: RemittanceTrends | null;
  target_language: LanguageCode;
}

/**
 * Response of `POST /api/v1/remittance/recommend`. `recommended_firm` is the best-ranked
 * provider workers have not flagged, chosen by the backend; the texts are in
 * `target_language`.
 */
export interface RemittanceRecommendation {
  corridor_id: CorridorId;
  target_language: LanguageCode;
  recommended_rpw_id: number;
  recommended_firm: string;
  headline: string;
  explanation: string;
  timing_tip: string | null;
}

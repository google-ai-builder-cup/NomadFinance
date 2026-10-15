import type { LanguageCode } from "@/types/enums";

// The Financial Coach's answers, as docs/api/v2-coach.md defines them. Only what the chat reads is
// typed; the backend may add fields without a break (clients ignore what they do not know).

export const COACH_STAGES = [
  "intro",
  "income",
  "obligations",
  "debt",
  "savings",
  "review",
  "plan",
] as const;
export type CoachStage = (typeof COACH_STAGES)[number];

export const COACH_SLOTS = [
  "destination_country",
  "job_type",
  "departure_date",
  "monthly_salary",
  "dependents",
  "remittance_target",
  "recruitment_fee_paid",
  "debt_outstanding",
  "debt_interest",
  "savings",
  "bank_or_wallet",
] as const;
export type CoachSlot = (typeof COACH_SLOTS)[number];

export interface CoachMessage {
  id: string;
  role: "user" | "coach";
  text: string;
  language: string;
  at: string;
}

/** `contract_prefill`, `profile_prefill` and `identity_prefill` are answers the worker agreed to
 * from what the Coach already knew (NF-FC-023); `user` is one they gave. */
export type CoachSlotSource = "user" | "contract_prefill" | "profile_prefill" | "identity_prefill";

export interface CoachSlotAnswer {
  /** Shaped as the slot's field of `CoachProfile`: a string, a number or an object. */
  value: unknown;
  confirmed: boolean;
  source: CoachSlotSource;
}

/** Where an offered answer was worked out from (`docs/api/v2-coach.md`, "What the Coach already
 * knows"). */
export type KnownSource = "profile" | "contract" | "income" | "savings" | "transfers";

/** One answer the Coach could fill in. It is not an answer until the worker keeps it. */
export interface CoachKnownItem {
  slot: CoachSlot;
  value: unknown;
  source: KnownSource;
  /** The date of the newest entry the figure comes from; null for the profile and the contract. */
  as_of: string | null;
}

export interface CoachKnown {
  /** In the order of the interview. */
  items: CoachKnownItem[];
}

export const SCORE_FACTORS = [
  "debt_to_income",
  "emergency_buffer",
  "remittance_ratio",
  "recruitment_fee_vs_cap",
  "banked_status",
] as const;
export type ScoreFactorId = (typeof SCORE_FACTORS)[number];

export interface ScoreFactor {
  id: ScoreFactorId;
  /** The measured figure (a ratio, or months); null when it could not be measured. */
  value: number | null;
  /** This factor's points, 0 to 100. */
  score: number;
  weight: number;
}

/** The preparedness score. `band` is an open id: a band the
 * screen does not know is shown with a neutral label. */
export interface CoachScore {
  total: number;
  band: string;
  factors: ScoreFactor[];
  rubric_version: number;
}

/** A figure of the plan: always an amount and its money. */
export interface PlanMoney {
  amount: number;
  currency: string;
}
export interface BudgetLine {
  id: string;
  amount: PlanMoney;
}
export interface MonthlyBudget {
  income: PlanMoney;
  costs: BudgetLine[];
  goals: BudgetLine[];
  /** Income minus costs minus goals, exactly; negative is a gap. */
  left_over: PlanMoney;
  setup_costs?: PlanMoney | null;
}
export interface ProviderQuote {
  slug: string;
  name: string;
  fee: PlanMoney;
  /** What arrives at home, in the home currency. */
  receives: PlanMoney;
  fx_rate: number;
  quoted_at: string;
}
export interface RemittancePlan {
  corridor_id: string | null;
  monthly_amount: PlanMoney;
  provider: ProviderQuote | null;
  schedule: { week: number; amount: PlanMoney }[];
}
export interface DebtPlan {
  outstanding: PlanMoney;
  monthly_payment: PlanMoney;
  months_to_clear: number | null;
}
export interface EmergencyFundPlan {
  target: PlanMoney;
  months_of_costs: number;
  monthly_saving: PlanMoney;
  weeks_to_target: number | null;
}
export interface PlanWeek {
  week: number;
  title: string;
  actions: string[];
}
export type WarningSeverity = "info" | "warning" | "urgent";
export interface PlanWarning {
  id: string;
  severity: WarningSeverity;
  text: string;
}
export interface PlanChecklistItem {
  id: string;
  text: string;
}
export interface CoachPlanBody {
  summary: string;
  monthly_budget: MonthlyBudget;
  remittance: RemittancePlan;
  debt: DebtPlan | null;
  emergency_fund: EmergencyFundPlan;
  weeks: PlanWeek[];
  warnings: PlanWarning[];
  checklist: PlanChecklistItem[];
  disclaimer: string;
}

/** `POST /coach/sessions/{id}/plan` and `GET /coach/plans/{id}`: a stored plan in one language
 * (`docs/api/v2-coach.md`). Every sentence is text in `language`; every figure is a `PlanMoney`. */
export interface CoachPlanResponse {
  id: string;
  session_id: string | null;
  language: LanguageCode;
  available_languages: LanguageCode[];
  host_country: string;
  home_country?: string;
  corridor_id?: string;
  departure_date?: string;
  reporting_currency: string;
  slots: Record<string, unknown>;
  rates_as_of: string;
  score: CoachScore;
  plan: CoachPlanBody;
  created_at: string;
}

/** What the score screen reads of a made plan; the plan page reads all of it. */
export type CoachPlanMade = CoachPlanResponse;

/** `GET /coach/overview`: what the dashboard and the Coach page need to offer the right next step. */
export interface CoachOverview {
  session: {
    id: string;
    stage: CoachStage;
    language: LanguageCode;
    turn_count: number;
    last_active: string;
  } | null;
  plan: {
    id: string;
    created_at: string;
    score_total: number;
    band: string;
    departure_date?: string;
  } | null;
}

export interface CoachSession {
  id: string;
  status: "active" | "completed" | "abandoned";
  stage: CoachStage;
  language: LanguageCode;
  slots: Partial<Record<CoachSlot, CoachSlotAnswer>>;
  messages: CoachMessage[];
  /** The slot the coach asks next; null exactly in the `review` and `plan` stages. */
  next_slot: CoachSlot | null;
  turn_count: number;
  /** At `review` and `plan` unless it cannot be worked out right now (a missing rate): `null`. */
  score: CoachScore | null;
  plan_id: string | null;
  /** Only while the worker has not yet answered what the Coach already knows; absent otherwise. */
  known?: CoachKnown;
  created_at: string;
  last_active: string;
}

/** `POST /coach/sessions`: the session, and whether the worker already had one open. */
export type CoachSessionStart = CoachSession & { resumed: boolean };

/** One turn. Without `text` the coach speaks first (the opening, or the question again). */
export interface CoachTurnRequest {
  sessionId: string;
  text?: string;
  language: LanguageCode;
  /** The same key on every retry of one turn, so a turn that finished is replayed, not repeated. */
  idempotencyKey: string;
}

export interface CoachDone {
  messageId: string;
  stage: CoachStage;
  nextSlot: CoachSlot | null;
  turnCount: number;
}

/** What the stream says, in the order it arrives. Everything before `done` is provisional. */
export type CoachStreamEvent =
  | { type: "token"; text: string }
  | { type: "slot_update"; slot: CoachSlot; value: unknown; confirmed: boolean }
  | ({ type: "done" } & CoachDone)
  | { type: "error"; code: string; message: string };

/** Why a turn did not finish. `code` is the backend's, or one of ours for a dropped stream. */
export interface CoachFailure {
  code: string;
  /** HTTP status; 0 for a stream that broke or never reached the backend. */
  status: number;
  retryAfterSeconds?: number;
}

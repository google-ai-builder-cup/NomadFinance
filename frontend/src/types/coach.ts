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

export interface CoachSlotAnswer {
  /** Shaped as the slot's field of `CoachProfile`: a string, a number or an object. */
  value: unknown;
  confirmed: boolean;
  source: "user" | "contract_prefill";
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

/** The preparedness score of `docs/features/coach-scoring.md`. `band` is an open id: a band the
 * screen does not know is shown with a neutral label. */
export interface CoachScore {
  total: number;
  band: string;
  factors: ScoreFactor[];
  rubric_version: number;
}

/** What the screen reads of a made plan (`POST /coach/sessions/{id}/plan`); the plan view of
 * NF-FC-021 reads the rest of it. */
export interface CoachPlanMade {
  id: string;
  language: LanguageCode;
  score: CoachScore;
  plan: { summary: string };
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

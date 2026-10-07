import type { CorridorId, LanguageCode } from "@/types/enums";
import type { Severity } from "@/utils/risk";

// The scam analyzer's answer, as docs/api/v2-scam.md defines it. Only what the screens read is
// typed; the backend may add fields without a break (clients ignore what they do not know).

/** What a worker hands in: a pasted or shared message, or a screenshot. */
export type ScamCheckInput = { kind: "text"; text: string } | { kind: "screenshot"; file: File };

export interface ScamCheckRequest {
  input: ScamCheckInput;
  language: LanguageCode;
  /** Only when the worker's route is one of the six; the backend accepts none. */
  corridorId?: CorridorId;
}

export interface ScamVerdict {
  is_scam: boolean;
  /** Taxonomy id; null exactly when `is_scam` is false. */
  scam_type: string | null;
  tactics: string[];
  risk_level: Severity;
  confidence: number;
  trigger_phrases: string[];
}

export interface ScamIndicator {
  id: string;
  kind: "url" | "phone" | "email" | "handle" | "sender";
  value: string;
  flags: string[];
  imitates?: string;
  seen: { reports: number; incidents: number; last_reported_at: string; flagged: boolean } | null;
}

export type ScamExplainer =
  | {
      kind: "scam";
      language: string;
      why_it_works: { tactic: string; text: string }[];
      scammer_wants: string;
      next_steps: string[];
    }
  | { kind: "benign"; language: string; reassurance: string; tip: string };

/** A known scam or a worker's report that the message resembles. No id and no text: only what
 * the card shows. */
export interface ScamSimilar {
  source: "scam_pattern" | "radar_report";
  /** Taxonomy id, or null for a report that is not about a kind of scam. */
  scam_type: string | null;
  score: number;
}

export interface ScamAnalyzeResponse {
  id: string;
  cached: boolean;
  input_type: "text" | "screenshot";
  language: string;
  message_language: string | null;
  redacted_text: string;
  corridor_id: string | null;
  verdict: ScamVerdict;
  indicators: ScamIndicator[];
  similar: ScamSimilar[];
  explainer: ScamExplainer | null;
  explainer_status: "ready" | "unavailable";
  corridor_report_count: number | null;
  reported: boolean;
  report_id: string | null;
  created_at: string;
  expires_at: string;
}

/** One stored check, as `GET /scam/checks/{id}` returns it: the analyze answer without `cached`.
 * `indicators[].seen` is read live, so it shows today's count. */
export type ScamCheckDetail = Omit<ScamAnalyzeResponse, "cached">;

/** What the result view draws: a fresh check (which may have come from the cache) or a stored one. */
export type ScamResultView = ScamCheckDetail & { cached?: boolean };

/** One row of the history: the verdict's headline and nothing more. */
export interface ScamCheckSummary {
  id: string;
  created_at: string;
  input_type: "text" | "screenshot";
  language: string;
  is_scam: boolean;
  scam_type: string | null;
  risk_level: Severity;
  confidence: number;
  /** The first 140 characters of the redacted message. */
  excerpt: string;
  reported: boolean;
}

export interface ScamCheckList {
  items: ScamCheckSummary[];
  /** Null on the last page. */
  next_cursor: string | null;
}

/** What the confirmation sheet sends: exactly what it showed, nothing else. */
export interface ScamReportRequest {
  /** The contacts the worker left ticked; may be empty. */
  indicator_ids: string[];
  /** The message as the worker edited it, 1 to 1,000 characters. */
  description: string;
}

export interface ScamReportResponse {
  report_id: string;
  /** True when the check had been reported already: the first report comes back, nothing is added. */
  already_reported: boolean;
  /** The Radar profile of this kind of scam: `/radar/entity/{entity_slug}`. */
  entity_slug: string;
  entity_name: string;
  created_at: string;
}

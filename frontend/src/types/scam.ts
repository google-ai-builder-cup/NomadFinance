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

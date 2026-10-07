import type { Timestamp } from "firebase/firestore";

import type { CorridorId, HostCountry, LanguageCode } from "@/types/enums";
import type { ScamIndicator } from "@/types/scam";
import type { Severity } from "@/utils/risk";

/** Same values as backend `RadarEntityType` (docs/data-model/collections/radar.md). */
export const ENTITY_TYPES = ["money_transfer_operator", "recruitment_agency", "employer"] as const;
export type EntityType = (typeof ENTITY_TYPES)[number];

/** The profile of a kind of scam (a Scam Analyzer report, NF-SA-013). It is stored like a business
 * but is not in `ENTITY_TYPES` on purpose: that list is what a worker may choose in the report
 * form, and a worker's own form cannot produce a scam report. */
export type ScamEntityType = "scam_type";

/** Same values as backend `RadarViolationType`. The backend picks it; the form never sends it. */
export type ViolationType =
  | "hidden_fees"
  | "exchange_rate_markup"
  | "illegal_recruitment_fee"
  | "wage_theft"
  | "illegal_deduction"
  | "contract_substitution"
  | "passport_retention"
  | "unlicensed_operator"
  | "scam_message"
  | "other";

/** Body of `POST /api/v1/radar/report`. */
export interface RadarReportRequest {
  entity_type: EntityType;
  entity_name: string;
  corridor_id?: CorridorId;
  host_country?: HostCountry;
  description: string;
  language: LanguageCode;
}

/** Response of `POST /api/v1/radar/report`: the stored report. */
export interface RadarReportResponse {
  report_id: string;
  entity_type: EntityType;
  entity_name: string;
  violation_type: ViolationType;
  corridor_id: CorridorId | null;
  host_country: HostCountry | null;
  description: string;
  /** One neutral English sentence about the report. */
  summary: string;
  created_at: string;
}

/** Response of `POST /api/v1/radar/report/{id}/evidence`. */
export interface RadarEvidenceResponse {
  report_id: string;
  evidence_paths: string[];
}

export type ReportSource = "user" | "contract_signal" | "seed" | "scam_check";

/** The `scam` map of a report made from a Scam Analyzer check (docs/data-model radar.md): what the
 * worker confirmed on the sheet. The contacts are the ones left ticked, without an id or a count. */
export interface RadarScamReport {
  scam_type: string;
  tactics: string[];
  risk_level: Severity;
  confidence: number;
  trigger_phrases: string[];
  /** Every key is optional: an absent key means unknown. */
  details: {
    payment_requested?: string;
    amount_requested?: { amount: number; currency: string };
  };
  indicators: Omit<ScamIndicator, "id" | "seen">[];
  message_language?: string | null;
  input_type: "text" | "screenshot";
}

/** One entry of `GET /api/v1/radar/entities/{slug}/reports` (NF-P3-008). */
export interface RadarReportSummary {
  report_id: string;
  violation_type: ViolationType;
  description: string;
  /** Null for contract_signal/seed reports, which have no free text to summarize. */
  summary: string | null;
  language: LanguageCode;
  corridor_id: CorridorId | null;
  host_country: HostCountry | null;
  source: ReportSource;
  /** Only on a report made from a scam check. */
  scam?: RadarScamReport;
  created_at: string;
}

/** What the form has collected so far. */
export interface ReportDraft {
  entityType: EntityType | null;
  entityName: string;
  corridorId: CorridorId | null;
  hostCountry: HostCountry | null;
  description: string;
  language: LanguageCode | null;
  files: File[];
}

/** `radar_entities/{slug}` as the heatmap reads it (docs/data-model/collections/radar.md). */
export interface RadarEntityProfile {
  slug: string;
  name: string;
  entity_type: EntityType | ScamEntityType;
  /** Other spellings merged into this profile; the way to catch a name the slug misses. */
  aliases?: string[];
  corridors: CorridorId[];
  host_countries: HostCountry[];
  report_count: number;
  incident_count: number;
  violation_counts: Partial<Record<ViolationType, number>>;
  /** Null until the business has enough incidents to be rated. */
  community_rating: number | null;
  risk_level: "low" | "medium" | "high";
  flagged: boolean;
}

/**
 * `radar_alerts/{corridor}/current/{id}` (radar.md): a surge of reports about one business on
 * one route, written by the alert job (NF-P3-004). Language-neutral: the page words it.
 */
export interface RouteAlert {
  id: string;
  corridor_id: CorridorId;
  entity_slug: string;
  entity_name: string;
  violation_type: ViolationType;
  window_days: number;
  report_count: number;
  baseline_count: number;
  severity: "info" | "warning" | "critical";
  status: "active" | "expired";
  created_at: Timestamp;
  expires_at: Timestamp;
}

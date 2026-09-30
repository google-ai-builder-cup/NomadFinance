import type { CorridorId, HostCountry, LanguageCode } from "@/types/enums";

/** Same values as backend `RadarEntityType` (docs/data-model/collections/radar.md). */
export const ENTITY_TYPES = ["money_transfer_operator", "recruitment_agency", "employer"] as const;
export type EntityType = (typeof ENTITY_TYPES)[number];

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

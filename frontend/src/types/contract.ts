import type { HostCountry, JobType, LanguageCode } from "@/types/enums";

export type Legibility = "good" | "partial" | "poor";

export type ClauseRisk = "safe" | "caution" | "danger";

export interface ClauseCounts {
  safe: number;
  caution: number;
  danger: number;
}

/** Response of `POST /api/v1/contracts` (step 1: the file is read and stored). */
export interface ContractUploadResponse {
  contract_id: string;
  status: "uploaded" | "processing" | "completed" | "failed";
  /** True when this file was already uploaded by this worker; nothing was re-read. */
  reused: boolean;
  page_count: number;
  title: string | null;
  /** `poor`: ask for a clearer photo instead of analysing. */
  legibility: Legibility;
}

/** Body of `POST /api/v1/contracts/{id}/analyze`. Each field wins over what is detected. */
export interface AnalyzeRequest {
  host_country?: HostCountry;
  job_type?: JobType;
  report_language?: LanguageCode;
}

/** Response of `POST /api/v1/contracts/{id}/analyze`: where to find the finished report. */
export interface ContractAnalysis {
  contract_id: string;
  status: "uploaded" | "processing" | "completed" | "failed";
  /** True when a stored analysis was still current, so nothing was re-checked. */
  cached: boolean;
  host_country: HostCountry;
  job_type: JobType;
  health_score: number;
  risk_level: ClauseRisk;
  clause_counts: ClauseCounts;
  report_language: LanguageCode;
  /** Alphabetically sorted, not source-language-first (backend D-60). */
  report_languages: LanguageCode[];
  /** The letter failed for a passing reason; analyze again to write only it. */
  complaint_pending: boolean;
}

/** The step on `users/{uid}/contracts/{id}.step` while it is analysed, and in `error.step`. */
export type PipelineStep = "extract" | "detect" | "law" | "compare" | "complaint" | "translate";

/** The worker-facing reasons `POST .../analyze` can stop, from `error.code` on the contract. */
export type PipelineErrorCode =
  | "poor_legibility"
  | "country_unknown"
  | "not_employment_contract"
  | "no_law_data"
  | "no_terms"
  | "gemini_busy"
  | "gemini_unavailable"
  | "gemini_timeout"
  | "gemini_bad_answer"
  | "internal";

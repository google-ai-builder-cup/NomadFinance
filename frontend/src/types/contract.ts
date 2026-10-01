import type { Timestamp } from "firebase/firestore";

import type { HostCountry, JobType, LanguageCode } from "@/types/enums";

export type Legibility = "good" | "partial" | "poor";

export type ClauseRisk = "safe" | "caution" | "danger";

/** The 15 curated labor-law categories (docs/data-model/collections/labor_laws.md) plus other. */
export type ClauseCategory =
  | "minimum_wage"
  | "working_hours"
  | "overtime_pay"
  | "rest_days_and_holidays"
  | "annual_leave"
  | "sick_leave"
  | "salary_payment"
  | "salary_deductions"
  | "termination_notice"
  | "early_termination"
  | "recruitment_fees"
  | "passport_retention"
  | "accommodation"
  | "insurance_and_injury"
  | "social_security"
  | "other";

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
  /** Why it is pending; absent from a backend older than 2026-10-01. */
  complaint_pending_reason?: LetterPendingReason | null;
}

/**
 * Why a complaint letter is still pending (backend `LetterPendingReason`): the AI service's
 * daily quota is used up (tomorrow), it is busy (minutes), it gave an unusable answer, or the
 * country's template is not loaded.
 */
export type LetterPendingReason = "ai_daily_limit" | "ai_busy" | "ai_failed" | "no_template";

/**
 * `users/{uid}/contracts/{contractId}`'s light fields, read straight from Firestore for the
 * home dashboard's recent-contracts widget (NF-P3-019) — never the heavy per-language report.
 * `health_score`/`risk_level` are present once `status` is `completed`, absent otherwise
 * (contracts.md: "when completed").
 */
export interface ContractSummary {
  id: string;
  status: "uploaded" | "processing" | "completed" | "failed";
  title: string | null;
  health_score?: number;
  risk_level?: ClauseRisk;
  created_at: Timestamp;
}

/** One clause of a stored report (`reports/{lang}.clauses`, contracts.md). */
export interface ReportClause {
  index: number;
  number: string | null;
  page: number;
  /** The clause's exact words, in the report's language. */
  text: string;
  category: ClauseCategory;
  risk: ClauseRisk;
  law_reference: string | null;
  explanation: string;
  recommendation: string | null;
  block_ids: number[];
}

export interface ComplaintChannel {
  kind: "web" | "email" | "phone" | "post";
  value: string;
  note: string | null;
}

/** The language a labor authority works in (`complaint_templates/{country}`, contracts.md). */
export type LetterLanguage = "en" | "ko" | "ms" | "ja";

/** The complaint letter stored on a report when a term broke the law (NF-P2-006). */
export interface ContractComplaint {
  template_type: string;
  authority_name: string;
  authority_url: string | null;
  channels: ComplaintChannel[];
  letter_language: LetterLanguage;
  letter_text: string;
  worker_language: LanguageCode;
  /** Same letter in `worker_language`, to read; null when that is the letter language. */
  worker_copy: string | null;
  violation_count: number;
}

/** A stored `users/{uid}/contracts/{id}/reports/{language}` document (contracts.md). */
export interface ContractReport {
  language: LanguageCode;
  /** True for `reports/en`, the report the analysis wrote; false for a translation. */
  is_source: boolean;
  full_text: string;
  summary: string;
  clauses: ReportClause[];
  complaint: ContractComplaint | null;
  content_hash: string;
  law_version: number;
  prompt_versions: Record<string, number>;
  models: Record<string, string>;
  schema_version: number;
}

/**
 * Who the contract names, from `users/{uid}/contracts/{id}.extracted` (contracts.md): what
 * Radar is checked against. Either may be absent when the contract names no one.
 */
export interface ContractParties {
  employer_name: string | null;
  agency_name: string | null;
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

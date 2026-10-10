import { ApiError } from "@/services/apiClient";
import type {
  ClauseCounts,
  ClauseRisk,
  ContractAnalysis,
  PipelineErrorCode,
  PipelineStep,
  LetterPendingReason,
} from "@/types/contract";
import type { HostCountry, JobType, LanguageCode } from "@/types/enums";
import { errorMessageKey } from "@/utils/errors";

/**
 * The five steps the worker sees. The backend has six (NF-P2-007); its complaint letter and
 * translation only run sometimes, so they share "report" instead of appearing and vanishing.
 */
export const SCREEN_STEPS = ["read", "place", "law", "check", "report"] as const;
export type ScreenStep = (typeof SCREEN_STEPS)[number];
export type StepState = "waiting" | "running" | "done" | "failed";

const SCREEN_STEP_OF: Record<PipelineStep, ScreenStep> = {
  extract: "read",
  detect: "place",
  law: "law",
  compare: "check",
  complaint: "report",
  translate: "report",
};

/** The fields of `users/{uid}/contracts/{id}` the progress screen reads (contracts.md). */
export interface ContractProgressDoc {
  status?: ContractAnalysis["status"];
  step?: PipelineStep;
  error?: { step: PipelineStep; code: PipelineErrorCode };
  host_country?: HostCountry;
  job_type?: JobType;
  health_score?: number;
  risk_level?: ClauseRisk;
  clause_counts?: ClauseCounts;
  report_languages?: LanguageCode[];
  complaint_pending?: boolean;
  complaint_pending_reason?: LetterPendingReason | null;
}

/** Where the page is: sending the file, waiting for the analysis, or stopped by an error. */
export type Phase = "uploading" | "analyzing" | "failed";

export interface ProgressView {
  states: Record<ScreenStep, StepState>;
  /** The running or failed step; null when nothing has started or everything is done. */
  current: ScreenStep | null;
  failedCode: PipelineErrorCode | null;
}

function viewAt(step: ScreenStep, state: "running" | "failed"): Record<ScreenStep, StepState> {
  const index = SCREEN_STEPS.indexOf(step);
  return Object.fromEntries(
    SCREEN_STEPS.map((name, i) => [name, i < index ? "done" : i === index ? state : "waiting"])
  ) as Record<ScreenStep, StepState>;
}

/**
 * The screen steps from the page's phase and the live contract document.
 *
 * The document is the truth once it exists; before the upload returns there is none, so the
 * first step runs.
 *
 * `seenThisRun` is whether this run has been seen `processing` (the backend claiming the
 * contract). Until then a `completed` document is the last check of the same file (a re-upload
 * reuses the contract), and a `failed` one seen while analysing is the failure being retried:
 * this run has not got past finding the workplace yet.
 */
export function progressView(
  phase: Phase,
  latest: ContractProgressDoc | null,
  seenThisRun = true
): ProgressView {
  const earlier =
    !seenThisRun &&
    (latest?.status === "completed" || (latest?.status === "failed" && phase === "analyzing"));
  const doc: ContractProgressDoc | null = earlier
    ? { ...latest, status: "uploaded", error: undefined }
    : latest;
  if (doc?.status === "completed") {
    return { states: viewAt("report", "running"), current: null, failedCode: null };
  }
  if (phase === "failed" || doc?.status === "failed") {
    const step = doc?.error ? SCREEN_STEP_OF[doc.error.step] : doc ? "place" : "read";
    return { states: viewAt(step, "failed"), current: step, failedCode: doc?.error?.code ?? null };
  }
  if (phase === "uploading" || !doc) {
    return { states: viewAt("read", "running"), current: "read", failedCode: null };
  }
  const step =
    doc.status === "processing" && doc.step ? SCREEN_STEP_OF[doc.step] : ("place" as ScreenStep);
  return { states: viewAt(step, "running"), current: step, failedCode: null };
}

/** Every step done: what the page shows for a finished analysis. */
export const ALL_DONE: Record<ScreenStep, StepState> = Object.fromEntries(
  SCREEN_STEPS.map((name) => [name, "done"])
) as Record<ScreenStep, StepState>;

/** i18n key telling the worker why the check stopped and what to do. */
export function failureMessageKey(code: PipelineErrorCode | null): string {
  switch (code) {
    case "poor_legibility":
      return "contract.progress.errors.poorLegibility";
    case "country_unknown":
      return "contract.progress.errors.countryUnknown";
    case "not_employment_contract":
      return "contract.progress.errors.notEmploymentContract";
    case "no_law_data":
      return "contract.progress.errors.noLawData";
    case "no_terms":
      return "contract.progress.errors.noTerms";
    case "gemini_busy":
    case "gemini_unavailable":
      return "contract.progress.errors.aiBusy";
    case "gemini_timeout":
      return "contract.progress.errors.aiSlow";
    default:
      return "contract.progress.errors.generic";
  }
}

/**
 * Why a contract request failed, when the contract document has no `error` to say it (the
 * upload itself, or a failure before the backend stored one). The contract endpoints use
 * 502/503/504 only for Gemini (`docs/api/endpoints.md`), not for a broken server.
 */
export function requestFailureKey(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 503) {
      return "contract.progress.errors.aiBusy";
    }
    if (error.status === 504) {
      return "contract.progress.errors.aiSlow";
    }
    if (error.status === 502) {
      return "contract.progress.errors.generic";
    }
  }
  return errorMessageKey(error);
}

/**
 * What to tell the worker when the upload itself was refused. A file the reader finds no document
 * in (a photo of something else) is a 422, and "Something went wrong, try again" would send them
 * round again with the same file.
 */
export function uploadFailureKey(error: unknown): string {
  if (error instanceof ApiError && error.status === 422) {
    return "contract.upload.errors.notAContract";
  }
  return requestFailureKey(error);
}

/** Whether running the analysis again can help. Content problems need a different file. */
export function canRetry(code: PipelineErrorCode | null): boolean {
  return !(
    code === "poor_legibility" ||
    code === "not_employment_contract" ||
    code === "no_law_data" ||
    code === "no_terms"
  );
}

/**
 * The finished analysis read from the contract document: the result still reaches the worker
 * when the phone lost the analyze response but the server finished (common on mobile data).
 */
export function analysisFromDoc(
  contractId: string,
  doc: ContractProgressDoc,
  reportLanguage: LanguageCode
): ContractAnalysis | null {
  if (
    doc.status !== "completed" ||
    doc.health_score === undefined ||
    !doc.risk_level ||
    !doc.clause_counts ||
    !doc.host_country ||
    !doc.job_type
  ) {
    return null;
  }
  return {
    contract_id: contractId,
    status: "completed",
    cached: false,
    host_country: doc.host_country,
    job_type: doc.job_type,
    health_score: doc.health_score,
    risk_level: doc.risk_level,
    clause_counts: doc.clause_counts,
    report_language: reportLanguage,
    report_languages: doc.report_languages ?? [],
    complaint_pending: doc.complaint_pending ?? false,
    complaint_pending_reason: doc.complaint_pending ? (doc.complaint_pending_reason ?? null) : null,
  };
}

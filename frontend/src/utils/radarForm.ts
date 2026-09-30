import { ApiError } from "@/services/apiClient";
import type { LanguageCode } from "@/types/enums";
import type { RadarReportRequest, ReportDraft } from "@/types/radar";
import { errorMessageKey } from "@/utils/errors";

// Mirror backend `radar_report.py` and the evidence upload limits (`radar.py`, UPLOAD_MAX_BYTES).
// The backend is authoritative; these give quick feedback before a slow upload.
export const MIN_DESCRIPTION_CHARS = 10;
export const MAX_DESCRIPTION_CHARS = 2000;
export const MAX_NAME_CHARS = 200;
export const MAX_EVIDENCE_FILES = 5;
export const MAX_EVIDENCE_BYTES = 10 * 1024 * 1024;
export const EVIDENCE_TYPES: Record<string, string[]> = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/webp": [".webp"],
  "image/heic": [".heic"],
  "image/heif": [".heif"],
};

export const STEPS = ["who", "where", "what", "review"] as const;
export type Step = (typeof STEPS)[number];

/** i18n key of what is wrong with a step, or null when the worker may go on. */
export function stepProblem(step: Step, draft: ReportDraft): string | null {
  if (step === "who") {
    if (draft.entityType === null) {
      return "radar.report.validation.typeRequired";
    }
    return draft.entityName.trim() === "" ? "radar.report.validation.nameRequired" : null;
  }
  if (step === "where") {
    if (draft.entityType === "employer") {
      return draft.hostCountry === null ? "radar.report.validation.locationRequired" : null;
    }
    return draft.corridorId === null ? "radar.report.validation.locationRequired" : null;
  }
  if (step === "what") {
    return draft.description.trim().length < MIN_DESCRIPTION_CHARS
      ? "radar.report.validation.descriptionShort"
      : null;
  }
  return null;
}

/** The request body. An employer has a country, an operator or agency has a money route. */
export function buildRequest(
  draft: ReportDraft,
  fallbackLanguage: LanguageCode
): RadarReportRequest {
  if (draft.entityType === null) {
    throw new Error("entity type is required");
  }
  const request: RadarReportRequest = {
    entity_type: draft.entityType,
    entity_name: draft.entityName.trim(),
    description: draft.description.trim(),
    language: draft.language ?? fallbackLanguage,
  };
  if (draft.entityType === "employer" && draft.hostCountry !== null) {
    request.host_country = draft.hostCountry;
  } else if (draft.corridorId !== null) {
    request.corridor_id = draft.corridorId;
  }
  return request;
}

// Start of the 422 texts in backend `api/v1/radar.py`, in the order they are raised there.
const REJECTION_KEYS: ReadonlyArray<readonly [string, string]> = [
  ["Could not tell who", "radar.report.errors.entityUnknown"],
  ["Could not tell where", "radar.report.errors.locationUnknown"],
  ["This doesn't look like a real report", "radar.report.errors.spam"],
  ["This report cannot be published", "radar.report.errors.abusive"],
  ["Please remove personal details", "radar.report.errors.personalData"],
];

/** i18n key that tells the worker why sending the report failed. */
export function reportFailureKey(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) {
      const match = REJECTION_KEYS.find(([start]) => error.detail.startsWith(start));
      return match ? match[1] : "radar.report.errors.rejected";
    }
    if (error.status === 503) {
      return "radar.report.errors.aiBusy";
    }
    if (error.status === 504) {
      return "radar.report.errors.aiSlow";
    }
  }
  return errorMessageKey(error);
}

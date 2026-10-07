// The analyze answers of docs/mocks/scam/ as typed values, for the tests of the scam screens.
// Only tests import this module; the app never does.
import { jsonMocks } from "@/mocks/files";
import type { ScamAnalyzeResponse } from "@/types/scam";

export const SCAM_CASES = {
  high: "scam/analyze-01-high-risk.json",
  medium: "scam/analyze-02-medium-risk.json",
  low: "scam/analyze-03-low-risk.json",
  benign: "scam/analyze-04-benign.json",
  noExplainer: "scam/analyze-06-explainer-unavailable.json",
} as const;

export type ScamCase = keyof typeof SCAM_CASES;

/** One mock answer, with any field changed for the test's purpose. */
export function scamResult(
  name: ScamCase,
  changes: Partial<ScamAnalyzeResponse> = {}
): ScamAnalyzeResponse {
  const mock = jsonMocks.get(SCAM_CASES[name]);
  if (mock?.body === undefined) {
    throw new Error(`No mock ${SCAM_CASES[name]}`);
  }
  return { ...(structuredClone(mock.body) as ScamAnalyzeResponse), ...changes };
}

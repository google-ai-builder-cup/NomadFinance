// What the "Warn other workers" sheet may send (NF-SA-018). The rules are the contract's
// (docs/api/v2-scam.md, `POST /scam/checks/{id}/report`); keeping them here, away from the sheet,
// means every edge is a plain test and the sheet only draws.
import type { ScamIndicator, ScamReportRequest } from "@/types/scam";

export const MAX_REPORT_CHARS = 1000;
export const MAX_REPORT_CONTACTS = 10;

// The server counts characters (code points); a string's `length` counts UTF-16 units, so an
// emoji would count twice and a cut could split one in half.
const characters = (text: string): string[] => Array.from(text);

export function reportTextLength(text: string): number {
  return characters(text).length;
}

/** The text cut to the limit, without splitting a character. */
export function clampReportText(text: string): string {
  const all = characters(text);
  return all.length <= MAX_REPORT_CHARS ? text : all.slice(0, MAX_REPORT_CHARS).join("");
}

/** The report may go when the text says something and is not over the limit. */
export function canSendReport(text: string): boolean {
  return text.trim() !== "" && reportTextLength(text) <= MAX_REPORT_CHARS;
}

/** The contacts ticked when the sheet opens: all of them, up to the limit. They are the worker's
 * to untick, because a number or address in the message may be their own. */
export function initialTicked(indicators: readonly ScamIndicator[]): string[] {
  return indicators.slice(0, MAX_REPORT_CONTACTS).map((indicator) => indicator.id);
}

/** Tick or untick one contact. A tick past the limit is ignored: the contract takes at most 10. */
export function toggleTicked(ticked: readonly string[], id: string): string[] {
  if (ticked.includes(id)) {
    return ticked.filter((current) => current !== id);
  }
  return ticked.length >= MAX_REPORT_CONTACTS ? [...ticked] : [...ticked, id];
}

/** The request is exactly what the sheet shows: the text as it stands and the ticked contacts, in
 * the order the message lists them. Nothing else is sent. */
export function buildReportRequest(
  text: string,
  indicators: readonly ScamIndicator[],
  ticked: readonly string[]
): ScamReportRequest {
  return {
    indicator_ids: indicators.map((indicator) => indicator.id).filter((id) => ticked.includes(id)),
    description: text.trim(),
  };
}

/** The Radar profile of a kind of scam, the way the backend names it (`scam-` and the type id with
 * hyphens: docs/data-model/collections/radar.md). The report's answer carries the slug; this is
 * for a check that was reported before, whose stored record does not. */
export function scamEntitySlug(scamType: string): string {
  return `scam-${scamType.replaceAll("_", "-")}`;
}

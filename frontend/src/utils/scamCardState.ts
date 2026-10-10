import type { ScamCheckList } from "@/types/scam";

const RISKS = ["low", "medium", "high"] as const;
export type CardRisk = (typeof RISKS)[number];

/** What the home dashboard's Scam Check card says about the worker's history. */
export type ScamCardState =
  { kind: "none" } | { kind: "last"; result: CardRisk | "benign"; at: string };

/**
 * The newest check, as a word the card can show. A message that is not a scam is "benign"
 * whatever its risk level; a risk level this version does not know is shown as the middle one,
 * so the card never prints a raw code.
 */
export function scamCardState(list: ScamCheckList): ScamCardState {
  const newest = list.items[0];
  if (newest === undefined) {
    return { kind: "none" };
  }
  if (!newest.is_scam) {
    return { kind: "last", result: "benign", at: newest.created_at };
  }
  const known = (RISKS as readonly string[]).includes(newest.risk_level);
  return {
    kind: "last",
    result: known ? (newest.risk_level as CardRisk) : "medium",
    at: newest.created_at,
  };
}

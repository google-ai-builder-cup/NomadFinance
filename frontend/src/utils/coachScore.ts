import type { CoachScore, ScoreFactorId } from "@/types/coach";

// The words of the score screen are chosen by factor and level, not written per score
// (docs/features/coach-scoring.md, "For the screen and for the tests").
export type ScoreLevel = "strong" | "fair" | "weak";

/** Strong from 70 points, fair from 40, weak below: the same cut-offs as the bands. */
export function levelOf(points: number): ScoreLevel {
  if (points >= 70) {
    return "strong";
  }
  return points >= 40 ? "fair" : "weak";
}

export const KNOWN_BANDS = ["needs_work", "getting_ready", "well_prepared"] as const;
export type ScoreBand = (typeof KNOWN_BANDS)[number];

export function isKnownBand(band: string): band is ScoreBand {
  return (KNOWN_BANDS as readonly string[]).includes(band);
}

/** The colour family of a band: red below 40, amber to 69, green from 70. A band the screen does
 * not know is neutral. The band's name is always written as well: colour is never alone. */
export function bandTone(band: string): "danger" | "caution" | "safe" | "neutral" {
  switch (band) {
    case "needs_work":
      return "danger";
    case "getting_ready":
      return "caution";
    case "well_prepared":
      return "safe";
    default:
      return "neutral";
  }
}

export const FLOOR_POINTS = 20;

/** A total in the top band's range is held at "getting ready" by one very low factor (the floor
 * rule of the rubric). The screen says so, or a worker with 74 points would not understand 74
 * being "getting ready". */
export function isHeldByFloor(score: CoachScore): boolean {
  return (
    score.band === "getting_ready" &&
    score.total >= 70 &&
    score.factors.some((factor) => factor.score < FLOOR_POINTS)
  );
}

export function factorKey(
  id: ScoreFactorId | string,
  level: ScoreLevel,
  part: "means" | "improve"
) {
  return `score.factor.${id}.${level}.${part}`;
}

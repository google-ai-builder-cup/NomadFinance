import type { FeatureFlags } from "@/types/flags";

// Bumping the version shows the tour again to everyone, for a release that adds new modules.
const TOUR_VERSION = "v2";
const KEY_PREFIX = "nomadfinance.tour.";

export const tourStorageKey = (uid: string) => `${KEY_PREFIX}${TOUR_VERSION}.${uid}`;

/**
 * Whether this worker has been through (or skipped) the tour in this browser. When the browser
 * will not say (storage blocked or full) the answer is "seen": a tour that cannot be remembered
 * would come back on every visit, and a worker is better off without it than nagged by it.
 */
export function hasSeenTour(uid: string): boolean {
  try {
    return localStorage.getItem(tourStorageKey(uid)) !== null;
  } catch {
    return true;
  }
}

export function markTourSeen(uid: string): void {
  try {
    localStorage.setItem(tourStorageKey(uid), new Date().toISOString());
  } catch {
    // Storage is blocked or full: hasSeenTour then reports "seen", so the tour does not repeat.
  }
}

export type TourStep = "scam" | "coach" | "outro";

/** The tour introduces only the modules that are on for this worker, then a closing step. With
 * none on there is nothing new to show, so there is no tour. */
export function tourSteps(flags: Pick<FeatureFlags, "scam" | "coach">): TourStep[] {
  const steps: TourStep[] = [];
  if (flags.scam) {
    steps.push("scam");
  }
  if (flags.coach) {
    steps.push("coach");
  }
  return steps.length === 0 ? [] : [...steps, "outro"];
}

import type { TrendPoint } from "@/types/remittance";

const DAY_MS = 86_400_000;
// The ECB publishes on working days only, so a period can open with a few days and a
// holiday weekend before its first point: that is not a short history.
const SLACK_DAYS = 7;

/**
 * The first stored day when the history starts well after the chosen period does (a new
 * installation before its history backfill, D-64), or null when the period is covered. Then
 * every period shows the same few points, which looks like the period switch is broken.
 */
export function historyStartsLate(
  points: readonly TrendPoint[],
  days: number,
  now: Date = new Date()
): string | null {
  if (points.length === 0) {
    return null;
  }
  const first = points[0].date;
  const periodStart = now.getTime() - days * DAY_MS;
  const firstTime = Date.parse(`${first}T00:00:00Z`);
  return firstTime - periodStart > SLACK_DAYS * DAY_MS ? first : null;
}

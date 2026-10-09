/**
 * How long ago something happened, in the worker's language ("2 hours ago", "yesterday"), or null
 * when it was under a minute ago or the time is unusable: the caller then says nothing about when.
 * Whole minutes, hours and days only; a worker needs "last night", not seconds.
 */
export function relativeTime(iso: string, language: string, now = Date.now()): string | null {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) {
    return null;
  }
  const seconds = Math.round((then - now) / 1000);
  // A clock that is a little fast can put the last answer in the future; say nothing then.
  if (seconds > -60) {
    return null;
  }
  const [value, unit]: [number, Intl.RelativeTimeFormatUnit] =
    seconds > -3_600
      ? [Math.round(seconds / 60), "minute"]
      : seconds > -86_400
        ? [Math.round(seconds / 3_600), "hour"]
        : [Math.round(seconds / 86_400), "day"];
  const locale = Intl.RelativeTimeFormat.supportedLocalesOf([language])[0] ?? "en";
  return new Intl.RelativeTimeFormat(locale, { numeric: "auto" }).format(value, unit);
}

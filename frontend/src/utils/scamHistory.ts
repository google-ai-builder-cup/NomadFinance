/** A stored check's date in the worker's language ("5 Nov 2026"), from the browser's locale data.
 * An unreadable value is shown as it came rather than as "Invalid Date". */
export function formatCheckDate(iso: string, language: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  try {
    return new Intl.DateTimeFormat(language, { dateStyle: "medium" }).format(date);
  } catch {
    return date.toISOString().slice(0, 10);
  }
}

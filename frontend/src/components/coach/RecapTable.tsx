import { ClipboardList, Pencil } from "lucide-react";
import { useId } from "react";

import { useFocusOnMount } from "@/hooks/useFocusOnMount";
import { useI18n } from "@/hooks/useI18n";
import { useUiLanguage } from "@/hooks/useUiLanguage";
import type { CoachSlot } from "@/types/coach";
import { recapRows } from "@/utils/coachRecap";

export interface RecapTableProps {
  /** Answers so far, as bare values. */
  slots: Partial<Record<CoachSlot, unknown>>;
  /** A turn is running: nothing more can be sent yet. */
  busy: boolean;
  /** The worker wants to change an answer: the sentence to send, which names it. */
  onChange: (sentence: string) => void;
}

/**
 * The review step's list of answers, as a table the worker can check at a glance, with a Change
 * button on each row. It is built from the saved answers, not from the coach's words, so the
 * figures are exactly the ones stored, and the coach's own message can stay one short line.
 */
export default function RecapTable({ slots, busy, onChange }: RecapTableProps) {
  const { t } = useI18n("coach");
  const language = useUiLanguage();
  const headingId = useId();
  // It appears when the interview reaches the review, below where the worker was looking: focus
  // brings it into view, and a screen reader says what it is.
  const ref = useFocusOnMount<HTMLElement>();
  const rows = recapRows(slots, t, language);

  return (
    <section
      ref={ref}
      tabIndex={-1}
      aria-labelledby={headingId}
      // scroll-mt-20: when focus scrolls it into view, the sticky header (4 rem) must not cover its title.
      className="w-full shrink-0 scroll-mt-20 overflow-hidden rounded-2xl border bg-background shadow-sm focus:outline-none"
    >
      <div className="flex items-center gap-2 border-b bg-muted/50 px-4 py-3">
        <ClipboardList className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        <h2 id={headingId} className="text-sm font-extrabold">
          {t("recap.title")}
        </h2>
      </div>
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{t("recap.caption")}</caption>
        <thead>
          <tr className="text-xs text-muted-foreground">
            <th scope="col" className="px-4 py-2 text-start font-semibold">
              {t("recap.question")}
            </th>
            <th scope="col" className="px-2 py-2 text-start font-semibold">
              {t("recap.answer")}
            </th>
            <th scope="col" className="px-2 py-2">
              <span className="sr-only">{t("recap.action")}</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((row) => (
            <tr key={row.slot}>
              <th
                scope="row"
                className="w-[36%] px-4 py-2.5 text-start align-middle font-medium text-muted-foreground"
              >
                {row.label}
              </th>
              <td className="break-words px-2 py-2.5 align-middle font-bold">{row.value}</td>
              <td className="w-px whitespace-nowrap pe-2 text-end align-middle">
                <button
                  type="button"
                  disabled={busy}
                  aria-label={t("recap.changeLabel", { what: row.label })}
                  onClick={() => onChange(t("recap.changeSentence", { what: row.label }))}
                  className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2 text-sm font-bold text-primary transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
                >
                  <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                  {t("recap.change")}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

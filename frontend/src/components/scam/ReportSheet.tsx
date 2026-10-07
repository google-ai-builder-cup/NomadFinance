import { CircleAlert, Loader2, ShieldCheck, X } from "lucide-react";
import { type FormEvent, type RefObject, useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import type { ScamReportRequest, ScamResultView } from "@/types/scam";
import { scamReportErrorView } from "@/utils/scamErrors";
import {
  buildReportRequest,
  canSendReport,
  clampReportText,
  initialTicked,
  MAX_REPORT_CHARS,
  MAX_REPORT_CONTACTS,
  reportTextLength,
  toggleTicked,
} from "@/utils/scamReport";

export interface ReportSheetProps {
  result: ScamResultView;
  pending: boolean;
  /** The last failed send, shown beside the button; null when there is none. */
  error: unknown;
  onSend: (request: ScamReportRequest) => void;
  onClose: () => void;
}

// Nothing the worker can fix by sending again.
const FINAL_ERRORS = new Set(["report.errors.notAScam", "report.errors.expired"]);

const FOCUSABLE = "button:not([disabled]), textarea, input:not([disabled]), a[href]";

/** A modal that keeps the keyboard inside it, closes on Escape and hands focus back to the button
 * that opened it. Closing is refused while a send is in flight, so a report is never abandoned
 * half way with the worker believing it went. */
function useSheetBehaviour(
  panel: RefObject<HTMLDivElement>,
  pending: boolean,
  onClose: () => void
) {
  const latest = useRef({ pending, onClose });
  useEffect(() => {
    latest.current = { pending, onClose };
  });

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();

    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !latest.current.pending) {
        latest.current.onClose();
        return;
      }
      if (event.key !== "Tab" || panel.current === null) {
        return;
      }
      const items = panel.current.querySelectorAll<HTMLElement>(FOCUSABLE);
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === panel.current)) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
      if (opener?.isConnected) {
        opener.focus();
      }
    };
  }, [panel]);
}

/**
 * The confirmation before a warning goes to Exploitation Radar. It shows exactly what other
 * workers will see (the kind of scam, the message as the worker leaves it, each contact with a
 * tick) and sends exactly that. The message is masked for numbers and links but not for names
 * (D-108), so this is where the worker takes a name out.
 */
export default function ReportSheet({ result, pending, error, onSend, onClose }: ReportSheetProps) {
  const { t } = useI18n("scam");
  const ids = useId();
  const panel = useRef<HTMLDivElement>(null);
  const [text, setText] = useState(() => clampReportText(result.redacted_text));
  const [ticked, setTicked] = useState(() => initialTicked(result.indicators));
  useSheetBehaviour(panel, pending, onClose);

  const { verdict, indicators } = result;
  const count = reportTextLength(text);
  const errorView = error === null || error === undefined ? null : scamReportErrorView(error);
  const final = errorView !== null && FINAL_ERRORS.has(errorView.messageKey);
  const typeLabel = verdict.scam_type
    ? t(`result.type.${verdict.scam_type}`, {
        defaultValue: verdict.scam_type.replaceAll("_", " "),
      })
    : "";

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (canSendReport(text) && !pending && !final) {
      onSend(buildReportRequest(text, indicators, ticked));
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-4"
      onClick={() => !pending && onClose()}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${ids}-title`}
        aria-describedby={`${ids}-intro`}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
        className="max-h-[92%] w-full max-w-lg overflow-y-auto rounded-t-2xl border bg-card p-5 pb-0 shadow-lg focus:outline-none sm:rounded-2xl"
      >
        <div className="flex items-start justify-between gap-3">
          <h2 id={`${ids}-title`} className="text-lg font-extrabold">
            {t("report.sheet.title")}
          </h2>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="-mr-2 -mt-1 h-11 w-11 shrink-0"
            onClick={onClose}
            disabled={pending}
            aria-label={t("report.sheet.close")}
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </Button>
        </div>

        <form onSubmit={handleSubmit} className="mt-3 space-y-5" noValidate>
          <p id={`${ids}-intro`} className="text-sm">
            {t("report.sheet.intro", { type: typeLabel })}
          </p>

          <p className="text-sm">
            <span className="block text-xs font-semibold text-muted-foreground">
              {t("result.kindOfScam")}
            </span>
            <strong>{typeLabel}</strong>
          </p>

          <div className="space-y-2">
            <label htmlFor={`${ids}-text`} className="text-sm font-bold">
              {t("report.sheet.textLabel")}
            </label>
            <textarea
              id={`${ids}-text`}
              value={text}
              onChange={(event) => setText(clampReportText(event.target.value))}
              disabled={pending}
              rows={6}
              aria-describedby={`${ids}-text-hint`}
              className={cn(
                "min-h-36 w-full resize-y rounded-xl border border-input bg-background px-3 py-2 text-base",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
              )}
            />
            <div id={`${ids}-text-hint`} className="flex items-start justify-between gap-3 text-xs">
              <span className="text-muted-foreground">{t("report.sheet.textHint")}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {t("input.counter", { count, max: MAX_REPORT_CHARS })}
              </span>
            </div>
          </div>

          <fieldset className="space-y-2" disabled={pending}>
            <legend className="text-sm font-bold">{t("report.sheet.contactsTitle")}</legend>
            {indicators.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("report.sheet.noContacts")}</p>
            ) : (
              <>
                <p className="text-xs text-muted-foreground">
                  {t("report.sheet.contactsHint")}
                  {indicators.length > MAX_REPORT_CONTACTS &&
                    ` ${t("report.sheet.contactsMax", { max: MAX_REPORT_CONTACTS })}`}
                </p>
                <ul className="space-y-2">
                  {indicators.map((indicator) => {
                    const checked = ticked.includes(indicator.id);
                    const full = !checked && ticked.length >= MAX_REPORT_CONTACTS;
                    return (
                      <li key={indicator.id}>
                        <label
                          className={cn(
                            "flex min-h-11 cursor-pointer items-start gap-3 rounded-xl border border-border p-3",
                            full && "cursor-not-allowed opacity-60"
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={full}
                            onChange={() =>
                              setTicked((current) => toggleTicked(current, indicator.id))
                            }
                            className="mt-0.5 h-5 w-5 shrink-0 accent-primary"
                          />
                          <span className="min-w-0 space-y-1">
                            <span className="block text-xs font-semibold text-muted-foreground">
                              {t(`result.indicators.kind.${indicator.kind}`)}
                            </span>
                            <code className="block break-all text-sm font-semibold">
                              {indicator.value}
                            </code>
                          </span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </>
            )}
          </fieldset>

          <div className="space-y-2 rounded-xl bg-muted/60 p-3 text-sm">
            <p>{t("report.sheet.alsoShared")}</p>
            <p className="flex items-start gap-2 font-semibold">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              {t("report.sheet.anonymous")}
            </p>
          </div>

          {errorView !== null && (
            <p
              role="alert"
              className="flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm font-semibold"
            >
              <CircleAlert
                className="mt-0.5 h-4 w-4 shrink-0 text-destructive"
                aria-hidden="true"
              />
              {t(errorView.messageKey)}
            </p>
          )}

          {/* Stuck to the bottom of the sheet, so on a short phone the button that sends is never
              below the fold. */}
          <div className="sticky bottom-0 -mx-5 flex flex-col-reverse gap-2 border-t bg-card px-5 pb-5 pt-3 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              onClick={onClose}
              disabled={pending}
            >
              {t("report.sheet.cancel")}
            </Button>
            <Button
              type="submit"
              className="min-h-11 gap-2"
              disabled={pending || final || !canSendReport(text)}
            >
              {pending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              {pending ? t("report.sheet.sending") : t("report.sheet.send")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

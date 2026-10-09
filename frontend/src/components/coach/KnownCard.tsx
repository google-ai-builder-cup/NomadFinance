import { useMutation } from "@tanstack/react-query";
import { Loader2, Pencil, Undo2, UserCheck } from "lucide-react";
import { useId, useRef, useState } from "react";

import CoachNotice from "@/components/coach/CoachNotice";
import { Button } from "@/components/ui/button";
import { useFocusOnMount } from "@/hooks/useFocusOnMount";
import { useI18n } from "@/hooks/useI18n";
import { useUiLanguage } from "@/hooks/useUiLanguage";
import { applyKnownDetails } from "@/services/coachService";
import type { CoachKnownItem, CoachSession, CoachSlot } from "@/types/coach";
import { toFailure } from "@/utils/coachErrors";
import { formatDate, recapValue } from "@/utils/coachRecap";

export interface KnownCardProps {
  sessionId: string;
  items: readonly CoachKnownItem[];
  /** The server made the kept answers into the session's answers. */
  onApplied: (session: CoachSession) => void;
  /** The interview cannot go on (it ended or is gone): start a new one. */
  onRestart: () => void;
  restarting?: boolean;
}

/**
 * What the Coach already knows about the worker, from their profile, their contract and their
 * Financial Identity, shown before the first question. Each row says where it came from; the
 * worker keeps it or marks it "change", and a changed one is asked as usual. Nothing is an answer
 * until they press the button, and nothing they change here is written back to their records.
 */
export default function KnownCard({
  sessionId,
  items,
  onApplied,
  onRestart,
  restarting,
}: KnownCardProps) {
  const { t } = useI18n("coach");
  const language = useUiLanguage();
  const headingId = useId();
  const ref = useFocusOnMount<HTMLElement>();
  const [changing, setChanging] = useState<ReadonlySet<CoachSlot>>(new Set());
  const kept = items.filter(({ slot }) => !changing.has(slot)).map(({ slot }) => slot);

  // What the last press asked for, so "Try again" repeats that and not the other button.
  const asked = useRef<readonly CoachSlot[]>([]);
  const apply = useMutation({
    mutationFn: (keep: readonly CoachSlot[]) => applyKnownDetails(sessionId, keep),
    onSuccess: onApplied,
    retry: false,
    // The failure is shown here, next to the buttons, not as a toast.
    meta: { inlineError: true },
  });
  const busy = apply.isPending || restarting === true;

  function send(keep: readonly CoachSlot[]) {
    asked.current = keep;
    apply.mutate(keep);
  }

  function toggle(slot: CoachSlot) {
    setChanging((now) => {
      const next = new Set(now);
      if (!next.delete(slot)) {
        next.add(slot);
      }
      return next;
    });
  }

  return (
    <section
      ref={ref}
      tabIndex={-1}
      aria-labelledby={headingId}
      className="w-full scroll-mt-20 overflow-hidden rounded-2xl border bg-card shadow-sm focus:outline-none"
    >
      <div className="flex items-start gap-3 border-b bg-muted/50 px-4 py-3">
        <UserCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <h2 id={headingId} className="text-base font-extrabold">
            {t("known.title")}
          </h2>
          <p className="text-sm text-muted-foreground">{t("known.description")}</p>
        </div>
      </div>
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{t("known.caption")}</caption>
        <thead>
          <tr className="text-xs text-muted-foreground">
            <th scope="col" className="px-4 py-2 text-start font-semibold">
              {t("known.question")}
            </th>
            <th scope="col" className="px-2 py-2 text-start font-semibold">
              {t("known.answer")}
            </th>
            <th scope="col" className="px-2 py-2">
              <span className="sr-only">{t("known.action")}</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {items.map((item) => {
            const label = t(`recap.slot.${item.slot}`);
            const dropped = changing.has(item.slot);
            const value = recapValue(item.slot, item.value, t, language) ?? "—";
            return (
              <tr key={item.slot}>
                <th
                  scope="row"
                  className="w-[34%] px-4 py-2.5 text-start align-middle font-medium text-muted-foreground"
                >
                  {label}
                </th>
                <td className="break-words px-2 py-2.5 align-middle">
                  {dropped ? (
                    <span className="italic text-muted-foreground">{t("known.willAsk")}</span>
                  ) : (
                    <>
                      <span className="block font-bold">{value}</span>
                      <span className="block text-xs text-muted-foreground">
                        {t(`known.source.${item.source}`, {
                          date: item.as_of === null ? "" : formatDate(item.as_of, language),
                        })}
                      </span>
                    </>
                  )}
                </td>
                <td className="w-px whitespace-nowrap pe-2 text-end align-middle">
                  <button
                    type="button"
                    disabled={busy}
                    aria-label={t(dropped ? "known.keepLabel" : "known.changeLabel", {
                      what: label,
                    })}
                    onClick={() => toggle(item.slot)}
                    className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2 text-sm font-bold text-primary transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
                  >
                    {dropped ? (
                      <Undo2 className="h-3.5 w-3.5" aria-hidden="true" />
                    ) : (
                      <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                    )}
                    {t(dropped ? "known.keep" : "known.change")}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="space-y-3 border-t p-4">
        {apply.isError && (
          <CoachNotice
            failure={toFailure(apply.error)}
            onRetry={() => apply.mutate(asked.current)}
            onRestart={onRestart}
            restarting={restarting}
          />
        )}
        {kept.length === 0 && (
          <p role="status" className="text-sm text-muted-foreground">
            {t("known.noneKept")}
          </p>
        )}
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button
            type="button"
            className="min-h-11 flex-1 gap-2 font-bold"
            disabled={busy || kept.length === 0}
            onClick={() => send(kept)}
          >
            {apply.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
            {t("known.use")}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="min-h-11 flex-1 font-bold"
            disabled={busy}
            onClick={() => send([])}
          >
            {t("known.skip")}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">{t("known.privacy")}</p>
      </div>
    </section>
  );
}

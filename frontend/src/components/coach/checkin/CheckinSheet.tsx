import { CircleAlert, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import CheckinDone from "@/components/coach/checkin/CheckinDone";
import { Button } from "@/components/ui/button";
import { useSubmitCheckin } from "@/hooks/useCoachCheckin";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import type { CheckinAnswers, CheckinMilestone } from "@/types/coachCheckin";
import { toFailure } from "@/utils/coachErrors";
import { CHECKIN_QUESTIONS, checkinErrorView, isComplete } from "@/utils/coachCheckin";

export interface CheckinSheetProps {
  planId: string;
  milestone: CheckinMilestone;
}

/**
 * The three questions of a day 30, 60 or 90 check-in, one at a time, each a closed list of
 * choices (nothing typed, so nothing sensitive is stored and every choice is translated). The
 * answers are kept on this screen until the last question, then sent once; a failure keeps them,
 * so sending again is one tap.
 */
export default function CheckinSheet({ planId, milestone }: CheckinSheetProps) {
  const { t } = useI18n("coach");
  const submit = useSubmitCheckin(planId, milestone);
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Partial<CheckinAnswers>>({});
  const legend = useRef<HTMLLegendElement>(null);
  const moved = useRef(false);

  // The next question is a new thing to read: put the reader at its start (after the first one,
  // which the page has just opened).
  useEffect(() => {
    if (moved.current) {
      legend.current?.focus();
    }
    moved.current = true;
  }, [step]);

  if (submit.isSuccess) {
    return <CheckinDone planId={planId} result={submit.data} />;
  }

  const question = CHECKIN_QUESTIONS[step];
  const chosen = answers[question.id];
  const last = step === CHECKIN_QUESTIONS.length - 1;
  const failure = submit.isError ? checkinErrorView(toFailure(submit.error)) : null;

  function choose(option: string) {
    setAnswers((current) => ({ ...current, [question.id]: option }));
  }

  function next() {
    if (!last) {
      setStep(step + 1);
    } else if (isComplete(answers)) {
      submit.mutate(answers);
    }
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (chosen !== undefined && !submit.isPending) {
          next();
        }
      }}
      className="space-y-4"
    >
      <div className="space-y-1.5">
        <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
          {t("checkin.progress", { current: step + 1, total: CHECKIN_QUESTIONS.length })}
        </p>
        <div className="flex gap-1.5" aria-hidden="true">
          {CHECKIN_QUESTIONS.map(({ id }, index) => (
            <span
              key={id}
              className={cn("h-1.5 flex-1 rounded-full", index <= step ? "bg-primary" : "bg-muted")}
            />
          ))}
        </div>
      </div>

      <fieldset className="min-w-0 space-y-3" disabled={submit.isPending}>
        <legend
          ref={legend}
          tabIndex={-1}
          className="mb-3 text-lg font-bold leading-snug focus:outline-none"
        >
          {t(`checkin.questions.${question.id}`)}
        </legend>
        {question.options.map((option) => {
          const selected = chosen === option;
          return (
            <label
              key={option}
              className={cn(
                "flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border bg-card p-3 text-base font-semibold",
                "focus-within:ring-2 focus-within:ring-ring",
                selected && "border-primary bg-primary/5"
              )}
            >
              <input
                type="radio"
                name={question.id}
                value={option}
                checked={selected}
                onChange={() => choose(option)}
                className="h-5 w-5 shrink-0 accent-primary"
              />
              <span className="min-w-0">{t(`checkin.options.${question.id}.${option}`)}</span>
            </label>
          );
        })}
      </fieldset>

      {failure !== null && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-2xl border border-destructive/40 bg-destructive/5 p-3"
        >
          <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-danger-ink" aria-hidden="true" />
          <p className="text-sm font-semibold">{t(failure.messageKey)}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {step > 0 && (
          <Button
            type="button"
            variant="outline"
            className="min-h-11"
            disabled={submit.isPending}
            onClick={() => setStep(step - 1)}
          >
            {t("checkin.back")}
          </Button>
        )}
        <Button
          type="submit"
          className="min-h-11 flex-1 font-bold sm:flex-none"
          disabled={chosen === undefined || submit.isPending}
        >
          {submit.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              {t("checkin.sending")}
            </>
          ) : last ? (
            t("checkin.send")
          ) : (
            t("checkin.next")
          )}
        </Button>
      </div>
    </form>
  );
}

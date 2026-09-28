import { Check, Loader2, X } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { SCREEN_STEPS, type ScreenStep, type StepState } from "@/utils/pipelineProgress";

// Gemini sometimes stalls on one step for a minute or more (D-54): after this long the worker
// is told it is still working, so a slow step does not look like a frozen page.
const STALL_AFTER_MS = 45_000;

export interface PipelineProgressProps {
  states: Record<ScreenStep, StepState>;
  /** The running or failed step; null when all are waiting or done. */
  current: ScreenStep | null;
  /** i18n key of why the check stopped; null while it runs. */
  failureKey: string | null;
  /** Buttons shown under a failure (try again, check another contract). */
  actions?: ReactNode;
}

function StepIcon({ state, number }: { state: StepState; number: number }) {
  const base = "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm";
  if (state === "done") {
    return (
      <span className={cn(base, "border-primary bg-primary text-primary-foreground")}>
        <Check className="h-4 w-4" aria-hidden="true" />
      </span>
    );
  }
  if (state === "running") {
    return (
      <span className={cn(base, "border-primary text-primary")}>
        <Loader2 className="h-4 w-4 motion-safe:animate-spin" aria-hidden="true" />
      </span>
    );
  }
  if (state === "failed") {
    return (
      <span className={cn(base, "border-destructive bg-destructive text-destructive-foreground")}>
        <X className="h-4 w-4" aria-hidden="true" />
      </span>
    );
  }
  return (
    <span className={cn(base, "text-muted-foreground")} aria-hidden="true">
      {number}
    </span>
  );
}

/**
 * Contract Shield's steps while a contract is checked (NF-P2-010). Driven by the live contract
 * document, so a step is only "done" when the backend has really moved past it.
 */
export default function PipelineProgress({
  states,
  current,
  failureKey,
  actions,
}: PipelineProgressProps) {
  const { t } = useI18n();
  const running = failureKey === null ? current : null;
  // The step that has run too long; the hint shows only while that same step still runs.
  const [stalledStep, setStalledStep] = useState<ScreenStep | null>(null);
  const stalled = running !== null && stalledStep === running;

  useEffect(() => {
    if (running === null) {
      return;
    }
    const timer = window.setTimeout(() => setStalledStep(running), STALL_AFTER_MS);
    return () => window.clearTimeout(timer);
  }, [running]);

  const runningNumber = running === null ? 0 : SCREEN_STEPS.indexOf(running) + 1;

  return (
    <section
      aria-labelledby="contract-progress-title"
      className="space-y-5 rounded-lg border bg-card p-6"
    >
      <header className="space-y-1">
        <h2 id="contract-progress-title" className="text-lg font-semibold">
          {t("contract.progress.title")}
        </h2>
        <p className="text-sm text-muted-foreground">{t("contract.progress.subtitle")}</p>
      </header>

      <ol className="space-y-3">
        {SCREEN_STEPS.map((step, index) => {
          const state = states[step];
          return (
            <li
              key={step}
              aria-current={state === "running" ? "step" : undefined}
              className="flex items-start gap-3"
            >
              <StepIcon state={state} number={index + 1} />
              <div className="min-w-0 pt-1">
                <p
                  className={cn(
                    "text-sm",
                    state === "running" && "font-semibold",
                    state === "waiting" && "text-muted-foreground",
                    state === "failed" && "font-semibold text-destructive"
                  )}
                >
                  {t(`contract.progress.steps.${step}`)}
                  <span className="sr-only"> ({t(`contract.progress.state.${state}`)})</span>
                </p>
                {state === "running" && stalled && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("contract.progress.stalled")}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {/* Announces each new step; the list itself is not a live region, to avoid repeats. */}
      <p aria-live="polite" className="sr-only">
        {running &&
          t("contract.progress.announce", {
            number: runningNumber,
            total: SCREEN_STEPS.length,
            step: t(`contract.progress.steps.${running}`),
          })}
      </p>

      {failureKey && (
        <div
          role="alert"
          className="space-y-4 rounded-md border border-destructive/30 bg-destructive/10 p-4"
        >
          <p className="text-sm font-medium text-destructive">
            {t("contract.progress.failedTitle")}
          </p>
          <p className="text-sm">{t(failureKey)}</p>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      )}
    </section>
  );
}

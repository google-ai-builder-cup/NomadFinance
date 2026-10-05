import { Check, Loader2, X } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import PillarIllustration from "@/components/visual/PillarIllustration";
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
  const base =
    "relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 bg-card text-sm font-bold";
  if (state === "done") {
    return (
      <span className={cn(base, "animate-pop-in border-safe bg-safe text-white")}>
        <Check className="h-4 w-4" aria-hidden="true" />
      </span>
    );
  }
  if (state === "running") {
    return (
      <span className={cn(base, "border-contract bg-contract-tint text-contract-ink")}>
        <Loader2 className="h-4 w-4 motion-safe:animate-spin" aria-hidden="true" />
      </span>
    );
  }
  if (state === "failed") {
    return (
      <span className={cn(base, "border-danger bg-danger text-white")}>
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
 * Contract Shield's steps while a contract is checked (NF-P2-010): a vertical timeline beside a
 * document being scanned. Driven by the live contract document, so a step is only "done" when
 * the backend has really moved past it.
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
  const doneCount = SCREEN_STEPS.filter((step) => states[step] === "done").length;

  return (
    <section
      aria-labelledby="contract-progress-title"
      className="card-surface card-edge grid gap-6 bg-gradient-to-br from-contract-tint via-card to-card p-5 md:grid-cols-[minmax(0,1fr)_minmax(0,14rem)] md:p-7"
    >
      <div className="space-y-5">
        <header className="space-y-1">
          <h2 id="contract-progress-title" className="text-lg font-bold tracking-tight">
            {t("contract.progress.title")}
          </h2>
          <p className="text-sm text-muted-foreground">{t("contract.progress.subtitle")}</p>
        </header>

        <div aria-hidden="true" className="h-1.5 overflow-hidden rounded-full bg-muted">
          <span
            className="block h-full rounded-full bg-gradient-to-r from-contract to-contract-soft transition-[width] duration-slow ease-out-soft"
            style={{ width: `${(doneCount / SCREEN_STEPS.length) * 100}%` }}
          />
        </div>

        <ol className="relative space-y-4">
          {/* The thread joining the step markers. */}
          <span
            aria-hidden="true"
            className="absolute bottom-4 left-4 top-4 w-0.5 -translate-x-1/2 bg-border"
          />
          {SCREEN_STEPS.map((step, index) => {
            const state = states[step];
            return (
              <li
                key={step}
                aria-current={state === "running" ? "step" : undefined}
                className="relative flex items-start gap-3"
              >
                <StepIcon state={state} number={index + 1} />
                <div className="min-w-0 pt-1">
                  <p
                    className={cn(
                      "text-sm",
                      state === "running" && "font-bold",
                      state === "waiting" && "text-muted-foreground",
                      state === "failed" && "font-bold text-danger-ink"
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
            className="space-y-4 rounded-xl border border-danger/30 bg-danger-tint p-4 text-danger-tint-ink"
          >
            <p className="text-sm font-bold">{t("contract.progress.failedTitle")}</p>
            <p className="text-sm">{t(failureKey)}</p>
            {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
          </div>
        )}
      </div>

      <div className="hidden self-center md:block">
        <PillarIllustration pillar="contract" />
      </div>
    </section>
  );
}

import { Check } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface Step {
  id: string;
  /** Already translated. */
  label: string;
}

export interface StepProgressProps {
  steps: readonly Step[];
  /** Zero-based index of the step the person is on. Steps before it are done. */
  currentIndex: number;
  /** Accessible name of the list, e.g. "Interview progress". */
  listLabel: string;
  /** Visible and spoken position, e.g. "Step 3 of 7: Income". Built by the caller so it can be
   * translated and can follow each language's word order. */
  progressLabel: string;
  /** Spoken after each step's name, e.g. "completed", "current step", "not started". */
  statusLabels: { done: string; current: string; upcoming: string };
  /** A control beside the position line, at its end (for example "Start over"). */
  action?: ReactNode;
  className?: string;
}

/** A row of numbered steps. Done, current and upcoming differ in icon and in spoken text, not
 * only in colour. Step names are drawn under the markers from the `sm` breakpoint up; on a
 * narrow screen they are visually hidden but still read out, and `progressLabel` below the row
 * names the current one. The names sit outside the row's flow, so a long one never squeezes the
 * line between markers. */
export default function StepProgress({
  steps,
  currentIndex,
  listLabel,
  progressLabel,
  statusLabels,
  action,
  className,
}: StepProgressProps) {
  return (
    <nav aria-label={listLabel} className={cn("w-full", className)}>
      <ol className="flex w-full items-center sm:mb-8">
        {steps.map((step, index) => {
          const state =
            index < currentIndex ? "done" : index === currentIndex ? "current" : "upcoming";
          const last = index === steps.length - 1;
          return (
            <li
              key={step.id}
              aria-current={state === "current" ? "step" : undefined}
              className={cn("flex items-center", !last && "flex-1")}
            >
              <span className="relative flex">
                <span
                  aria-hidden="true"
                  className={cn(
                    "flex h-7 w-7 items-center justify-center rounded-full border-2 text-xs font-bold",
                    state === "done" && "border-primary bg-primary text-primary-foreground",
                    state === "current" && "border-primary bg-card text-primary",
                    state === "upcoming" && "border-input bg-card text-muted-foreground"
                  )}
                >
                  {state === "done" ? <Check className="h-4 w-4" /> : index + 1}
                </span>
                <span
                  className={cn(
                    "sr-only sm:not-sr-only sm:absolute sm:start-1/2 sm:top-full sm:mt-1 sm:w-20",
                    "sm:-translate-x-1/2 sm:text-center sm:text-xs sm:font-semibold sm:leading-tight rtl:sm:translate-x-1/2",
                    state === "current" ? "sm:text-foreground" : "sm:text-muted-foreground"
                  )}
                >
                  {step.label}
                </span>
                <span className="sr-only">{statusLabels[state]}</span>
              </span>
              {!last && (
                <span
                  aria-hidden="true"
                  className={cn(
                    "mx-1 h-0.5 flex-1 rounded-full",
                    index < currentIndex ? "bg-primary" : "bg-border"
                  )}
                />
              )}
            </li>
          );
        })}
      </ol>
      {action ? (
        <div className="mt-1 flex items-center justify-between gap-3">
          <p className="text-xs font-semibold text-muted-foreground">{progressLabel}</p>
          {action}
        </div>
      ) : (
        <p className="mt-2 text-center text-xs font-semibold text-muted-foreground">
          {progressLabel}
        </p>
      )}
    </nav>
  );
}

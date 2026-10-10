import { GraduationCap, LayoutDashboard, ScanSearch, X, type LucideIcon } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { useFeatureFlags } from "@/hooks/useFeatureFlag";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { hasSeenTour, markTourSeen, type TourStep, tourSteps } from "@/utils/firstRunTour";
import { PILLAR_STYLES, type PillarKey } from "@/utils/pillars";

const FOCUSABLE = "button:not([disabled]), a[href]";

const STEP_LOOK: Record<TourStep, { icon: LucideIcon; pillar: PillarKey }> = {
  scam: { icon: ScanSearch, pillar: "scam" },
  coach: { icon: GraduationCap, pillar: "coach" },
  outro: { icon: LayoutDashboard, pillar: "remit" },
};

/**
 * The first-run tour (NF-HR-002): a short, skippable walk through the modules that are new for
 * this worker, shown once on the home dashboard. Skipping, Escape, the close button and the last
 * step all count as seen. A modal that keeps the keyboard inside it and hands focus back, like the
 * report sheet.
 */
function TourDialog({ steps, onClose }: { steps: TourStep[]; onClose: () => void }) {
  const { t } = useI18n();
  const ids = useId();
  const panel = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  const latestClose = useRef(onClose);
  useEffect(() => {
    latestClose.current = onClose;
  });

  const step = steps[index];
  const last = index === steps.length - 1;
  const { icon: Icon, pillar } = STEP_LOOK[step];

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();

    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        latestClose.current();
        return;
      }
      if (event.key !== "Tab" || panel.current === null) {
        return;
      }
      const items = panel.current.querySelectorAll<HTMLElement>(FOCUSABLE);
      const first = items[0];
      const final = items[items.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === panel.current)) {
        event.preventDefault();
        final?.focus();
      } else if (!event.shiftKey && active === final) {
        event.preventDefault();
        first?.focus();
      }
    }

    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
      opener?.focus?.();
    };
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-4"
      onClick={onClose}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={t("dashboard.tour.label")}
        aria-describedby={`${ids}-body`}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-md rounded-t-2xl border bg-card p-5 shadow-lg focus:outline-none sm:rounded-2xl"
      >
        <div className="flex items-start justify-between gap-3">
          <p className="pt-2 text-xs font-bold uppercase tracking-wide text-muted-foreground">
            {t("dashboard.tour.step", { current: index + 1, total: steps.length })}
          </p>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="-mr-2 -mt-1 h-11 w-11 shrink-0"
            onClick={onClose}
            aria-label={t("dashboard.tour.close")}
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </Button>
        </div>

        <div className="mt-2 flex items-start gap-4">
          <span
            className={cn(
              "flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl shadow-sm",
              PILLAR_STYLES[pillar].tile
            )}
          >
            <Icon className="h-6 w-6" aria-hidden="true" />
          </span>
          <div className="min-w-0 space-y-1.5">
            <h2 className="text-lg font-extrabold leading-snug">
              {t(`dashboard.tour.${step}.title`)}
            </h2>
            <p id={`${ids}-body`} className="text-sm text-muted-foreground">
              {t(`dashboard.tour.${step}.body`)}
            </p>
          </div>
        </div>

        <div className="mt-5 flex items-center justify-between gap-2">
          <div className="flex gap-1.5" aria-hidden="true">
            {steps.map((_, dot) => (
              <span
                key={dot}
                className={cn("h-1.5 w-6 rounded-full", dot === index ? "bg-primary" : "bg-muted")}
              />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {!last && (
              <Button type="button" variant="ghost" className="min-h-11" onClick={onClose}>
                {t("dashboard.tour.skip")}
              </Button>
            )}
            {index > 0 && (
              <Button
                type="button"
                variant="outline"
                className="min-h-11"
                onClick={() => setIndex(index - 1)}
              >
                {t("dashboard.tour.back")}
              </Button>
            )}
            <Button
              type="button"
              className="min-h-11 font-bold"
              onClick={() => (last ? onClose() : setIndex(index + 1))}
            >
              {last ? t("dashboard.tour.done") : t("dashboard.tour.next")}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Mounts the tour on the home dashboard when this worker has a module they have not seen
 * introduced and has not been through it in this browser. Renders nothing otherwise. */
export default function FirstRunTour() {
  const { user } = useAuth();
  const { flags, isLoading } = useFeatureFlags();
  const uid = user?.uid;
  const [closed, setClosed] = useState(false);
  const steps = tourSteps(flags);

  if (closed || isLoading || uid === undefined || steps.length === 0 || hasSeenTour(uid)) {
    return null;
  }

  function close() {
    if (uid !== undefined) {
      markTourSeen(uid);
    }
    setClosed(true);
  }

  return <TourDialog steps={steps} onClose={close} />;
}

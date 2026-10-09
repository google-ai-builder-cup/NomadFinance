import { History } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useUiLanguage } from "@/hooks/useUiLanguage";
import type { CoachStage } from "@/types/coach";
import { relativeTime } from "@/utils/relativeTime";

// The interview's steps, as the stepper shows them; `plan` is past the last one.
const STEPS = ["intro", "income", "obligations", "debt", "savings", "review"] as const;

export interface ResumeBannerProps {
  stage: CoachStage;
  /** When the worker last answered (`last_active` of the session). */
  lastActive: string;
  /** Carry on where it stopped: the banner goes away. */
  onContinue: () => void;
  /** Close this interview and start a new one. Asked about first: the answers go with it. */
  onStartOver: () => void;
}

/**
 * Shown when the worker comes back to an interview that is already under way: where it stopped
 * and how long ago, that the answers are saved, and the choice to carry on or to start over. Not
 * shown for a brand-new interview, and it goes at the worker's first answer.
 */
export default function ResumeBanner({
  stage,
  lastActive,
  onContinue,
  onStartOver,
}: ResumeBannerProps) {
  const { t } = useI18n("coach");
  const language = useUiLanguage();
  const [confirming, setConfirming] = useState(false);

  const index = Math.max(STEPS.indexOf(stage as (typeof STEPS)[number]), 0);
  const position = t("stage.position", {
    current: index + 1,
    total: STEPS.length,
    name: t(`stage.${STEPS[index]}`),
  });
  const when = relativeTime(lastActive, language);

  return (
    <section
      aria-label={t("resume.label")}
      className="flex shrink-0 items-start gap-3 rounded-2xl border bg-card p-3"
    >
      <History className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
      <div className="min-w-0 flex-1 space-y-2">
        {confirming ? (
          <>
            <p className="text-sm font-semibold">{t("resume.confirm")}</p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" className="min-h-11" onClick={onStartOver}>
                {t("resume.confirmYes")}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="min-h-11"
                onClick={() => setConfirming(false)}
              >
                {t("resume.confirmNo")}
              </Button>
            </div>
          </>
        ) : (
          <>
            <p className="text-sm font-bold">{t("resume.label")}</p>
            <p className="text-sm text-muted-foreground">
              {position}
              {". "}
              {when !== null && `${t("resume.lastSeen", { when })} `}
              {t("resume.saved")}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" className="min-h-11" onClick={onContinue}>
                {t("resume.continue")}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="min-h-11"
                onClick={() => setConfirming(true)}
              >
                {t("chat.error.restart")}
              </Button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}

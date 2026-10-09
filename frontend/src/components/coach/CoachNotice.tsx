import { CircleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useFocusOnMount } from "@/hooks/useFocusOnMount";
import { useI18n } from "@/hooks/useI18n";
import type { CoachFailure } from "@/types/coach";
import { coachErrorView } from "@/utils/coachErrors";

export interface CoachNoticeProps {
  failure: CoachFailure;
  onRetry: () => void;
  /** Start a new interview, offered when this one cannot go on. */
  onRestart: () => void;
  restarting?: boolean;
}

/** Why a turn did not go through, in plain words, with the one button that can help. */
export default function CoachNotice({ failure, onRetry, onRestart, restarting }: CoachNoticeProps) {
  const { t } = useI18n("coach");
  const view = coachErrorView(failure);
  const ref = useFocusOnMount<HTMLDivElement>();

  return (
    <div
      ref={ref}
      role="alert"
      tabIndex={-1}
      className="flex shrink-0 items-start gap-3 rounded-2xl border border-destructive/40 bg-destructive/5 p-3 focus:outline-none"
    >
      <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-danger-ink" aria-hidden="true" />
      <div className="min-w-0 flex-1 space-y-2">
        <p className="text-sm font-semibold">{t(view.messageKey, { seconds: view.waitSeconds })}</p>
        {view.action !== "none" && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="min-h-11"
            disabled={restarting}
            onClick={view.action === "restart" ? onRestart : onRetry}
          >
            {view.action === "restart" ? t("chat.error.restart") : t("common.retry")}
          </Button>
        )}
      </div>
    </div>
  );
}

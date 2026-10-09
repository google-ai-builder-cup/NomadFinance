import { CircleCheck } from "lucide-react";
import { Link } from "react-router-dom";

import AnswerPanel from "@/components/coach/AnswerPanel";
import ChatLog from "@/components/coach/ChatLog";
import CoachNotice from "@/components/coach/CoachNotice";
import StageStepper from "@/components/coach/StageStepper";
import { Button } from "@/components/ui/button";
import { useCoachChat, type CoachChatTiming } from "@/hooks/useCoachChat";
import { useFocusOnMount } from "@/hooks/useFocusOnMount";
import { useI18n } from "@/hooks/useI18n";
import { useUiLanguage } from "@/hooks/useUiLanguage";
import type { CoachSessionStart } from "@/types/coach";
import { toFailure } from "@/utils/coachErrors";

export interface CoachChatProps {
  session: CoachSessionStart;
  /** Close this interview and start a new one. */
  onRestart: () => void;
  restarting?: boolean;
  /** Why the last restart failed, if it did. */
  restartError?: unknown;
  timing?: CoachChatTiming;
}

/** The interview: the steps, the conversation, and the place to answer. Mounted once per
 * session (the page keys it by the session's id), so a new interview starts from nothing. */
export default function CoachChat({
  session,
  onRestart,
  restarting,
  restartError,
  timing,
}: CoachChatProps) {
  const { t } = useI18n("coach");
  const language = useUiLanguage();
  const { state, busy, send, retry } = useCoachChat(session, timing, language);
  // A restart that failed is shown the same way as a turn that failed.
  const failure = restartError ? toFailure(restartError) : state.failure;
  const confirmed = state.stage === "plan";
  // The answer panel is gone once the answers are confirmed; focus goes to what replaces it.
  const confirmedRef = useFocusOnMount<HTMLDivElement>(confirmed);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <StageStepper stage={state.stage} />
      <ChatLog
        lines={state.lines}
        draft={state.draft}
        announcement={state.announcement}
        language={session.language}
        footer={
          failure && (
            <CoachNotice
              failure={failure}
              onRetry={restartError ? onRestart : retry}
              onRestart={onRestart}
              restarting={restarting}
            />
          )
        }
      />
      {confirmed ? (
        <div
          ref={confirmedRef}
          tabIndex={-1}
          className="flex shrink-0 items-start gap-3 rounded-2xl border bg-card p-4 focus:outline-none"
        >
          <CircleCheck className="mt-0.5 h-5 w-5 shrink-0 text-safe-ink" aria-hidden="true" />
          <div className="min-w-0 flex-1 space-y-2">
            <p className="text-sm font-bold">{t("confirmed.title")}</p>
            <p className="text-sm text-muted-foreground">{t("confirmed.description")}</p>
            <Button asChild variant="outline" className="min-h-11">
              <Link to="/dashboard">{t("confirmed.backToDashboard")}</Link>
            </Button>
          </div>
        </div>
      ) : (
        <AnswerPanel
          stage={state.stage}
          slot={state.nextSlot}
          slots={state.slots}
          busy={busy}
          onSend={send}
          language={language}
        />
      )}
    </div>
  );
}

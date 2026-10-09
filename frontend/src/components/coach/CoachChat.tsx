import { CircleCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import AnswerPanel from "@/components/coach/AnswerPanel";
import ChatLog from "@/components/coach/ChatLog";
import CoachNotice from "@/components/coach/CoachNotice";
import OfflineNotice from "@/components/coach/OfflineNotice";
import ResumeBanner from "@/components/coach/ResumeBanner";
import ScoreScreen from "@/components/coach/score/ScoreScreen";
import StageStepper from "@/components/coach/StageStepper";
import { Button } from "@/components/ui/button";
import { useCoachChat, type CoachChatTiming } from "@/hooks/useCoachChat";
import { CoachDraftProvider } from "@/hooks/useCoachDraft";
import { useFocusOnMount } from "@/hooks/useFocusOnMount";
import { useI18n } from "@/hooks/useI18n";
import { useUiLanguage } from "@/hooks/useUiLanguage";
import { removeEntry } from "@/lib/coachOutboxStore";
import type { CoachSessionStart } from "@/types/coach";
import { clearDraft } from "@/utils/coachDraft";
import { toFailure } from "@/utils/coachErrors";

export interface CoachChatProps {
  session: CoachSessionStart;
  /** Close this interview and start a new one. */
  onRestart: () => void;
  restarting?: boolean;
  /** Why the last restart failed, if it did. */
  restartError?: unknown;
  timing?: CoachChatTiming;
  /** The signed-in person. With it, what they type and an answer sent without a connection are
   * kept on this phone (NF-FC-019); without it, nothing is kept (tests). */
  uid?: string;
}

/** The interview: the steps, the conversation, and the place to answer. Mounted once per
 * session (the page keys it by the session's id), so a new interview starts from nothing. */
export default function CoachChat({
  session,
  onRestart,
  restarting,
  restartError,
  timing,
  uid,
}: CoachChatProps) {
  const { t } = useI18n("coach");
  const language = useUiLanguage();
  const { state, busy, send, retry, restoring } = useCoachChat(session, timing, language, uid);
  // An answer waiting for a connection locks the panel like a running turn: the coach's next
  // question depends on it.
  const locked = busy || state.queued || restoring;
  const question = `${state.stage}:${state.nextSlot}`;
  const draftScope = useMemo(
    () => (uid === undefined ? null : { uid, sessionId: session.id, question }),
    [uid, session.id, question]
  );
  // Coming back to an interview that is under way: say where it stopped, until the worker carries
  // on. Not for a new interview, and not for one whose answers are already confirmed.
  const [resuming, setResuming] = useState(
    session.resumed &&
      session.status === "active" &&
      session.messages.length > 0 &&
      session.stage !== "plan"
  );
  // A restart that failed is shown the same way as a turn that failed.
  const failure = restartError ? toFailure(restartError) : state.failure;
  const confirmed = state.stage === "plan";
  // The answer panel is gone once the answers are confirmed; focus goes to what replaces it.
  const confirmedRef = useFocusOnMount<HTMLDivElement>(confirmed);

  // Starting over takes the answers with it: so does what was kept for them on this phone.
  function startOver() {
    if (uid !== undefined) {
      void removeEntry(session.id);
      clearDraft(uid);
    }
    onRestart();
  }

  const showBanner =
    resuming && !restoring && !state.queued && state.failure === null && !confirmed;
  const panel = (
    <AnswerPanel
      stage={state.stage}
      slot={state.nextSlot}
      slots={state.slots}
      busy={locked}
      onSend={(text) => {
        setResuming(false);
        // The answer is on its way: what was kept for it (the box, its amount, that the box was
        // open) is not needed, and must not come back for a question that is already answered.
        if (uid !== undefined) {
          clearDraft(uid);
        }
        send(text);
      }}
      language={language}
    />
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {showBanner && (
        <ResumeBanner
          stage={state.stage}
          lastActive={session.last_active}
          onContinue={() => setResuming(false)}
          onStartOver={startOver}
        />
      )}
      <StageStepper stage={state.stage} />
      {/* Once the answers are confirmed the score takes the room: the conversation shrinks to its
          last lines, still there to scroll back through. */}
      <div
        className={confirmed ? "flex max-h-16 shrink-0 flex-col" : "flex min-h-0 flex-1 flex-col"}
      >
        <ChatLog
          lines={state.lines}
          draft={state.draft}
          announcement={state.announcement}
          language={session.language}
          footer={
            failure ? (
              <CoachNotice
                failure={failure}
                onRetry={restartError ? startOver : retry}
                onRestart={startOver}
                restarting={restarting}
              />
            ) : (
              state.queued && <OfflineNotice onSendNow={retry} />
            )
          }
        />
      </div>
      {confirmed ? (
        <div
          ref={confirmedRef}
          tabIndex={-1}
          className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain rounded-2xl border bg-card p-4 focus:outline-none"
        >
          <div className="flex items-start gap-3">
            <CircleCheck className="mt-0.5 h-5 w-5 shrink-0 text-safe-ink" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold">{t("confirmed.title")}</p>
              <p className="text-sm text-muted-foreground">{t("confirmed.description")}</p>
            </div>
          </div>
          <ScoreScreen sessionId={session.id} language={language} />
          <Button asChild variant="outline" className="min-h-11">
            <Link to="/dashboard">{t("confirmed.backToDashboard")}</Link>
          </Button>
        </div>
      ) : draftScope === null ? (
        panel
      ) : (
        <CoachDraftProvider scope={draftScope}>{panel}</CoachDraftProvider>
      )}
    </div>
  );
}

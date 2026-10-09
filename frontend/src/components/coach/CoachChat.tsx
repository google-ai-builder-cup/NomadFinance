import { CircleCheck } from "lucide-react";
import { useId, useLayoutEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import AnswerPanel from "@/components/coach/AnswerPanel";
import ChatLog from "@/components/coach/ChatLog";
import CoachNotice from "@/components/coach/CoachNotice";
import KnownCard from "@/components/coach/KnownCard";
import NewInterviewButton, { NewInterviewConfirm } from "@/components/coach/NewInterviewButton";
import OfflineNotice from "@/components/coach/OfflineNotice";
import RecapTable from "@/components/coach/RecapTable";
import ResumeBanner from "@/components/coach/ResumeBanner";
import ScoreScreen from "@/components/coach/score/ScoreScreen";
import StageStepper from "@/components/coach/StageStepper";
import { Button } from "@/components/ui/button";
import { useCoachChat, type CoachChatTiming } from "@/hooks/useCoachChat";
import { CoachDraftProvider } from "@/hooks/useCoachDraft";
import { useFocusOnMount } from "@/hooks/useFocusOnMount";
import { useI18n } from "@/hooks/useI18n";
import { useNewInterviewAsk } from "@/hooks/useNewInterviewAsk";
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
  /** Told when the interview reaches the review or the plan (and when it leaves them), so the page
   * can stop fixing its own height: from there it is a page to scroll, not a chat to fit. */
  onFlowChange?: (flowing: boolean) => void;
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
  onFlowChange,
  uid,
}: CoachChatProps) {
  const { t } = useI18n("coach");
  const language = useUiLanguage();
  const headingId = useId();
  const { state, busy, send, retry, restoring, adoptKnown } = useCoachChat(
    session,
    timing,
    language,
    uid
  );
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
  const restartFailure = restartError ? toFailure(restartError) : null;
  const failure = restartFailure ?? state.failure;
  // What the Coach already knows, waiting for the worker before the first question.
  const [offer, setOffer] = useState(session.known ?? null);
  const confirmed = state.stage === "plan";
  // The answer panel is gone once the answers are confirmed; focus goes to what replaces it.
  const confirmedRef = useFocusOnMount<HTMLElement>(confirmed);
  // The review (a table to read) and the finished screen (a score to read) are pages that grow;
  // before them the conversation scrolls inside a box that fits the window.
  const flowing = confirmed || state.stage === "review" || offer !== null;
  useLayoutEffect(() => onFlowChange?.(flowing), [flowing, onFlowChange]);

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

  // An answer on its way, whether typed, picked, or a row of the review table: what was kept for
  // it (the box, its amount, that the box was open) is not needed, and must not come back for a
  // question that is already answered.
  function submit(text: string) {
    setResuming(false);
    if (uid !== undefined) {
      clearDraft(uid);
    }
    send(text);
  }

  const panel = (
    <AnswerPanel
      stage={state.stage}
      slot={state.nextSlot}
      slots={state.slots}
      busy={locked}
      onSend={submit}
      language={language}
    />
  );
  const log = (
    <ChatLog
      lines={state.lines}
      draft={state.draft}
      announcement={state.announcement}
      language={session.language}
      footer={
        failure && !confirmed ? (
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
  );
  const answerPanel =
    draftScope === null ? (
      panel
    ) : (
      <CoachDraftProvider scope={draftScope}>{panel}</CoachDraftProvider>
    );
  const banner = showBanner && (
    <ResumeBanner
      stage={state.stage}
      lastActive={session.last_active}
      onContinue={() => setResuming(false)}
      onStartOver={startOver}
    />
  );
  // The welcome-back banner offers the same choice, so the button waits until it is gone.
  const again = useNewInterviewAsk();
  const newInterview = !showBanner && !again.asking && (
    <NewInterviewButton onClick={again.ask} focusOnMount={again.returned} />
  );
  const confirmNewInterview = again.asking && (
    <NewInterviewConfirm onRestart={startOver} onCancel={again.cancel} restarting={restarting} />
  );

  // Before the first question: what the profile, the contract and Financial Identity already
  // answer, for the worker to keep or change.
  if (offer !== null) {
    return (
      <div className="flex flex-col gap-3 pb-2">
        <StageStepper stage={state.stage} />
        <KnownCard
          sessionId={session.id}
          items={offer.items}
          onApplied={(applied) => {
            setOffer(null);
            adoptKnown(applied);
          }}
          onRestart={startOver}
          restarting={restarting}
        />
      </div>
    );
  }

  // The finished screen: the score comes first, and the whole conversation stays below it in a
  // box tall enough to read.
  if (confirmed) {
    return (
      <div className="flex flex-col gap-4 pb-2">
        <StageStepper stage={state.stage} />
        <section
          ref={confirmedRef}
          tabIndex={-1}
          aria-labelledby={`${headingId}-done`}
          className="space-y-4 rounded-2xl border bg-card p-4 focus:outline-none"
        >
          <div className="flex items-start gap-3">
            <CircleCheck className="mt-0.5 h-5 w-5 shrink-0 text-safe-ink" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <h2 id={`${headingId}-done`} className="text-sm font-bold">
                {t("confirmed.title")}
              </h2>
              <p className="text-sm text-muted-foreground">{t("confirmed.description")}</p>
            </div>
          </div>
          <ScoreScreen sessionId={session.id} language={language} />
          {restartFailure && (
            <CoachNotice
              failure={restartFailure}
              onRetry={startOver}
              onRestart={startOver}
              restarting={restarting}
            />
          )}
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline" className="min-h-11">
              <Link to="/dashboard">{t("confirmed.backToDashboard")}</Link>
            </Button>
            {!again.asking && (
              <NewInterviewButton onClick={again.ask} focusOnMount={again.returned} />
            )}
          </div>
          {confirmNewInterview}
        </section>
        <section aria-labelledby={`${headingId}-log`} className="space-y-2">
          <h2 id={`${headingId}-log`} className="text-sm font-extrabold">
            {t("confirmed.conversation")}
          </h2>
          <div className="flex h-[min(32rem,70dvh)] flex-col">{log}</div>
        </section>
      </div>
    );
  }

  // The review: the conversation in a box of its own, then every answer in a table the whole
  // height of which can be read, then the question.
  if (flowing) {
    return (
      <div className="flex flex-col gap-3 pb-2">
        {banner}
        <StageStepper stage={state.stage} action={newInterview} />
        {!showBanner && confirmNewInterview}
        <div className="flex h-[min(20rem,40dvh)] flex-col">{log}</div>
        <RecapTable slots={state.slots} busy={locked} onChange={submit} />
        {answerPanel}
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {banner}
      <StageStepper stage={state.stage} action={newInterview} />
      {!showBanner && confirmNewInterview}
      <div className="flex min-h-0 flex-1 flex-col">{log}</div>
      {answerPanel}
    </div>
  );
}

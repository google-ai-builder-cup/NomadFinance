import { ArrowDown } from "lucide-react";
import type { ReactNode } from "react";

import ChatBubble from "@/components/common/ChatBubble";
import { useI18n } from "@/hooks/useI18n";
import { useStickToBottom } from "@/hooks/useStickToBottom";
import type { ChatLine } from "@/utils/coachChatState";

export interface ChatLogProps {
  lines: readonly ChatLine[];
  /** The reply that is arriving; null when no turn is running. */
  draft: string | null;
  /** The last finished coach reply, read out once; the chat empties it a few seconds later. */
  announcement: string;
  language: string;
  /** Shown after the last line, inside the scrolling box: a notice about the turn that failed. It
   * stays with the conversation instead of taking room from it. */
  footer?: ReactNode;
}

/** The conversation. It scrolls inside a fixed-height box, so a reply growing line by line moves
 * nothing else on the page. */
export default function ChatLog({ lines, draft, announcement, language, footer }: ChatLogProps) {
  const { t } = useI18n("coach");
  const { ref, onScroll, away, jumpToLatest } = useStickToBottom<HTMLDivElement>(
    `${lines.length}:${draft ?? ""}:${footer ? "notice" : ""}`
  );

  return (
    <div className="relative min-h-0 flex-1">
      {/* Not a live region (`aria-live="off"`): a streamed reply would be read word by word.
          The status region below says the finished reply once. */}
      <div
        ref={ref}
        onScroll={onScroll}
        role="log"
        aria-live="off"
        aria-label={t("chat.log")}
        lang={language}
        // Focusable so the keyboard can scroll it.
        tabIndex={0}
        // `relative` makes this box the anchor of the screen-reader-only speaker labels in the
        // bubbles (absolutely positioned). Without it they are placed against a box outside the
        // scroller, below the visible area, and every message adds to the page's height.
        className="relative flex h-full flex-col gap-3 overflow-y-auto overscroll-contain rounded-2xl border bg-card p-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {lines.map((line) => (
          <ChatBubble
            key={line.id}
            role={line.role === "coach" ? "assistant" : "user"}
            speakerLabel={line.role === "coach" ? t("chat.coachSays") : t("chat.youSaid")}
            failed={line.failed}
            failedLabel={t("chat.notSent")}
            // The notice below the last line is the alert: it says why, and takes focus.
            announceFailed={false}
            pending={line.queued}
            pendingLabel={t("offline.waiting")}
          >
            {line.text}
          </ChatBubble>
        ))}
        {draft !== null && (
          <ChatBubble
            role="assistant"
            streaming
            typingLabel={t("chat.typing")}
            speakerLabel={t("chat.coachSays")}
          >
            {draft}
          </ChatBubble>
        )}
        {footer}
      </div>
      {away && (
        <button
          type="button"
          onClick={jumpToLatest}
          className="absolute bottom-3 end-3 flex min-h-11 items-center gap-1.5 rounded-full border bg-card px-4 text-sm font-bold shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ArrowDown className="h-4 w-4" aria-hidden="true" />
          {t("chat.latest")}
        </button>
      )}
      <div role="status" className="sr-only">
        {announcement}
      </div>
    </div>
  );
}

import { Clock, RotateCw } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ChatBubbleProps {
  /** `assistant` sits at the start of the line, `user` at the end (mirrored in right-to-left). */
  role: "assistant" | "user";
  children?: ReactNode;
  /** True while the reply is still arriving: shows a caret, or three dots when nothing came yet. */
  streaming?: boolean;
  /** Read out while streaming, e.g. "The coach is typing". */
  typingLabel?: string;
  /** Read out before the message so a screen reader says who spoke, e.g. "You said:". */
  speakerLabel?: string;
  timeLabel?: string;
  /** The message did not go through: shows `failedLabel` and a retry button. */
  failed?: boolean;
  failedLabel?: string;
  retryLabel?: string;
  onRetry?: () => void;
  /** The message is kept on the device and goes when the connection is back (not a failure). */
  pending?: boolean;
  pendingLabel?: string;
  className?: string;
}

/** One chat message. It carries no live-region role of its own: the list that holds the bubbles
 * is the `role="log"`, so a streamed reply is announced once, when `streaming` ends. */
export default function ChatBubble({
  role,
  children,
  streaming = false,
  typingLabel,
  speakerLabel,
  timeLabel,
  failed = false,
  failedLabel,
  retryLabel,
  onRetry,
  pending = false,
  pendingLabel,
  className,
}: ChatBubbleProps) {
  const fromUser = role === "user";
  const empty = streaming && !children;
  return (
    <div
      data-role={role}
      aria-busy={streaming || undefined}
      className={cn("flex w-full", fromUser ? "justify-end" : "justify-start", className)}
    >
      <div
        className={cn("flex max-w-[85%] flex-col gap-1", fromUser ? "items-end" : "items-start")}
      >
        <div
          className={cn(
            "break-words whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            fromUser
              ? "rounded-ee-md bg-primary text-primary-foreground"
              : "rounded-es-md bg-muted text-foreground",
            failed && "border border-destructive"
          )}
        >
          {speakerLabel && <span className="sr-only">{speakerLabel} </span>}
          {empty ? (
            <span className="flex h-5 items-center gap-1" aria-hidden="true">
              {[0, 150, 300].map((delay) => (
                <span
                  key={delay}
                  className="h-1.5 w-1.5 rounded-full bg-current opacity-60 motion-safe:animate-pulse"
                  style={{ animationDelay: `${delay}ms` }}
                />
              ))}
            </span>
          ) : (
            children
          )}
          {streaming && !empty && (
            <span
              aria-hidden="true"
              className="ms-0.5 inline-block h-4 w-0.5 translate-y-0.5 bg-current motion-safe:animate-pulse"
            />
          )}
          {streaming && typingLabel && <span className="sr-only">{typingLabel}</span>}
        </div>
        {(timeLabel || failed || pending) && (
          <div className="flex items-center gap-2 px-1 text-xs text-muted-foreground">
            {timeLabel && <span>{timeLabel}</span>}
            {pending && pendingLabel && (
              <span className="flex items-center gap-1 font-semibold">
                <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                {pendingLabel}
              </span>
            )}
            {failed && failedLabel && (
              <span role="alert" className="font-semibold text-danger-ink">
                {failedLabel}
              </span>
            )}
            {failed && onRetry && retryLabel && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 gap-1 px-2 text-xs font-bold"
                onClick={onRetry}
              >
                <RotateCw className="h-3.5 w-3.5" aria-hidden="true" />
                {retryLabel}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

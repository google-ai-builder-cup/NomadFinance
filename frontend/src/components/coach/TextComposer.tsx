import { SendHorizontal } from "lucide-react";
import { useId, useState, type FormEvent, type KeyboardEvent } from "react";

import { FIELD_CLASS } from "@/components/coach/fieldClasses";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { MAX_ANSWER_CHARS } from "@/utils/coachInput";

// Show the counter only when the end is near, so the box is not cluttered for a short answer.
const COUNTER_FROM = Math.floor(MAX_ANSWER_CHARS * 0.8);

export interface TextComposerProps {
  busy: boolean;
  onSend: (text: string) => void;
}

/**
 * The free-text answer. It stays editable while the coach replies and only the send button waits:
 * a field that is disabled gives up focus, the phone's keyboard closes, and the page jumps. A
 * message over the limit is not cut; the worker is told and decides (the server refuses it, 422).
 */
export default function TextComposer({ busy, onSend }: TextComposerProps) {
  const { t } = useI18n("coach");
  const id = useId();
  const [text, setText] = useState("");
  const count = text.trim().length;
  const tooLong = count > MAX_ANSWER_CHARS;
  const canSend = count > 0 && !tooLong && !busy;

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (canSend) {
      onSend(text.trim());
      setText("");
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends and Shift+Enter adds a line, as in a chat. Not while an input method (Hindi,
    // Bengali) is still composing a word, when Enter confirms the word instead.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form onSubmit={submit} className="space-y-1" noValidate>
      <div className="flex items-end gap-2">
        <label htmlFor={`${id}-text`} className="sr-only">
          {t("input.textLabel")}
        </label>
        <textarea
          id={`${id}-text`}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          enterKeyHint="send"
          placeholder={t("input.textPlaceholder")}
          aria-invalid={tooLong}
          aria-describedby={count >= COUNTER_FROM ? `${id}-count` : undefined}
          className={cn(FIELD_CLASS, "max-h-32 resize-none py-2.5")}
        />
        <Button
          type="submit"
          size="icon"
          className="h-11 w-11 shrink-0 rounded-xl"
          disabled={!canSend}
          aria-label={t("input.send")}
        >
          <SendHorizontal className="h-5 w-5" aria-hidden="true" />
        </Button>
      </div>
      {count >= COUNTER_FROM && (
        <p
          id={`${id}-count`}
          role={tooLong ? "alert" : undefined}
          className={cn(
            "text-xs tabular-nums",
            tooLong ? "font-bold text-danger-ink" : "text-muted-foreground"
          )}
        >
          {tooLong ? t("input.tooLong", { max: MAX_ANSWER_CHARS }) : null}{" "}
          {t("input.counter", { count, max: MAX_ANSWER_CHARS })}
        </p>
      )}
    </form>
  );
}

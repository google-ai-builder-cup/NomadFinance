import { Mic, SendHorizontal, Square } from "lucide-react";
import { useEffect, useId, useRef, type FormEvent, type KeyboardEvent } from "react";

import { FIELD_CLASS } from "@/components/coach/fieldClasses";
import { Button } from "@/components/ui/button";
import { useDraftFields } from "@/hooks/useCoachDraft";
import { useI18n } from "@/hooks/useI18n";
import { useSpeechInput } from "@/hooks/useSpeechInput";
import { cn } from "@/lib/utils";
import { MAX_ANSWER_CHARS } from "@/utils/coachInput";
import { appendDictation } from "@/utils/voiceInput";
import type { LanguageCode } from "@/types/enums";

// Show the counter only when the end is near, so the box is not cluttered for a short answer.
const COUNTER_FROM = Math.floor(MAX_ANSWER_CHARS * 0.8);

export interface TextComposerProps {
  busy: boolean;
  onSend: (text: string) => void;
  /** The coach's language: it decides whether the microphone is offered. */
  language?: LanguageCode;
  /** Open already listening (the microphone was pressed before the box was here). */
  listenOnOpen?: boolean;
}

/**
 * The free-text answer. It stays editable while the coach replies and only the send button waits:
 * a field that is disabled gives up focus, the phone's keyboard closes, and the page jumps. A
 * message over the limit is not cut; the worker is told and decides (the server refuses it, 422).
 *
 * Where the browser can recognise speech in the coach's language (English, Hindi, Indonesian),
 * a microphone fills the box with what was said. It never sends: the worker reads it first.
 */
export default function TextComposer({
  busy,
  onSend,
  language = "en",
  listenOnOpen = false,
}: TextComposerProps) {
  const { t } = useI18n("coach");
  const id = useId();
  // Kept as a draft, so what was typed comes back after a reload (NF-FC-019).
  const [{ text }, change] = useDraftFields("text", { text: "" });
  const setText = (value: string) => change({ text: value });
  const count = text.trim().length;
  const tooLong = count > MAX_ANSWER_CHARS;
  const canSend = count > 0 && !tooLong && !busy;
  const voice = useSpeechInput(language);
  // What was in the box when the microphone was pressed: the words heard are added after it.
  const typedBefore = useRef("");

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (canSend) {
      voice.cancel();
      onSend(text.trim());
      setText("");
    }
  }

  function toggleVoice() {
    if (voice.listening) {
      voice.stop();
      return;
    }
    typedBefore.current = text;
    voice.start((heard) => setText(appendDictation(typedBefore.current, heard)));
  }

  useEffect(() => {
    if (listenOnOpen && voice.available) {
      toggleVoice();
    }
    // Once, when the box opens from the microphone on the helper; later toggles are the worker's.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
        {voice.available && (
          <Button
            type="button"
            size="icon"
            variant={voice.listening ? "default" : "outline"}
            className="h-11 w-11 shrink-0 rounded-xl"
            onClick={toggleVoice}
            aria-pressed={voice.listening}
            aria-label={voice.listening ? t("input.voiceStop") : t("input.voiceStart")}
          >
            {voice.listening ? (
              <Square className="h-4 w-4 fill-current" aria-hidden="true" />
            ) : (
              <Mic className="h-5 w-5" aria-hidden="true" />
            )}
          </Button>
        )}
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
      {/* One live region for the microphone: what is happening, or why it stopped. The note on
          where the voice goes is shown while it is listening, when it matters. */}
      <p role="status" className="min-h-0 text-xs text-muted-foreground empty:hidden">
        {voice.listening
          ? `${t("input.voiceListening")} ${t("input.voicePrivacy")}`
          : voice.problem
            ? t(`input.voiceProblem.${voice.problem}`)
            : null}
      </p>
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

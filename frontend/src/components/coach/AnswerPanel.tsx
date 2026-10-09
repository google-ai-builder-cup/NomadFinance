import { Keyboard, ListChecks, Mic } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties } from "react";

import QuickReplyChips from "@/components/common/QuickReplyChips";
import MoneyField from "@/components/coach/MoneyField";
import { CountField, DateField, InterestField } from "@/components/coach/SimpleFields";
import TextComposer from "@/components/coach/TextComposer";
import { Button } from "@/components/ui/button";
import { useDraftFields } from "@/hooks/useCoachDraft";
import { useI18n } from "@/hooks/useI18n";
import type { CoachSlot, CoachStage } from "@/types/coach";
import type { LanguageCode } from "@/types/enums";
import { answerInputFor, defaultCurrency, type AnswerInput } from "@/utils/coachInput";
import { isVoiceAvailable } from "@/utils/voiceInput";

export interface AnswerPanelProps {
  stage: CoachStage;
  slot: CoachSlot | null;
  /** Answers so far (bare values), for the currency to offer first. */
  slots: Partial<Record<CoachSlot, unknown>>;
  /** A reply is arriving: nothing more can be sent yet. */
  busy: boolean;
  onSend: (text: string) => void;
  /** The coach's language, for the microphone. */
  language?: LanguageCode;
}

// The label key of each chip, by set. Job types reuse the onboarding strings (all six languages).
const CHOICE_KEY: Record<Extract<AnswerInput, { kind: "choice" }>["set"], string> = {
  country: "input.country",
  job: "onboarding.jobTypes",
  bank: "input.bank",
  review: "input.review",
};

// When the answers are taller than the panel (seven kinds of work), a soft shadow on the edge that
// has more behind it shows there is more to scroll to; it disappears at the end. CSS only: the
// two white covers scroll with the content and hide the two shadows, which stay put.
const MORE_BELOW: CSSProperties = {
  background:
    "linear-gradient(hsl(var(--card)) 30%, transparent) center top / 100% 24px no-repeat local, " +
    "linear-gradient(transparent, hsl(var(--card)) 70%) center bottom / 100% 24px no-repeat local, " +
    "radial-gradient(farthest-side at 50% 0, hsl(var(--foreground) / 0.2), transparent) center top / 100% 10px no-repeat scroll, " +
    "radial-gradient(farthest-side at 50% 100%, hsl(var(--foreground) / 0.2), transparent) center bottom / 100% 10px no-repeat scroll, " +
    "hsl(var(--card))",
};

/**
 * Where the worker answers. The coach says which question is next, and the panel offers the
 * fitting helper: tap a chip, fill an amount, pick a date. "Type my own answer" is always there.
 * Whatever the helper makes is sent as text, exactly as if it had been typed.
 */
export default function AnswerPanel({
  stage,
  slot,
  slots,
  busy,
  onSend,
  language,
}: AnswerPanelProps) {
  const { t } = useI18n("coach");
  const input = answerInputFor(stage, slot);
  // Whether the answer box replaces the helper. Kept with the draft, so a worker who was typing
  // finds the box (and what was in it) again after a reload.
  const [choice, changeChoice] = useDraftFields("panel", { typing: "" }, `${stage}:${slot}`);
  const typing = choice.typing === "1";
  const setTyping = (value: boolean | ((was: boolean) => boolean)) =>
    changeChoice({ typing: (typeof value === "function" ? value(typing) : value) ? "1" : "" });
  // The microphone was pressed on a helper: the answer box opens already listening.
  const [speaking, setSpeaking] = useState(false);
  const voiceReady = isVoiceAvailable(language ?? "en");
  const [question, setQuestion] = useState(`${stage}:${slot}`);
  const panel = useRef<HTMLDivElement>(null);

  // A new question starts with its helper again (the draft hook drops the choice of typing with
  // the question); a clarifying turn (same question) keeps it.
  if (question !== `${stage}:${slot}`) {
    setQuestion(`${stage}:${slot}`);
    setSpeaking(false);
  }

  const asText = input.kind === "text" || typing;

  // The control the worker just used is gone when the next question's helper replaces it, and
  // focus falls back to the top of the page: a keyboard user would have to Tab through everything
  // again, and a screen reader says nothing. So when a turn ends and focus is lost, it comes to
  // the panel (not into a field: that would open the phone's keyboard unasked). Focus the worker
  // put elsewhere, or the notice that takes it, is left alone.
  const wasBusy = useRef(busy);
  useEffect(() => {
    if (wasBusy.current && !busy && document.activeElement === document.body) {
      panel.current?.focus({ preventScroll: true });
    }
    wasBusy.current = busy;
  }, [busy]);

  return (
    <div
      ref={panel}
      role="group"
      aria-label={t("input.panel")}
      tabIndex={-1}
      className="max-h-[50%] shrink-0 space-y-2 overflow-y-auto overscroll-contain rounded-2xl border bg-card p-3 focus:outline-none"
      style={MORE_BELOW}
    >
      {asText ? (
        <TextComposer busy={busy} onSend={onSend} language={language} listenOnOpen={speaking} />
      ) : input.kind === "choice" ? (
        <QuickReplyChips
          groupLabel={t("input.suggestions")}
          options={input.ids.map((id) => ({ id, label: t(`${CHOICE_KEY[input.set]}.${id}`) }))}
          disabled={busy}
          onSelect={(option) => onSend(option.label)}
        />
      ) : input.kind === "money" ? (
        <MoneyField
          periods={input.periods}
          canBeNone={input.canBeNone}
          defaultCurrency={defaultCurrency(slots)}
          busy={busy}
          onSend={onSend}
        />
      ) : input.kind === "count" ? (
        <CountField busy={busy} onSend={onSend} />
      ) : input.kind === "interest" ? (
        <InterestField busy={busy} onSend={onSend} />
      ) : (
        <DateField busy={busy} onSend={onSend} />
      )}
      {input.kind !== "text" && (
        <div className="flex gap-2">
          <Button
            type="button"
            variant="ghost"
            className="min-h-11 flex-1 gap-2 text-sm font-bold"
            onClick={() => {
              setSpeaking(false);
              setTyping((value) => !value);
            }}
          >
            {typing ? (
              <ListChecks className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Keyboard className="h-4 w-4" aria-hidden="true" />
            )}
            {typing ? t("input.useQuick") : t("input.typeInstead")}
          </Button>
          {/* One press instead of two for a worker who would rather speak: open the answer box
              and start listening. Inside the box the microphone is there too. */}
          {voiceReady && !typing && (
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-11 w-11 shrink-0 rounded-xl"
              aria-label={t("input.voiceStart")}
              onClick={() => {
                setSpeaking(true);
                setTyping(true);
              }}
            >
              <Mic className="h-5 w-5" aria-hidden="true" />
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

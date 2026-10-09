import { useCallback, useEffect, useRef, useState } from "react";

import type { LanguageCode } from "@/types/enums";
import {
  isVoiceAvailable,
  problemFor,
  speechRecognitionConstructor,
  transcriptOf,
  voiceTag,
  type SpeechRecognitionLike,
  type VoiceProblem,
} from "@/utils/voiceInput";

export interface SpeechInput {
  /** The microphone is offered: the browser can recognise speech and the language is supported. */
  available: boolean;
  listening: boolean;
  problem: VoiceProblem | null;
  /** Start listening; `onHeard` gets everything heard so far in this run, again on each change. */
  start: (onHeard: (text: string) => void) => void;
  /** Finish: what was heard so far is kept. */
  stop: () => void;
  /** Drop the run at once, hearing nothing more (the answer was sent, or the screen changed). */
  cancel: () => void;
}

/**
 * Dictation with the browser's speech recognition. One run listens until the worker stops, or
 * until the browser hears a pause (it ends the run itself). Nothing is sent anywhere by this app:
 * the words go into the answer box, and the worker reads them before sending. Leaving the screen,
 * or switching the language, cancels a run in progress.
 */
export function useSpeechInput(language: LanguageCode): SpeechInput {
  const [listening, setListening] = useState(false);
  const [problem, setProblem] = useState<VoiceProblem | null>(null);
  const run = useRef<SpeechRecognitionLike | null>(null);
  const available = isVoiceAvailable(language);

  const cancel = useCallback(() => {
    const current = run.current;
    run.current = null;
    if (current) {
      current.onresult = null;
      current.onerror = null;
      current.onend = null;
      current.abort();
    }
    setListening(false);
  }, []);

  const start = useCallback(
    (onHeard: (text: string) => void) => {
      const Recognition = speechRecognitionConstructor();
      const tag = voiceTag(language);
      if (Recognition === null || tag === null || run.current !== null) {
        return;
      }
      const recognition = new Recognition();
      recognition.lang = tag;
      recognition.interimResults = true;
      recognition.continuous = false;
      recognition.maxAlternatives = 1;
      recognition.onresult = (event) => onHeard(transcriptOf(event));
      recognition.onerror = (event) => setProblem(problemFor(event.error));
      recognition.onend = () => {
        run.current = null;
        setListening(false);
      };
      run.current = recognition;
      setProblem(null);
      try {
        recognition.start();
        setListening(true);
      } catch {
        // The browser refused to start (a run is still closing): tell the worker, never throw.
        run.current = null;
        setProblem("failed");
      }
    },
    [language]
  );

  const stop = useCallback(() => run.current?.stop(), []);

  // A different language, or leaving the screen, ends the run: it was listening for the old one.
  useEffect(() => cancel, [cancel, language]);

  return { available, listening, problem, start, stop, cancel };
}

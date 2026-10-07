import { useCallback, useEffect, useRef, useState } from "react";

import { pickVoice } from "@/utils/speech";

export interface Speech {
  /** A voice for the language is installed. False until the browser has listed its voices, and
   * on a device with none, so the button that needs it stays hidden. */
  available: boolean;
  speaking: boolean;
  /** The voice stopped on an error of its own, not because the worker pressed stop. */
  failed: boolean;
  speak: (parts: readonly string[]) => void;
  stop: () => void;
}

// A browser, a test runner or an old WebView may have no speech engine at all.
function engine(): SpeechSynthesis | null {
  return typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    typeof SpeechSynthesisUtterance !== "undefined"
    ? window.speechSynthesis
    : null;
}

// What the engine reports when a read is cut short on purpose (stop, or a newer read).
const ON_PURPOSE = new Set(["canceled", "interrupted"]);

/** Reads text aloud with the browser's own voices (Web Speech API) in one of the app's languages.
 * Offers play and stop only: pause is unreliable on Android Chrome, where most workers are. A read
 * stops by itself when the component goes away, so a voice never talks over the next screen. */
export function useSpeech(language: string): Speech {
  const [voice, setVoice] = useState<SpeechSynthesisVoice | null>(null);
  const [speaking, setSpeaking] = useState(false);
  const [failed, setFailed] = useState(false);
  // Numbers each read so the late events of a stopped one cannot change the state of the next.
  const read = useRef(0);

  // Chrome lists its voices after the page loads and says so with `voiceschanged`.
  useEffect(() => {
    const synth = engine();
    if (synth === null) {
      return undefined;
    }
    const update = () => setVoice(pickVoice(synth.getVoices(), language));
    update();
    synth.addEventListener("voiceschanged", update);
    return () => synth.removeEventListener("voiceschanged", update);
  }, [language]);

  const stop = useCallback(() => {
    read.current += 1;
    engine()?.cancel();
    setSpeaking(false);
  }, []);

  useEffect(
    () => () => {
      read.current += 1;
      engine()?.cancel();
    },
    []
  );

  const speak = useCallback(
    (parts: readonly string[]) => {
      const synth = engine();
      if (synth === null || voice === null || parts.length === 0) {
        return;
      }
      const id = ++read.current;
      setFailed(false);
      setSpeaking(true);
      parts.forEach((part, index) => {
        const utterance = new SpeechSynthesisUtterance(part);
        utterance.voice = voice;
        // The voice's own tag (`hi-IN`), which is what Android's engine needs to pick a language.
        utterance.lang = voice.lang;
        utterance.onend = () => {
          if (read.current === id && index === parts.length - 1) {
            setSpeaking(false);
          }
        };
        utterance.onerror = (event) => {
          if (read.current !== id) {
            return;
          }
          // One failed piece ends the read; the queued ones then report "canceled" and are ignored.
          read.current += 1;
          synth.cancel();
          setSpeaking(false);
          setFailed(!ON_PURPOSE.has(event.error));
        };
        synth.speak(utterance);
      });
    },
    [voice]
  );

  return { available: voice !== null, speaking, failed, speak, stop };
}

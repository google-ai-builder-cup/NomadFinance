import type { LanguageCode } from "@/types/enums";

// The browser's own speech-to-text (Web Speech API). Chrome on Android recognises English, Hindi
// and Indonesian well; the other three of the app's languages are not offered because a wrong
// transcript in a language the worker cannot easily correct does more harm than no microphone.
// The tags are what Chrome lists: en-US is the safest English for workers from every corridor.
export const VOICE_LANGUAGE_TAGS: Partial<Record<LanguageCode, string>> = {
  en: "en-US",
  hi: "hi-IN",
  id: "id-ID",
};

/** What the page uses of a recognition object: the standard names, and Chrome's `webkit` prefix. */
export interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

export interface SpeechResultEvent {
  resultIndex: number;
  results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>;
}

export type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

export type VoiceProblem = "denied" | "noSpeech" | "noMic" | "network" | "failed";

export function speechRecognitionConstructor(
  scope: object = window
): SpeechRecognitionConstructor | null {
  const found = scope as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return found.SpeechRecognition ?? found.webkitSpeechRecognition ?? null;
}

/** The recognition language for `language`, or null when the microphone is not offered for it. */
export function voiceTag(language: LanguageCode): string | null {
  return VOICE_LANGUAGE_TAGS[language] ?? null;
}

/** Whether to show the microphone: the browser has speech recognition and the language is one of
 * the three offered. It stays hidden everywhere else. */
export function isVoiceAvailable(language: LanguageCode, scope: object = window): boolean {
  return voiceTag(language) !== null && speechRecognitionConstructor(scope) !== null;
}

/** The words heard so far in one recognition run, as one line. */
export function transcriptOf(event: SpeechResultEvent): string {
  const parts: string[] = [];
  for (let index = 0; index < event.results.length; index += 1) {
    const alternative = event.results[index][0];
    if (alternative) {
      parts.push(alternative.transcript.trim());
    }
  }
  return parts.filter(Boolean).join(" ");
}

/** What a recognition error means for the worker. Anything not listed is a general failure. */
export function problemFor(error: string): VoiceProblem | null {
  switch (error) {
    case "not-allowed":
    case "service-not-allowed":
      return "denied";
    case "no-speech":
      return "noSpeech";
    case "audio-capture":
      return "noMic";
    case "network":
      return "network";
    case "aborted":
      return null; // the worker (or the screen) stopped it: nothing to tell
    default:
      return "failed";
  }
}

/** Dictated words added to what is already in the box, with one space between them. */
export function appendDictation(base: string, heard: string): string {
  const spoken = heard.trim();
  if (!spoken) {
    return base;
  }
  return base.trim() ? `${base.trimEnd()} ${spoken}` : spoken;
}

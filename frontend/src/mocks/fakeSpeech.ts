// A stand-in for the browser's speech engine, for the tests of read-aloud (NF-SA-017): jsdom has
// none. Only tests import this module; the app never does.
import { vi } from "vitest";

export class FakeUtterance {
  text: string;
  lang = "";
  voice: SpeechSynthesisVoice | null = null;
  onend: (() => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;

  constructor(text: string) {
    this.text = text;
  }
}

export function voice(
  lang: string,
  overrides: Partial<SpeechSynthesisVoice> = {}
): SpeechSynthesisVoice {
  return {
    name: `Voice ${lang}`,
    voiceURI: `voice-${lang}`,
    lang,
    localService: true,
    default: false,
    ...overrides,
  };
}

export interface FakeSpeech {
  /** Utterances handed to the engine and not yet finished, in order. */
  queue: FakeUtterance[];
  cancel: ReturnType<typeof vi.fn>;
  /** The browser finishing its list of voices after the page loaded. */
  setVoices: (voices: SpeechSynthesisVoice[]) => void;
  /** The engine finishing the utterance at the front of the queue. */
  finishNext: () => void;
  /** The engine failing on the utterance at the front of the queue. */
  failNext: (error: string) => void;
}

/** Puts the fake on `window` for one test; call `vi.unstubAllGlobals()` afterwards. */
export function installFakeSpeech(initial: SpeechSynthesisVoice[]): FakeSpeech {
  let voices = initial;
  const queue: FakeUtterance[] = [];
  const listeners = new Set<() => void>();

  // Like Chrome: stopping tells every waiting utterance it was interrupted.
  const cancel = vi.fn(() => {
    for (const utterance of queue.splice(0)) {
      utterance.onerror?.({ error: "interrupted" });
    }
  });

  vi.stubGlobal("speechSynthesis", {
    getVoices: () => voices,
    addEventListener: (_type: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_type: string, listener: () => void) => listeners.delete(listener),
    speak: (utterance: FakeUtterance) => queue.push(utterance),
    cancel,
  });
  vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);

  return {
    queue,
    cancel,
    setVoices: (next) => {
      voices = next;
      listeners.forEach((listener) => listener());
    },
    finishNext: () => queue.shift()?.onend?.(),
    failNext: (error) => queue.shift()?.onerror?.({ error }),
  };
}

// Which installed voice reads a language aloud (NF-SA-017). Pure, so the matching rules are
// testable without a browser that has voices.

// Android's text-to-speech names two of our languages by their older or alternate codes: Filipino
// is `fil` (Tagalog is its base) and Indonesian is `in` (Java's code for it).
const VOICE_CODES: Readonly<Record<string, readonly string[]>> = {
  tl: ["tl", "fil"],
  id: ["id", "in"],
};

/** `hi-IN` and `hi_IN` (Android Chrome writes an underscore) both give `hi`. */
function primaryTag(lang: string): string {
  return lang.toLowerCase().split(/[-_]/)[0];
}

// A voice stored on the phone still speaks with no signal, which is when a worker abroad may need
// the next steps most; the system default breaks a tie.
const rank = (voice: SpeechSynthesisVoice): number =>
  (voice.localService ? 2 : 0) + (voice.default ? 1 : 0);

/** The best installed voice for one of the app's language codes, or null when there is none (the
 * caller then hides the read-aloud button instead of reading in the wrong language). */
export function pickVoice(
  voices: readonly SpeechSynthesisVoice[],
  language: string
): SpeechSynthesisVoice | null {
  const accepted = VOICE_CODES[language] ?? [language];
  const matching = voices.filter((voice) => accepted.includes(primaryTag(voice.lang)));
  if (matching.length === 0) {
    return null;
  }
  return matching.reduce((best, voice) => (rank(voice) > rank(best) ? voice : best));
}

import type { ScamExplainer } from "@/types/scam";

/** The section names, in the language the voice will speak. */
export interface SpokenLabels {
  why: string;
  wants: string;
  steps: string;
  step: (number: number) => string;
}

/** What the read-aloud button says, one piece per breath: each is its own utterance, so the voice
 * pauses between ideas and a long explanation never hits a browser's cap on one utterance.
 *
 * Pass `labels` only when they are in the explainer's own language: the voice is chosen for that
 * language, and a heading in another one would be read out as noise. Without them it reads the
 * explainer's words alone. */
export function explainerSpeech(explainer: ScamExplainer, labels?: SpokenLabels): string[] {
  if (explainer.kind === "benign") {
    return [explainer.reassurance, explainer.tip];
  }
  return [
    labels?.why,
    ...explainer.why_it_works.map((item) => item.text),
    labels?.wants,
    explainer.scammer_wants,
    labels?.steps,
    ...explainer.next_steps.map((step, index) =>
      labels ? `${labels.step(index + 1)}. ${step}` : step
    ),
  ].filter((piece): piece is string => typeof piece === "string" && piece.trim() !== "");
}

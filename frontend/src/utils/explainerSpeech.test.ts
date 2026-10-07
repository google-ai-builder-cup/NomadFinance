import { describe, expect, it } from "vitest";

import type { ScamExplainer } from "@/types/scam";
import { explainerSpeech, type SpokenLabels } from "@/utils/explainerSpeech";

const scam: Extract<ScamExplainer, { kind: "scam" }> = {
  kind: "scam",
  language: "en",
  why_it_works: [
    { tactic: "urgency", text: "It says pay today." },
    { tactic: "scarcity", text: "It says one place is left." },
  ],
  scammer_wants: "They want your fee first.",
  next_steps: ["Do not pay.", "Check the agency.", "Tell your bank."],
};

const labels: SpokenLabels = {
  why: "Why this is a scam",
  wants: "What the sender wants",
  steps: "What to do now",
  step: (number) => `Step ${number}`,
};

describe("explainerSpeech", () => {
  it("reads the explainer's own words alone when no labels are given", () => {
    expect(explainerSpeech(scam)).toEqual([
      "It says pay today.",
      "It says one place is left.",
      "They want your fee first.",
      "Do not pay.",
      "Check the agency.",
      "Tell your bank.",
    ]);
  });

  it("adds the headings and numbers the steps when they are in the same language", () => {
    expect(explainerSpeech(scam, labels)).toEqual([
      "Why this is a scam",
      "It says pay today.",
      "It says one place is left.",
      "What the sender wants",
      "They want your fee first.",
      "What to do now",
      "Step 1. Do not pay.",
      "Step 2. Check the agency.",
      "Step 3. Tell your bank.",
    ]);
  });

  it("reads the reassurance, then the tip, for a message that is not a scam", () => {
    const benign: ScamExplainer = {
      kind: "benign",
      language: "en",
      reassurance: "This is an ordinary notice.",
      tip: "Check anything that asks for money.",
    };

    expect(explainerSpeech(benign, labels)).toEqual([
      "This is an ordinary notice.",
      "Check anything that asks for money.",
    ]);
  });

  it("skips empty text, so the voice never says nothing", () => {
    const sparse = { ...scam, why_it_works: [{ tactic: "urgency", text: "  " }] };

    expect(explainerSpeech(sparse)).not.toContain("  ");
    expect(explainerSpeech(sparse)).toHaveLength(4);
  });
});

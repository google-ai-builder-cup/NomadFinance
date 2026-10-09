import { describe, expect, it } from "vitest";

import {
  appendDictation,
  isVoiceAvailable,
  problemFor,
  speechRecognitionConstructor,
  transcriptOf,
  voiceTag,
  type SpeechResultEvent,
} from "@/utils/voiceInput";

class Fake {}

function heard(...phrases: string[]): SpeechResultEvent {
  return {
    resultIndex: 0,
    results: phrases.map((transcript) => Object.assign([{ transcript }], { isFinal: true })),
  };
}

describe("which languages offer the microphone", () => {
  it.each([
    ["en", "en-US"],
    ["hi", "hi-IN"],
    ["id", "id-ID"],
  ] as const)("%s listens as %s", (language, tag) => {
    expect(voiceTag(language)).toBe(tag);
  });

  it.each(["tl", "ne", "bn"] as const)("%s has no microphone", (language) => {
    expect(voiceTag(language)).toBeNull();
    expect(isVoiceAvailable(language, { SpeechRecognition: Fake })).toBe(false);
  });
});

describe("whether the browser can recognise speech", () => {
  it("finds the standard name and Chrome's prefixed one", () => {
    expect(speechRecognitionConstructor({ SpeechRecognition: Fake })).toBe(Fake);
    expect(speechRecognitionConstructor({ webkitSpeechRecognition: Fake })).toBe(Fake);
    expect(speechRecognitionConstructor({})).toBeNull();
  });

  it("shows the microphone only with both the API and a supported language", () => {
    expect(isVoiceAvailable("hi", { webkitSpeechRecognition: Fake })).toBe(true);
    expect(isVoiceAvailable("hi", {})).toBe(false); // Safari or Firefox without the API
    expect(isVoiceAvailable("bn", { webkitSpeechRecognition: Fake })).toBe(false);
  });
});

describe("what was heard", () => {
  it("joins the phrases of one run into one line", () => {
    expect(transcriptOf(heard(" I will earn ", "650 Singapore dollars"))).toBe(
      "I will earn 650 Singapore dollars"
    );
  });

  it("is empty when nothing was heard", () => {
    expect(transcriptOf(heard())).toBe("");
    expect(transcriptOf(heard("   "))).toBe("");
  });

  it("adds the words after what is already typed, with one space", () => {
    expect(appendDictation("", "Singapore")).toBe("Singapore");
    expect(appendDictation("I go to ", "Singapore")).toBe("I go to Singapore");
    expect(appendDictation("I go to", "")).toBe("I go to");
    expect(appendDictation("  ", " Singapore ")).toBe("Singapore");
  });
});

describe("what an error means", () => {
  it.each([
    ["not-allowed", "denied"],
    ["service-not-allowed", "denied"],
    ["no-speech", "noSpeech"],
    ["audio-capture", "noMic"],
    ["network", "network"],
    ["language-not-supported", "failed"],
    ["something-new", "failed"],
  ])("%s is %s", (error, problem) => {
    expect(problemFor(error)).toBe(problem);
  });

  it("says nothing when the worker stopped it", () => {
    expect(problemFor("aborted")).toBeNull();
  });
});

import { describe, expect, it } from "vitest";

import { voice } from "@/mocks/fakeSpeech";
import { pickVoice } from "@/utils/speech";

describe("pickVoice", () => {
  it("finds a voice for the language, whatever its region", () => {
    const hindi = voice("hi-IN");

    expect(pickVoice([voice("en-US"), hindi], "hi")).toBe(hindi);
    expect(pickVoice([voice("en-GB")], "en")).not.toBeNull();
  });

  it("reads Android's underscore tags (hi_IN) the same as hi-IN", () => {
    const hindi = voice("hi_IN");

    expect(pickVoice([hindi], "hi")).toBe(hindi);
  });

  it("is not case sensitive", () => {
    const indonesian = voice("ID-id");

    expect(pickVoice([indonesian], "id")).toBe(indonesian);
  });

  it("finds Filipino for Tagalog and Android's `in` for Indonesian", () => {
    const filipino = voice("fil-PH");
    const javaIndonesian = voice("in_ID");

    expect(pickVoice([filipino], "tl")).toBe(filipino);
    expect(pickVoice([javaIndonesian], "id")).toBe(javaIndonesian);
  });

  it("is null when no voice speaks the language, so the button can hide", () => {
    expect(pickVoice([voice("en-US"), voice("hi-IN")], "ne")).toBeNull();
    expect(pickVoice([], "en")).toBeNull();
  });

  it("does not take a language that only starts with the same letters", () => {
    // `in` (Indonesian) must not match `it` or `ind`; `bn` must not match `bng`.
    expect(pickVoice([voice("it-IT"), voice("ind-ID")], "id")).toBeNull();
    expect(pickVoice([voice("bng-BD")], "bn")).toBeNull();
  });

  it("prefers a voice stored on the phone, which works with no signal", () => {
    const online = voice("hi-IN", { localService: false, default: true });
    const stored = voice("hi-IN", { localService: true });

    expect(pickVoice([online, stored], "hi")).toBe(stored);
  });

  it("uses the system default among voices that are equally close", () => {
    const first = voice("en-US");
    const preferred = voice("en-GB", { default: true });

    expect(pickVoice([first, preferred], "en")).toBe(preferred);
    expect(pickVoice([first, voice("en-AU")], "en")).toBe(first);
  });
});

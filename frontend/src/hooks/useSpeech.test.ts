// @vitest-environment jsdom
// The read-aloud engine (NF-SA-017), against a fake of the browser's speech synthesis.
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useSpeech } from "@/hooks/useSpeech";
import { installFakeSpeech, voice } from "@/mocks/fakeSpeech";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useSpeech", () => {
  it("is not available where the browser has no speech engine", () => {
    const { result } = renderHook(() => useSpeech("en"));

    expect(result.current.available).toBe(false);
    act(() => result.current.speak(["Hello"]));
    expect(result.current.speaking).toBe(false);
  });

  it("is not available when no voice speaks the language", () => {
    installFakeSpeech([voice("en-US")]);

    const { result } = renderHook(() => useSpeech("hi"));

    expect(result.current.available).toBe(false);
  });

  it("becomes available when the browser finishes listing its voices", () => {
    const speech = installFakeSpeech([]);
    const { result } = renderHook(() => useSpeech("hi"));
    expect(result.current.available).toBe(false);

    act(() => speech.setVoices([voice("hi-IN")]));

    expect(result.current.available).toBe(true);
  });

  it("says each piece as its own utterance, in the voice and language chosen", () => {
    const speech = installFakeSpeech([voice("en-US"), voice("hi_IN")]);
    const { result } = renderHook(() => useSpeech("hi"));

    act(() => result.current.speak(["पहला", "दूसरा"]));

    expect(speech.queue.map((utterance) => utterance.text)).toEqual(["पहला", "दूसरा"]);
    expect(speech.queue.every((utterance) => utterance.voice?.lang === "hi_IN")).toBe(true);
    // The tag the voice reports, which is what Android's engine reads.
    expect(speech.queue.every((utterance) => utterance.lang === "hi_IN")).toBe(true);
    expect(result.current.speaking).toBe(true);
  });

  it("is still speaking until the last piece ends", () => {
    const speech = installFakeSpeech([voice("en-US")]);
    const { result } = renderHook(() => useSpeech("en"));
    act(() => result.current.speak(["One", "Two"]));

    act(() => speech.finishNext());
    expect(result.current.speaking).toBe(true);

    act(() => speech.finishNext());
    expect(result.current.speaking).toBe(false);
    expect(result.current.failed).toBe(false);
  });

  it("stops on request without calling that a failure", () => {
    const speech = installFakeSpeech([voice("en-US")]);
    const { result } = renderHook(() => useSpeech("en"));
    act(() => result.current.speak(["One", "Two"]));

    act(() => result.current.stop());

    expect(speech.cancel).toHaveBeenCalled();
    expect(result.current.speaking).toBe(false);
    expect(result.current.failed).toBe(false);
  });

  it("reports a failure of the voice itself and drops the rest of the read", () => {
    const speech = installFakeSpeech([voice("en-US")]);
    const { result } = renderHook(() => useSpeech("en"));
    act(() => result.current.speak(["One", "Two", "Three"]));

    act(() => speech.failNext("synthesis-failed"));

    expect(result.current.failed).toBe(true);
    expect(result.current.speaking).toBe(false);
    expect(speech.queue).toHaveLength(0);
  });

  it("clears an earlier failure when the worker tries again", () => {
    const speech = installFakeSpeech([voice("en-US")]);
    const { result } = renderHook(() => useSpeech("en"));
    act(() => result.current.speak(["One"]));
    act(() => speech.failNext("audio-busy"));
    expect(result.current.failed).toBe(true);

    act(() => result.current.speak(["One"]));

    expect(result.current.failed).toBe(false);
    expect(result.current.speaking).toBe(true);
  });

  it("does nothing when asked to say nothing", () => {
    const speech = installFakeSpeech([voice("en-US")]);
    const { result } = renderHook(() => useSpeech("en"));

    act(() => result.current.speak([]));

    expect(speech.queue).toHaveLength(0);
    expect(result.current.speaking).toBe(false);
  });

  it("stops talking when the screen goes away", () => {
    const speech = installFakeSpeech([voice("en-US")]);
    const { result, unmount } = renderHook(() => useSpeech("en"));
    act(() => result.current.speak(["One"]));

    unmount();

    expect(speech.cancel).toHaveBeenCalled();
    expect(speech.queue).toHaveLength(0);
  });
});

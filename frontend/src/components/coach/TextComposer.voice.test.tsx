// @vitest-environment jsdom
// The microphone of the answer box (NF-FC-018): shown only where the browser can recognise the
// coach's language, fills the box without sending, and says why when it cannot listen.
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import TextComposer from "@/components/coach/TextComposer";
import { loadNamespace } from "@/lib/i18n";
import type { LanguageCode } from "@/types/enums";
import type { SpeechRecognitionLike, SpeechResultEvent } from "@/utils/voiceInput";

beforeAll(async () => {
  await loadNamespace("coach");
});

/** A recognition object the test drives by hand. */
class FakeRecognition implements SpeechRecognitionLike {
  static runs: FakeRecognition[] = [];
  lang = "";
  interimResults = false;
  continuous = true;
  maxAlternatives = 0;
  onresult: ((event: SpeechResultEvent) => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  started = false;
  stopped = false;
  aborted = false;
  constructor() {
    FakeRecognition.runs.push(this);
  }
  start() {
    this.started = true;
  }
  stop() {
    this.stopped = true;
  }
  abort() {
    this.aborted = true;
  }
  hear(...phrases: string[]) {
    this.onresult?.({
      resultIndex: 0,
      results: phrases.map((transcript) => Object.assign([{ transcript }], { isFinal: false })),
    });
  }
  fail(error: string) {
    this.onerror?.({ error });
    this.onend?.();
  }
}

beforeEach(() => {
  FakeRecognition.runs = [];
  (window as unknown as Record<string, unknown>).webkitSpeechRecognition = FakeRecognition;
});
afterEach(() => {
  cleanup();
  delete (window as unknown as Record<string, unknown>).webkitSpeechRecognition;
});

function renderComposer(language: LanguageCode = "en", onSend = vi.fn()) {
  render(<TextComposer busy={false} onSend={onSend} language={language} />);
  return onSend;
}
const mic = () => screen.queryByRole("button", { name: /Speak your answer|Stop listening/ });
const box = () => screen.getByRole("textbox") as HTMLTextAreaElement;

describe("where the microphone is offered", () => {
  it.each(["en", "hi", "id"] as const)("shows it in %s when the browser can listen", (language) => {
    renderComposer(language);

    expect(mic()).not.toBeNull();
  });

  it.each(["tl", "ne", "bn"] as const)("hides it in %s", (language) => {
    renderComposer(language);

    expect(mic()).toBeNull();
  });

  it("hides it when the browser has no speech recognition", () => {
    delete (window as unknown as Record<string, unknown>).webkitSpeechRecognition;

    renderComposer("en");

    expect(mic()).toBeNull();
    expect(screen.getByRole("button", { name: "Send" })).toBeTruthy(); // typing still works
  });
});

describe("dictating", () => {
  it("listens in the coach's language and fills the box as words are heard", async () => {
    const user = userEvent.setup();
    renderComposer("hi");

    await user.click(mic() as HTMLElement);
    const run = FakeRecognition.runs[0];

    expect(run.started).toBe(true);
    expect(run.lang).toBe("hi-IN");
    expect(run.interimResults).toBe(true);
    expect((mic() as HTMLElement).getAttribute("aria-pressed")).toBe("true");
    act(() => run.hear("मैं सिंगापुर"));
    expect(box().value).toBe("मैं सिंगापुर");
    act(() => run.hear("मैं सिंगापुर जा रहा हूँ"));
    expect(box().value).toBe("मैं सिंगापुर जा रहा हूँ");
  });

  it("adds the words after what was already typed, and never sends by itself", async () => {
    const user = userEvent.setup();
    const onSend = renderComposer("en");
    await user.type(box(), "I will work in");

    await user.click(mic() as HTMLElement);
    act(() => FakeRecognition.runs[0].hear("Singapore"));

    expect(box().value).toBe("I will work in Singapore");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("tells the worker it is listening and where the voice goes", async () => {
    const user = userEvent.setup();
    renderComposer("en");

    await user.click(mic() as HTMLElement);

    const status = screen.getByRole("status");
    expect(status.textContent).toContain("Listening…");
    expect(status.textContent).toContain("speech service");
  });

  it("stops when the button is pressed again and keeps the words", async () => {
    const user = userEvent.setup();
    renderComposer("id");
    await user.click(mic() as HTMLElement);
    act(() => FakeRecognition.runs[0].hear("Malaysia"));

    await user.click(mic() as HTMLElement);

    expect(FakeRecognition.runs[0].stopped).toBe(true);
    act(() => FakeRecognition.runs[0].onend?.());
    expect(box().value).toBe("Malaysia");
    expect((mic() as HTMLElement).getAttribute("aria-pressed")).toBe("false");
  });

  it("is dropped when the answer is sent, so late words do not come back", async () => {
    const user = userEvent.setup();
    const onSend = renderComposer("en");
    await user.click(mic() as HTMLElement);
    act(() => FakeRecognition.runs[0].hear("Japan"));

    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith("Japan");
    expect(FakeRecognition.runs[0].aborted).toBe(true);
    act(() => FakeRecognition.runs[0].hear("something late"));
    expect(box().value).toBe("");
  });

  it("is dropped when the language changes", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<TextComposer busy={false} onSend={vi.fn()} language="en" />);
    await user.click(mic() as HTMLElement);

    rerender(<TextComposer busy={false} onSend={vi.fn()} language="hi" />);

    expect(FakeRecognition.runs[0].aborted).toBe(true);
    expect((mic() as HTMLElement).getAttribute("aria-pressed")).toBe("false");
  });

  it("is dropped when the screen is left", async () => {
    const user = userEvent.setup();
    renderComposer("en");
    await user.click(mic() as HTMLElement);

    cleanup();

    expect(FakeRecognition.runs[0].aborted).toBe(true);
  });
});

describe("when it cannot listen", () => {
  it.each([
    ["not-allowed", /microphone is blocked/],
    ["no-speech", /did not hear anything/],
    ["audio-capture", /No microphone was found/],
    ["network", /could not be reached/],
    ["language-not-supported", /did not work/],
  ])("%s says why, and the box still works", async (error, message) => {
    const user = userEvent.setup();
    renderComposer("en");
    await user.click(mic() as HTMLElement);

    act(() => FakeRecognition.runs[0].fail(error));

    expect(screen.getByRole("status").textContent).toMatch(message);
    await user.type(box(), "typed instead");
    expect(box().value).toBe("typed instead");
  });

  it("says nothing when the worker stopped it", async () => {
    const user = userEvent.setup();
    renderComposer("en");
    await user.click(mic() as HTMLElement);

    act(() => FakeRecognition.runs[0].fail("aborted"));

    expect(screen.getByRole("status").textContent).toBe("");
  });

  it("starts again after a problem", async () => {
    const user = userEvent.setup();
    renderComposer("en");
    await user.click(mic() as HTMLElement);
    act(() => FakeRecognition.runs[0].fail("no-speech"));

    await user.click(mic() as HTMLElement);

    expect(FakeRecognition.runs).toHaveLength(2);
    expect(screen.getByRole("status").textContent).toContain("Listening…");
  });
});

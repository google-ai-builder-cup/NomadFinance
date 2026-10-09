// @vitest-environment jsdom
// The microphone beside "Type my own answer" (NF-FC-018): one press opens the answer box already
// listening, for a worker who would rather speak than tap.
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import AnswerPanel from "@/components/coach/AnswerPanel";
import { loadNamespace } from "@/lib/i18n";
import type { LanguageCode } from "@/types/enums";

beforeAll(async () => {
  await loadNamespace("coach");
});

const runs: { lang: string; started: boolean }[] = [];

class FakeRecognition {
  lang = "";
  started = false;
  interimResults = false;
  continuous = false;
  maxAlternatives = 1;
  onresult = null;
  onerror = null;
  onend = null;
  constructor() {
    runs.push(this);
  }
  start() {
    this.started = true;
  }
  stop() {}
  abort() {}
}

beforeEach(() => {
  runs.length = 0;
  (window as unknown as Record<string, unknown>).webkitSpeechRecognition = FakeRecognition;
});
afterEach(() => {
  cleanup();
  delete (window as unknown as Record<string, unknown>).webkitSpeechRecognition;
});

function renderPanel(language: LanguageCode = "en") {
  const onSend = vi.fn();
  render(
    <AnswerPanel
      stage="intro"
      slot="destination_country"
      slots={{}}
      busy={false}
      onSend={onSend}
      language={language}
    />
  );
  return onSend;
}
const startVoice = () => screen.queryByRole("button", { name: "Speak your answer" });

describe("the microphone on a helper", () => {
  it("is beside 'Type my own answer' where the browser can listen", () => {
    renderPanel("en");

    expect(startVoice()).not.toBeNull();
    expect(screen.getByRole("button", { name: "Type my own answer" })).toBeTruthy();
  });

  it("opens the answer box already listening, in the coach's language", async () => {
    renderPanel("hi");

    await userEvent.setup().click(startVoice() as HTMLElement);

    expect(screen.getByRole("textbox")).toBeTruthy();
    expect(runs).toHaveLength(1);
    expect(runs[0]).toMatchObject({ lang: "hi-IN", started: true });
    expect(screen.getByRole("status").textContent).toContain("Listening");
  });

  it("is not there for Tagalog, Nepali or Bengali, or without the browser's speech API", () => {
    for (const language of ["tl", "ne", "bn"] as const) {
      renderPanel(language);
      expect(startVoice()).toBeNull();
      cleanup();
    }
    delete (window as unknown as Record<string, unknown>).webkitSpeechRecognition;
    renderPanel("en");
    expect(startVoice()).toBeNull();
  });

  it("leaves 'Type my own answer' alone: typing opens the box without listening", async () => {
    renderPanel("en");

    await userEvent.setup().click(screen.getByRole("button", { name: "Type my own answer" }));

    expect(screen.getByRole("textbox")).toBeTruthy();
    expect(runs).toHaveLength(0);
  });

  it("goes back to the quick answers and the microphone returns", async () => {
    const user = userEvent.setup();
    renderPanel("en");
    await user.click(startVoice() as HTMLElement);

    await user.click(screen.getByRole("button", { name: "Use quick answers" }));

    expect(screen.queryByRole("textbox")).toBeNull();
    expect(startVoice()).not.toBeNull();
  });
});

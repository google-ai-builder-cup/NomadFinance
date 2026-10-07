// @vitest-environment jsdom
// The explanation under the verdict card and its read-aloud button (NF-SA-017).
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import ExplainerSection from "@/components/scam/ExplainerSection";
import { loadNamespace } from "@/lib/i18n";
import { installFakeSpeech, voice } from "@/mocks/fakeSpeech";
import { scamResult } from "@/mocks/scamResult";
import type { ScamExplainer } from "@/types/scam";

beforeAll(async () => {
  await loadNamespace("scam");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// The scam mock is written in Hindi, the benign one in English; the UI under test is English.
const hindi = scamResult("high").explainer as Extract<ScamExplainer, { kind: "scam" }>;
const english: ScamExplainer = {
  ...hindi,
  language: "en",
  why_it_works: [{ tactic: "urgency", text: "It says pay today." }],
  scammer_wants: "They want your fee first.",
  next_steps: ["Do not pay.", "Check the agency.", "Tell your bank."],
};
const benign = scamResult("benign").explainer as ScamExplainer;

const spoken = (speech: ReturnType<typeof installFakeSpeech>) =>
  speech.queue.map((utterance) => utterance.text);

describe("ExplainerSection, for a scam", () => {
  it("shows why it works, what the sender wants and the steps as a numbered list", () => {
    render(<ExplainerSection explainer={english} />);

    expect(screen.getByRole("heading", { name: "Why this is a scam" })).toBeTruthy();
    // The explainer's own words, with the trick they belong to named above them.
    expect(screen.getByText("It says pay today.")).toBeTruthy();
    expect(screen.getByText("Pressure to hurry")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "What the sender wants" })).toBeTruthy();
    expect(screen.getByText("They want your fee first.")).toBeTruthy();

    expect(screen.getByRole("heading", { name: "What to do now" })).toBeTruthy();
    const steps = screen.getAllByRole("listitem").slice(-3);
    expect(steps.map((step) => step.textContent)).toEqual([
      "1Step 1.Do not pay.",
      "2Step 2.Check the agency.",
      "3Step 3.Tell your bank.",
    ]);
    expect(screen.getAllByRole("list").some((list) => list.tagName === "OL")).toBe(true);
  });

  it("marks the language of the explainer's text for a screen reader", () => {
    render(<ExplainerSection explainer={hindi} />);

    expect(screen.getByText(hindi.scammer_wants).getAttribute("lang")).toBe("hi");
    expect(screen.getByText(hindi.next_steps[0]).getAttribute("lang")).toBe("hi");
  });

  it("names a trick the explainer mentions that the app has no label for", () => {
    render(
      <ExplainerSection
        explainer={{ ...english, why_it_works: [{ tactic: "new_trick", text: "A new way." }] }}
      />
    );

    expect(screen.getByText("new trick")).toBeTruthy();
  });

  it("has no tactic list when there is nothing to say per tactic", () => {
    render(<ExplainerSection explainer={{ ...english, why_it_works: [] }} />);

    expect(screen.getByText("They want your fee first.")).toBeTruthy();
    expect(screen.getAllByRole("list")).toHaveLength(1);
  });
});

describe("ExplainerSection, for a message that is not a scam", () => {
  it("shows the reassurance and the tip, with no steps", () => {
    render(<ExplainerSection explainer={benign} />);

    expect(screen.getByRole("heading", { name: "Good to know" })).toBeTruthy();
    expect(screen.getByText(/ordinary delivery notice/)).toBeTruthy();
    expect(screen.getByText(/check it here before you do anything/)).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "What to do now" })).toBeNull();
  });

  it("can be read aloud too", async () => {
    const speech = installFakeSpeech([voice("en-US")]);
    render(<ExplainerSection explainer={benign} />);

    await userEvent.click(screen.getByRole("button", { name: "Listen to this" }));

    expect(spoken(speech)).toHaveLength(2);
    expect(spoken(speech)[0]).toMatch(/ordinary delivery notice/);
  });
});

describe("ExplainerSection, when the explanation could not be written", () => {
  it("says so, and offers no voice", () => {
    installFakeSpeech([voice("en-US"), voice("hi-IN")]);
    render(<ExplainerSection explainer={null} />);

    expect(screen.getByText(/could not write the full explanation/)).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("read-aloud", () => {
  it("hides itself where no voice speaks the explainer's language", () => {
    installFakeSpeech([voice("en-US")]);
    render(<ExplainerSection explainer={hindi} />);

    expect(screen.queryByRole("button", { name: "Listen to this" })).toBeNull();
  });

  it("hides itself where the browser has no speech engine at all", () => {
    render(<ExplainerSection explainer={english} />);

    expect(screen.queryByRole("button", { name: "Listen to this" })).toBeNull();
  });

  it("appears when the browser lists a voice for the language after the page loaded", () => {
    const speech = installFakeSpeech([]);
    render(<ExplainerSection explainer={hindi} />);
    expect(screen.queryByRole("button", { name: "Listen to this" })).toBeNull();

    act(() => speech.setVoices([voice("hi_IN")]));

    expect(screen.getByRole("button", { name: "Listen to this" })).toBeTruthy();
  });

  it("reads the headings and the numbered steps when they are in the explainer's language", async () => {
    const speech = installFakeSpeech([voice("en-US")]);
    render(<ExplainerSection explainer={english} />);

    await userEvent.click(screen.getByRole("button", { name: "Listen to this" }));

    expect(spoken(speech)).toEqual([
      "Why this is a scam",
      "It says pay today.",
      "What the sender wants",
      "They want your fee first.",
      "What to do now",
      "Step 1. Do not pay.",
      "Step 2. Check the agency.",
      "Step 3. Tell your bank.",
    ]);
  });

  it("reads only the explainer's words when the screen is in another language", async () => {
    // A Hindi explanation under the English screen: an English heading must not reach a Hindi voice.
    const speech = installFakeSpeech([voice("hi-IN")]);
    render(<ExplainerSection explainer={hindi} />);

    await userEvent.click(screen.getByRole("button", { name: "Listen to this" }));

    expect(spoken(speech)).toEqual([
      ...hindi.why_it_works.map((item) => item.text),
      hindi.scammer_wants,
      ...hindi.next_steps,
    ]);
    expect(speech.queue.every((utterance) => utterance.lang === "hi-IN")).toBe(true);
  });

  it("turns into a stop button while it speaks, and stops when pressed", async () => {
    const speech = installFakeSpeech([voice("en-US")]);
    render(<ExplainerSection explainer={english} />);

    await userEvent.click(screen.getByRole("button", { name: "Listen to this" }));
    await userEvent.click(screen.getByRole("button", { name: "Stop listening" }));

    expect(speech.cancel).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Listen to this" })).toBeTruthy();
  });

  it("goes back to listen when the last piece has been said", async () => {
    const speech = installFakeSpeech([voice("en-US")]);
    render(<ExplainerSection explainer={benign} />);
    await userEvent.click(screen.getByRole("button", { name: "Listen to this" }));

    act(() => {
      speech.finishNext();
      speech.finishNext();
    });

    expect(screen.getByRole("button", { name: "Listen to this" })).toBeTruthy();
  });

  it("tells the worker when the voice fails, and lets them try again", async () => {
    const speech = installFakeSpeech([voice("en-US")]);
    render(<ExplainerSection explainer={english} />);
    await userEvent.click(screen.getByRole("button", { name: "Listen to this" }));

    act(() => speech.failNext("synthesis-failed"));

    expect(screen.getByRole("status").textContent).toMatch(/could not play the voice/);
    await userEvent.click(screen.getByRole("button", { name: "Listen to this" }));
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("stops talking when the result goes away", async () => {
    const speech = installFakeSpeech([voice("en-US")]);
    const { unmount } = render(<ExplainerSection explainer={english} />);
    await userEvent.click(screen.getByRole("button", { name: "Listen to this" }));

    unmount();

    expect(speech.cancel).toHaveBeenCalled();
  });
});

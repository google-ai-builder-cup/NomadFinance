// @vitest-environment jsdom
// Tap to explain (NF-SA-016): each trick is a button that opens a plain explanation; the
// explainer's own words when there are some, a short general line when there are not.
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

import TacticChips from "@/components/scam/TacticChips";
import { loadNamespace } from "@/lib/i18n";

beforeAll(async () => {
  await loadNamespace("scam");
});

afterEach(cleanup);

const EXPLAINED = [
  { tactic: "urgency", text: "They say pay today, so you cannot stop to think." },
  { tactic: "scarcity", text: "They say only one place is left." },
];

describe("TacticChips", () => {
  it("shows nothing when the message uses no trick", () => {
    const { container } = render(<TacticChips tactics={[]} />);

    expect(container.firstChild).toBeNull();
  });

  it("starts closed, every trick a button with an icon and its name", () => {
    const { container } = render(<TacticChips tactics={["urgency", "fear"]} />);

    const buttons = screen.getAllByRole("button");
    expect(buttons.map((button) => button.textContent)).toEqual([
      "Pressure to hurry",
      "Scaring you",
    ]);
    for (const button of buttons) {
      expect(button.getAttribute("aria-expanded")).toBe("false");
      expect(button.querySelector("svg[aria-hidden='true']")).toBeTruthy();
    }
    expect(container.querySelector("[id]")).toBeNull();
  });

  it("opens the explainer's own words for the trick that was tapped", async () => {
    render(<TacticChips tactics={["urgency", "scarcity"]} explanations={EXPLAINED} />);

    await userEvent.click(screen.getByRole("button", { name: "Pressure to hurry" }));

    const button = screen.getByRole("button", { name: "Pressure to hurry" });
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("They say pay today, so you cannot stop to think.")).toBeTruthy();
    // The panel is the element the button controls.
    const panel = document.getElementById(button.getAttribute("aria-controls") ?? "");
    expect(panel?.textContent).toContain("They say pay today");
  });

  it("opens one at a time, and tapping the open one closes it", async () => {
    render(<TacticChips tactics={["urgency", "scarcity"]} explanations={EXPLAINED} />);
    const urgency = screen.getByRole("button", { name: "Pressure to hurry" });
    const scarcity = screen.getByRole("button", { name: "Only a few left" });

    await userEvent.click(urgency);
    await userEvent.click(scarcity);

    expect(urgency.getAttribute("aria-expanded")).toBe("false");
    expect(scarcity.getAttribute("aria-expanded")).toBe("true");
    expect(screen.queryByText(/pay today/)).toBeNull();
    expect(screen.getByText("They say only one place is left.")).toBeTruthy();

    await userEvent.click(scarcity);

    expect(scarcity.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText(/only one place/)).toBeNull();
  });

  it("works from the keyboard", async () => {
    render(<TacticChips tactics={["urgency"]} explanations={EXPLAINED} />);

    await userEvent.tab();
    expect(document.activeElement?.textContent).toBe("Pressure to hurry");
    await userEvent.keyboard("{Enter}");
    expect(screen.getByText(/pay today/)).toBeTruthy();
    await userEvent.keyboard(" ");
    expect(screen.queryByText(/pay today/)).toBeNull();
  });

  it("falls back to a general line when the explainer has nothing for that trick", async () => {
    render(<TacticChips tactics={["fear"]} explanations={EXPLAINED} />);

    await userEvent.click(screen.getByRole("button", { name: "Scaring you" }));

    expect(screen.getByText(/The sender threatens you/)).toBeTruthy();
  });

  it("answers a tap even when the explainer could not be written", async () => {
    render(<TacticChips tactics={["social_proof"]} />);

    await userEvent.click(screen.getByRole("button", { name: "Everyone else did it" }));

    expect(screen.getByText(/many people joined or earned money/)).toBeTruthy();
  });

  it("shows a trick it has no name for as words, and still opens", async () => {
    render(
      <TacticChips
        tactics={["fake_deadline"]}
        explanations={[{ tactic: "fake_deadline", text: "Hurry." }]}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "fake deadline" }));

    expect(screen.getByText("Hurry.")).toBeTruthy();
  });

  it("has tap targets of at least 44 px", () => {
    render(<TacticChips tactics={["urgency"]} />);

    expect(screen.getByRole("button").className).toContain("min-h-11");
  });
});

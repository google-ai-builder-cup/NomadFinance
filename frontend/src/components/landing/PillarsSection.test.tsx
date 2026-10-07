// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import "@/lib/i18n";
import { afterEach, describe, expect, it } from "vitest";

import PillarsSection from "@/components/landing/PillarsSection";

afterEach(cleanup);

function renderSection() {
  return render(
    <MemoryRouter>
      <PillarsSection />
    </MemoryRouter>
  );
}

describe("the landing page's pillars", () => {
  it("say six, and show six cards, each leading to sign-in", () => {
    renderSection();

    expect(screen.getByText("Six pillars")).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Six ways NomadFinance has your back" })
    ).toBeTruthy();
    const cards = screen.getAllByRole("link");
    expect(cards).toHaveLength(6);
    for (const card of cards) {
      expect(card.getAttribute("href")).toBe("/sign-in");
    }
  });

  it("name the four pillars of v1.0 and the Scam Check and the Financial Coach", () => {
    renderSection();

    for (const name of [
      "Remittance X-Ray",
      "Contract Shield",
      "Exploitation Radar",
      "Financial Identity",
      "Scam Check",
      "Financial Coach",
    ]) {
      expect(screen.getByRole("heading", { level: 3, name })).toBeTruthy();
    }
  });

  it("describe the Scam Check in three points, as the other cards do", () => {
    renderSection();

    expect(screen.getByText("Paste a message or upload a screenshot")).toBeTruthy();
    expect(screen.getByText("Warn other workers anonymously through the Radar")).toBeTruthy();
  });
});

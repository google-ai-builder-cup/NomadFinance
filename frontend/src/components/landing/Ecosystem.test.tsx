// @vitest-environment jsdom
// The ecosystem diagram on the landing page: all six pillars and the bank, and every exchange of
// data between them that docs/future-scope/design.md section 8 lists (plus the four v1.0 links).
// A test cannot see the picture, so it checks what makes it right: each connector starts on one
// card and ends on the other, no two cards touch, and every label has its words.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import Ecosystem from "@/components/landing/Ecosystem";
import { setLanguage } from "@/lib/i18n";

afterEach(async () => {
  cleanup();
  await setLanguage("en");
});

// from -> to, as the data flows. Contract Shield also gives the Coach the legal fee cap (design
// row 4), which travels on the same connector as the salary (row 3).
const CONNECTIONS: Record<string, [string, string]> = {
  contractToRadar: ["contract", "radar"],
  radarToContract: ["radar", "contract"],
  radarToRemit: ["radar", "remit"],
  contractToCoach: ["contract", "coach"],
  coachToRemit: ["coach", "remit"],
  remitToCoach: ["remit", "coach"],
  scamToRadar: ["scam", "radar"],
  radarToScam: ["radar", "scam"],
  scamToIdentity: ["scam", "identity"],
  contractToIdentity: ["contract", "identity"],
  remitToIdentity: ["remit", "identity"],
  coachToIdentity: ["coach", "identity"],
  identityToBanks: ["identity", "banks"],
};

interface Card {
  l: number;
  t: number;
  r: number;
  b: number;
}

function cards(root: HTMLElement): Record<string, Card> {
  const found: Record<string, Card> = {};
  for (const group of root.querySelectorAll("[data-node]")) {
    const rect = group.querySelector("rect[rx='20']") as SVGRectElement;
    const [x, y, w, h] = ["x", "y", "width", "height"].map((a) => Number(rect.getAttribute(a)));
    found[group.getAttribute("data-node") as string] = { l: x, t: y, r: x + w, b: y + h };
  }
  return found;
}

/** First and last point of a path made of M, H, V and C with absolute coordinates. */
function ends(d: string): { start: [number, number]; end: [number, number] } {
  let x = 0;
  let y = 0;
  let start: [number, number] = [0, 0];
  for (const [, command, args] of d.matchAll(/([MHVC])([^MHVC]*)/g)) {
    const n = args.match(/-?\d+(?:\.\d+)?/g)?.map(Number) ?? [];
    if (command === "M") [x, y] = [n[0], n[1]];
    if (command === "H") x = n[0];
    if (command === "V") y = n[0];
    if (command === "C") [x, y] = [n[4], n[5]];
    if (command === "M") start = [x, y];
  }
  return { start, end: [x, y] };
}

/** Whether a point is on a card's outline, to within a unit. */
const onEdge = ([px, py]: [number, number], c: Card) =>
  px >= c.l - 1 &&
  px <= c.r + 1 &&
  py >= c.t - 1 &&
  py <= c.b + 1 &&
  (Math.abs(px - c.l) <= 1 ||
    Math.abs(px - c.r) <= 1 ||
    Math.abs(py - c.t) <= 1 ||
    Math.abs(py - c.b) <= 1);

describe("the path reader these tests rely on", () => {
  it("finds where a line, a straight run and a curve start and end", () => {
    expect(ends("M382 156V256")).toEqual({ start: [382, 156], end: [382, 256] });
    expect(ends("M330 114H210")).toEqual({ start: [330, 114], end: [210, 114] });
    expect(ends("M526 114C760 96 1010 112 1020 261")).toEqual({
      start: [526, 114],
      end: [1020, 261],
    });
  });

  it("tells a point on a card's outline from one inside it or away from it", () => {
    const card = { l: 100, t: 100, r: 300, b: 200 };
    expect(onEdge([300, 150], card)).toBe(true);
    expect(onEdge([200, 100], card)).toBe(true);
    expect(onEdge([200, 150], card)).toBe(false);
    expect(onEdge([400, 150], card)).toBe(false);
  });
});

describe("the ecosystem diagram", () => {
  it("shows the six pillars and the banks, each once", () => {
    const { container } = render(<Ecosystem />);

    expect(
      [...container.querySelectorAll("[data-node]")].map((n) => n.getAttribute("data-node"))
    ).toEqual(
      expect.arrayContaining(["coach", "contract", "radar", "scam", "identity", "remit", "banks"])
    );
    expect(container.querySelectorAll("[data-node]")).toHaveLength(7);
    const picture = within(container.querySelector("svg") as unknown as HTMLElement);
    for (const name of [
      "Financial",
      "Contract",
      "Exploitation",
      "Scam",
      "Remittance",
      "Banks & MFIs",
    ]) {
      expect(picture.getAllByText(name).length).toBeGreaterThan(0);
    }
    // "Financial" is the first word of two pillars' names: Coach and Identity.
    expect(picture.getAllByText("Financial")).toHaveLength(2);
    expect(picture.getByText("Coach")).toBeTruthy();
    expect(picture.getByText("Check")).toBeTruthy();
  });

  it("draws exactly the connections of the design's cross-pillar table, each from one card to the other", () => {
    const { container } = render(<Ecosystem />);
    const where = cards(container);

    const drawn = [...container.querySelectorAll("path[data-connector]")].map((p) =>
      p.getAttribute("data-connector")
    );
    expect(drawn.sort()).toEqual(Object.keys(CONNECTIONS).sort());
    for (const [id, [from, to]] of Object.entries(CONNECTIONS)) {
      const path = container.querySelector(`path[data-connector='${id}']`) as SVGPathElement;
      const { start, end } = ends(path.getAttribute("d") as string);
      expect(onEdge(start, where[from]), `${id} starts on ${from}`).toBe(true);
      expect(onEdge(end, where[to]), `${id} ends on ${to}`).toBe(true);
    }
  });

  it("keeps the cards apart", () => {
    const { container } = render(<Ecosystem />);
    const where = Object.entries(cards(container));

    for (const [i, [a, first]] of where.entries()) {
      for (const [b, second] of where.slice(i + 1)) {
        const apart =
          first.r + 20 <= second.l ||
          second.r + 20 <= first.l ||
          first.b + 20 <= second.t ||
          second.b + 20 <= first.t;
        expect(apart, `${a} and ${b} are at least 20 units apart`).toBe(true);
      }
    }
  });

  it("labels every connector with words, not with a missing key", () => {
    const { container } = render(<Ecosystem />);

    const labels = [...container.querySelectorAll("svg g[transform] text")].map(
      (t) => t.textContent
    );
    expect(labels).toEqual(
      expect.arrayContaining([
        "contract flags",
        "warnings",
        "salary",
        "quote & link",
        "scam reports",
        "seen before",
        "scam activity",
        "verified employment",
        "transfer history",
        "savings goals",
        "portable profile",
      ])
    );
    expect(labels.some((label) => label?.startsWith("landing."))).toBe(false);
  });

  it("writes every exchange out below the picture, so it is not the only way to read it", () => {
    const { container } = render(<Ecosystem />);

    const items = [...container.querySelectorAll("ul li")].map((li) => li.textContent);
    expect(items).toHaveLength(8);
    expect(items.join(" ")).toMatch(/Scam Check sends anonymous reports to the Radar/);
    expect(items.join(" ")).toMatch(/The Coach plans with Remittance's cheapest price/);
    expect(items.join(" ")).toMatch(/only if you choose to share it/);
    expect(items.some((item) => item?.startsWith("landing."))).toBe(false);
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/Scam Check sends reports/);
  });

  it("is written in the app's language", async () => {
    await setLanguage("hi");

    const { container } = render(<Ecosystem />);

    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/^आरेख:/);
    expect(container.querySelectorAll("ul li")).toHaveLength(8);
    expect(container.textContent).toContain("बचत लक्ष्य");
    expect(container.textContent).not.toContain("landing.ecosystem");
  });
});

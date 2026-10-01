import { describe, expect, it } from "vitest";

import { slugify } from "@/utils/slug";

// Expected values are python-slugify's own output (backend `slugify`) for the same input, taken
// from the World Bank provider names that are not plain words, plus the awkward cases.
const BACKEND_SLUGS: readonly [string, string][] = [
  ["Wise", "wise"],
  ["Western Union", "western-union"],
  ["A-Express Remit", "a-express-remit"],
  ["Al-Rajhi Bank", "al-rajhi-bank"],
  ["Aussie Forex & Finance", "aussie-forex-finance"],
  ["CIMB Group (Cash Laju)", "cimb-group-cash-laju"],
  ["E-remit", "e-remit"],
  ["HLB (Hong Leong Bank)", "hlb-hong-leong-bank"],
  ["IME (International Money Express)", "ime-international-money-express"],
  ["PNB (Philippines National Bank)", "pnb-philippines-national-bank"],
  ["Prime Bank (Prime Exchange Co.)", "prime-bank-prime-exchange-co"],
  ["Han River Metals Co.", "han-river-metals-co"],
  ["Bob's Remit", "bob-s-remit"],
  ["A & B Money", "a-b-money"],
  ["  Wise  ", "wise"],
  ["Café Transfer", "cafe-transfer"],
  ["Ñandú Pay", "nandu-pay"],
  ["Remit__Now", "remit-now"],
  ["100% Remit", "100-remit"],
  ["Remit - Fast", "remit-fast"],
];

describe("slugify", () => {
  it.each(BACKEND_SLUGS)("turns %j into the slug the backend makes", (name, slug) => {
    expect(slugify(name)).toBe(slug);
  });

  it("gives an empty slug for a name with no Latin letters or digits", () => {
    expect(slugify("---")).toBe("");
    expect(slugify("")).toBe("");
  });
});

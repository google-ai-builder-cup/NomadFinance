import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FlaggedProviderBadge from "@/components/remittance/FlaggedProviderBadge";
import en from "@/i18n/en.json";
import type { RadarEntityProfile } from "@/types/radar";

const flaggedProvider = vi.hoisted(() => ({ current: null as RadarEntityProfile | null }));

vi.mock("@/hooks/useRadar", () => ({ useFlaggedProvider: () => flaggedProvider.current }));
// The real hook needs the i18next instance; the strings are what is under test, so read en.json.
vi.mock("@/hooks/useI18n", () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, string>) => {
      const text = key
        .split(".")
        .reduce<unknown>((node, part) => (node as Record<string, unknown>)[part], en) as string;
      return text.replace(/{{(\w+)}}/g, (_, name: string) => values?.[name] ?? "");
    },
  }),
}));

const ENTITY: RadarEntityProfile = {
  slug: "example-remit",
  name: "Example Remit",
  entity_type: "money_transfer_operator",
  corridors: ["SG-IN"],
  host_countries: ["SG"],
  report_count: 4,
  incident_count: 3,
  violation_counts: {},
  community_rating: 3.5,
  risk_level: "medium",
  flagged: true,
};

function render(): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <FlaggedProviderBadge firm="Example Remit" />
    </MemoryRouter>
  );
}

describe("FlaggedProviderBadge", () => {
  beforeEach(() => {
    flaggedProvider.current = null;
  });

  it("renders nothing for a provider with no flagged profile", () => {
    expect(render()).toBe("");
  });

  it("links a flagged provider to its radar profile, with the report count for screen readers", () => {
    flaggedProvider.current = ENTITY;

    const html = render();

    expect(html).toContain('href="/radar/entity/example-remit"');
    expect(html).toContain("Community flagged");
    expect(html).toContain(
      'aria-label="Community flagged: 4 worker reports about Example Remit. View details."'
    );
  });
});

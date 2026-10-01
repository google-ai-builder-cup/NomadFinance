import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FlaggedParties from "@/components/contract/FlaggedParties";
import en from "@/i18n/en.json";
import type { RadarEntityProfile } from "@/types/radar";
import type { FlaggedParty } from "@/utils/flaggedParties";

const flagged = vi.hoisted(() => ({ current: [] as FlaggedParty[] }));

vi.mock("@/hooks/useRadar", () => ({ useFlaggedParties: () => flagged.current }));
// The strings are what is under test, so read en.json instead of starting i18next.
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

function entity(slug: string, type: RadarEntityProfile["entity_type"], count: number) {
  return {
    slug,
    name: slug,
    entity_type: type,
    corridors: [],
    host_countries: ["KR"],
    report_count: count,
    incident_count: count,
    violation_counts: {},
    community_rating: 3,
    risk_level: "medium",
    flagged: true,
  } satisfies RadarEntityProfile;
}

function render(): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <FlaggedParties contractId="c_01" />
    </MemoryRouter>
  );
}

describe("FlaggedParties", () => {
  beforeEach(() => {
    flagged.current = [];
  });

  it("renders nothing when no one the contract names is flagged", () => {
    expect(render()).toBe("");
  });

  it("warns about a flagged employer with the report count and a link to its profile", () => {
    flagged.current = [
      {
        role: "employer",
        name: "Han River Metals Co., Ltd.",
        entity: entity("han-river-metals-co", "employer", 5),
      },
    ];

    const html = render();

    expect(html).toContain('href="/radar/entity/han-river-metals-co"');
    expect(html).toContain("Community flagged — 5 reports");
    expect(html).toContain("Employer: ");
    expect(html).toContain("Han River Metals Co., Ltd.");
    expect(html).toContain(
      'aria-label="Han River Metals Co., Ltd.: community flagged, 5 worker reports. View details."'
    );
  });

  it("lists the employer and the agency separately", () => {
    flagged.current = [
      { role: "employer", name: "Acme Works", entity: entity("acme-works", "employer", 2) },
      {
        role: "agency",
        name: "Acme Recruiters",
        entity: entity("acme-recruiters", "recruitment_agency", 6),
      },
    ];

    const html = render();

    expect(html.match(/<li /g)).toHaveLength(2);
    expect(html).toContain("Recruitment agency");
    expect(html).toContain('href="/radar/entity/acme-recruiters"');
  });
});

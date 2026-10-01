import { describe, expect, it } from "vitest";

import type { RadarEntityProfile } from "@/types/radar";
import { findFlaggedParties, matchKey } from "@/utils/flaggedParties";

function entity(over: Partial<RadarEntityProfile> & { slug: string }): RadarEntityProfile {
  return {
    name: over.slug,
    entity_type: "employer",
    corridors: [],
    host_countries: ["KR"],
    report_count: 3,
    incident_count: 3,
    violation_counts: {},
    community_rating: 3.5,
    risk_level: "medium",
    flagged: true,
    ...over,
  };
}

const NONE = { employer_name: null, agency_name: null };

describe("matchKey", () => {
  it.each([
    ["Han River Metals Co., Ltd.", "han-river-metals"],
    ["Han River Metals Co", "han-river-metals"],
    ["Han River Metals", "han-river-metals"],
    ["Sawit Jaya Plantations Sdn. Bhd.", "sawit-jaya-plantations"],
    ["Outback Harvest Pty Ltd", "outback-harvest"],
    ["Bayanihan Overseas Recruitment Pty Ltd", "bayanihan-overseas-recruitment"],
    ["Sakura Gardens Care Co., Ltd.", "sakura-gardens-care"],
  ])("reduces %j to %j", (name, key) => {
    expect(matchKey(name)).toBe(key);
  });

  it("drops only trailing legal words, never a middle one or the whole name", () => {
    expect(matchKey("Co-op Staffing")).toBe("co-op-staffing");
    expect(matchKey("Ltd")).toBe("ltd");
    expect(matchKey("---")).toBe("");
  });
});

describe("findFlaggedParties", () => {
  it("flags an employer whose contract name carries a legal suffix the profile lacks", () => {
    const han = entity({ slug: "han-river-metals-co", name: "Han River Metals Co" });

    const found = findFlaggedParties(
      { employer_name: "Han River Metals Co., Ltd.", agency_name: null },
      [entity({ slug: "other" }), han]
    );

    expect(found).toEqual([{ role: "employer", name: "Han River Metals Co., Ltd.", entity: han }]);
  });

  it("flags an agency against a recruitment agency profile", () => {
    const agency = entity({
      slug: "bayanihan-overseas-recruitment",
      entity_type: "recruitment_agency",
    });

    const found = findFlaggedParties(
      {
        employer_name: "Outback Harvest Pty Ltd",
        agency_name: "Bayanihan Overseas Recruitment Pty Ltd",
      },
      [agency]
    );

    expect(found.map((party) => [party.role, party.entity.slug])).toEqual([
      ["agency", "bayanihan-overseas-recruitment"],
    ]);
  });

  it("lists both when the employer and the agency are flagged", () => {
    const found = findFlaggedParties(
      { employer_name: "Acme Works", agency_name: "Acme Recruiters" },
      [
        entity({ slug: "acme-works" }),
        entity({ slug: "acme-recruiters", entity_type: "recruitment_agency" }),
      ]
    );

    expect(found.map((party) => party.role)).toEqual(["employer", "agency"]);
  });

  it("matches through an alias", () => {
    const aliased = entity({ slug: "hrm", aliases: ["Han River Metals"] });

    expect(
      findFlaggedParties({ employer_name: "Han River Metals Co., Ltd.", agency_name: null }, [
        aliased,
      ])
    ).toHaveLength(1);
  });

  it("shows nothing for a profile that is not flagged", () => {
    expect(
      findFlaggedParties({ employer_name: "Acme Works", agency_name: null }, [
        entity({ slug: "acme-works", flagged: false }),
      ])
    ).toEqual([]);
  });

  it("never matches a business of the other kind with the same name", () => {
    const found = findFlaggedParties({ employer_name: "Acme Works", agency_name: "Acme Works" }, [
      entity({ slug: "acme-works", entity_type: "money_transfer_operator" }),
      entity({ slug: "acme-works-2", name: "Acme Works", entity_type: "recruitment_agency" }),
    ]);

    expect(found.map((party) => party.role)).toEqual(["agency"]);
  });

  it("prefers the profile with most reports when several match", () => {
    const small = entity({ slug: "acme-works", report_count: 2 });
    const large = entity({ slug: "acme-works-ltd", report_count: 7 });

    expect(
      findFlaggedParties({ employer_name: "Acme Works", agency_name: null }, [small, large])[0]
        ?.entity
    ).toBe(large);
  });

  it("returns nothing for no names, no entities, or an empty name", () => {
    expect(findFlaggedParties(NONE, [entity({ slug: "acme-works" })])).toEqual([]);
    expect(findFlaggedParties({ employer_name: "Acme Works", agency_name: null }, [])).toEqual([]);
    expect(
      findFlaggedParties({ employer_name: "---", agency_name: null }, [entity({ slug: "" })])
    ).toEqual([]);
  });
});
